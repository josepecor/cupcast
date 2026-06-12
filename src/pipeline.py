"""
pipeline.py — orquestador del proyecto CupCast.

Modos de ejecución:
    --backtest-only   Genera backtest.json con WC 2010–2022 (modo estático)
    (sin flag)        Pipeline diario: descarga → resuelve → reentrena → predice → escribe JSONs

Uso:
    python src/pipeline.py --backtest-only
    python src/pipeline.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from data import download_historical, load_historical  # noqa: E402
from model import DixonColesModel  # noqa: E402
from elo import EloModel  # noqa: E402
from evaluate import evaluate  # noqa: E402
from freeze import FreezeManager, make_match_id  # noqa: E402
from simulate import TournamentSimulator, load_groups  # noqa: E402
from schedule import fetch_and_save as fetch_schedule  # noqa: E402

DOCS_DIR = _ROOT / "docs"
DATA_DIR = _ROOT / "data"

WC_EDITIONS = [
    {"torneo": "World Cup 2010", "inicio": "2010-06-11", "fin": "2010-07-11"},
    {"torneo": "World Cup 2014", "inicio": "2014-06-12", "fin": "2014-07-13"},
    {"torneo": "World Cup 2018", "inicio": "2018-06-14", "fin": "2018-07-15"},
    {"torneo": "World Cup 2022", "inicio": "2022-11-20", "fin": "2022-12-18"},
]


# ---------------------------------------------------------------------------
# Helpers de calendario
# ---------------------------------------------------------------------------

def _load_schedule() -> list[dict]:
    path = DATA_DIR / "wc2026_schedule.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("matches", [])


def _load_live_predictions() -> list[dict]:
    path = DOCS_DIR / "predictions.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("proximos_partidos", [])


def _results_set(df: pd.DataFrame) -> set[str]:
    """
    Genera el conjunto de IDs de partidos con resultado.
    Incluye variantes ±1 día para absorber discrepancias entre fuentes que usan
    fechas locales (martj42) vs UTC (football-data.org) en partidos nocturnos.
    """
    ids: set[str] = set()
    for row in df.itertuples(index=False):
        base = pd.Timestamp(row.date)
        for delta in (-1, 0, 1):
            d = (base + pd.Timedelta(days=delta)).strftime("%Y-%m-%d")
            ids.add(make_match_id(d, row.home, row.away))
    return ids


def _upcoming_matches(df: pd.DataFrame, schedule: list[dict]) -> list[dict]:
    """Partidos del calendario con equipos conocidos que aún no tienen resultado."""
    played = _results_set(df)
    upcoming = []
    for m in schedule:
        if "TBD" in m.get("local", "") or "TBD" in m.get("visitante", ""):
            continue
        mid = m.get("id") or make_match_id(m["fecha"][:10], m["local"], m["visitante"])
        if mid not in played:
            upcoming.append({**m, "id": mid})
    return upcoming


def _phase_complete(df: pd.DataFrame, schedule: list[dict], phase: str, today: str) -> bool:
    """
    Devuelve True si todos los partidos de una fase con fecha <= hoy tienen resultado.
    Ignora partidos con equipos TBD.
    """
    played = _results_set(df)
    missing = [
        m for m in schedule
        if m.get("fase") == phase
        and m["fecha"][:10] < today
        and "TBD" not in m.get("local", "")
        and "TBD" not in m.get("visitante", "")
        and (m.get("id") or make_match_id(m["fecha"][:10], m["local"], m["visitante"])) not in played
    ]
    return len(missing) == 0


def _phase_fully_done(df: pd.DataFrame, schedule: list[dict], phase: str) -> bool:
    """
    True si TODOS los partidos conocidos de la fase tienen resultado.
    A diferencia de _phase_complete (que solo mira partidos anteriores a hoy),
    esta función mira el total de la fase — para saber si ya terminó del todo.
    """
    played = _results_set(df)
    return all(
        (m.get("id") or make_match_id(m["fecha"][:10], m["local"], m["visitante"])) in played
        for m in schedule
        if m.get("fase") == phase
        and "TBD" not in m.get("local", "")
        and "TBD" not in m.get("visitante", "")
    )


def _detect_current_phase(df: pd.DataFrame, schedule: list[dict], today: str) -> str:
    """
    Devuelve la fase activa o la próxima fase si el torneo aún no ha empezado.

    - Pre-torneo: devuelve la fase del primer partido del calendario.
    - En curso: la primera fase con partidos iniciados pero no completamente resueltos.
    - Finalizado: todas las fases resueltas.
    """
    phases = ["grupos", "r32", "octavos", "cuartos", "semifinal", "final"]

    known_matches = [m for m in schedule if "TBD" not in m.get("local", "")]
    if not known_matches:
        return "sin_calendario"

    tournament_started = any(m["fecha"][:10] <= today for m in known_matches)
    if not tournament_started:
        return known_matches[0].get("fase", "grupos")

    for phase in phases:
        phase_matches = [m for m in schedule if m.get("fase") == phase]
        if not phase_matches:
            continue
        started = any(m["fecha"][:10] <= today for m in phase_matches)
        if started and not _phase_fully_done(df, schedule, phase):
            return phase
    return "finalizado"


# ---------------------------------------------------------------------------
# Pipeline diario
# ---------------------------------------------------------------------------

def run_daily(
    df_all: pd.DataFrame,
    n_simulations: int = 10_000,
    torneo: str = "FIFA World Cup 2026",
) -> None:
    """
    Ejecuta el pipeline diario completo en el orden estricto de CLAUDE.md sección 7:

    1. Cargar predicciones vivas del día anterior
    2. Resolver predicciones con resultados nuevos → JSONL (antes de reentrenar)
    3. Guard de completitud de fase
    4. Reentrenar Dixon-Coles y Elo
    5. Predecir partidos pendientes + simular torneo
    6. Escribir predictions.json y track_record.json
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today   = now_str[:10]

    fm       = FreezeManager(DOCS_DIR)

    # ── Paso 0: actualizar calendario desde la API (falla silenciosa → caché) ─
    print("  Actualizando calendario desde football-data.org…")
    fetch_schedule()

    schedule = _load_schedule()

    # ── Paso 1: cargar predicciones vivas ───────────────────────────────────
    live = _load_live_predictions()
    print(f"  Predicciones vivas cargadas: {len(live)}")

    # ── Paso 2: resolver predicciones (ANTES de reentrenar) ─────────────────
    resolved, still_pending = fm.resolve(live, df_all)
    if resolved:
        fm.append(resolved)
        print(f"  Resueltos: {len(resolved)} partido(s) — añadidos al track record.")
    else:
        print("  Sin nuevos resultados para resolver.")

    # ── Paso 3: guard de completitud ────────────────────────────────────────
    current_phase = _detect_current_phase(df_all, schedule, today)
    print(f"  Fase actual: {current_phase}")

    if current_phase == "finalizado":
        print("  Torneo finalizado — solo se actualiza track_record.json.")
        fm.write_json(torneo=torneo)
        return

    phase_ok = _phase_complete(df_all, schedule, current_phase, today)
    if not phase_ok:
        pending_count = len([
            m for m in schedule
            if m.get("fase") == current_phase
            and m["fecha"][:10] < today
            and "TBD" not in m.get("local", "")
            and "TBD" not in m.get("visitante", "")
            and (m.get("id") or make_match_id(m["fecha"][:10], m["local"], m["visitante"])) not in _results_set(df_all)
        ])
        print(f"  Guard: fase '{current_phase}' incompleta ({pending_count} resultado(s) pendiente(s)).")
        print("  track_record.json actualizado. predictions.json sin cambios.")
        fm.write_json(torneo=torneo)
        return

    # ── Paso 4: reentrenar ──────────────────────────────────────────────────
    print(f"\n  Reentrenando con datos hasta {today}…")
    # Elo primero: sus ratings se usan como pesos de calidad en Dixon-Coles.
    elo = EloModel()
    elo.fit(df_all, cutoff_date=today)

    dc = DixonColesModel()
    dc.fit(df_all, reference_date=today, elo_ratings=elo.ratings_)

    # ── Paso 5a: predecir partidos pendientes ────────────────────────────────
    upcoming = _upcoming_matches(df_all, schedule)
    print(f"  Partidos pendientes con equipos conocidos: {len(upcoming)}")

    new_predictions: list[dict] = []
    for m in upcoming:
        try:
            dc_p  = dc.predict_proba(m["local"], m["visitante"], neutral=True)
            elo_p = elo.predict_proba(m["local"], m["visitante"], neutral=True)
        except KeyError:
            # Equipo no visto en entrenamiento — omitir predicción
            print(f"    ⚠ Sin parámetros para {m['local']} vs {m['visitante']} — omitido.")
            continue

        new_predictions.append({
            "id":               m["id"],
            "fecha":            m["fecha"],
            "fase":             m.get("fase", ""),
            "grupo":            m.get("grupo", ""),
            "local":            m["local"],
            "visitante":        m["visitante"],
            "prob_local":       dc_p["prob_home"],
            "prob_empate":      dc_p["prob_draw"],
            "prob_visitante":   dc_p["prob_away"],
            "marcador_probable": dc_p.get("most_likely_score", ""),
            "fecha_prediccion": now_str,
            "prob_local_elo":      elo_p["prob_home"],
            "prob_empate_elo":     elo_p["prob_draw"],
            "prob_visitante_elo":  elo_p["prob_away"],
        })

    # ── Paso 5b: simular torneo ──────────────────────────────────────────────
    print(f"  Simulando torneo ({n_simulations:,} iteraciones)…")
    groups = load_groups()
    sim_results = TournamentSimulator(dc).run(groups, n_simulations=n_simulations)

    favoritos = sorted(
        sim_results["prob_campeon"].items(), key=lambda x: x[1], reverse=True
    )

    # ── Paso 6: escribir JSONs ───────────────────────────────────────────────
    DOCS_DIR.mkdir(exist_ok=True)

    predictions_out = {
        "metadata": {
            "torneo":          torneo,
            "generado":        now_str,
            "entrenado_hasta": today,
            "fase_actual":     current_phase,
            "modelo":          "dixon-coles-v1",
        },
        "favoritos": [
            {"equipo": t, "prob_campeon": p} for t, p in favoritos
        ],
        "proximos_partidos": new_predictions,
    }

    with open(DOCS_DIR / "predictions.json", "w", encoding="utf-8") as f:
        json.dump(predictions_out, f, ensure_ascii=False, indent=2)
    print(f"  predictions.json → {len(new_predictions)} partidos, {len(favoritos)} favoritos.")

    fm.write_json(torneo=torneo)
    print("  track_record.json actualizado.")


# ---------------------------------------------------------------------------
# Backtest (modo estático)
# ---------------------------------------------------------------------------

def _wc_matches(df_all: pd.DataFrame, inicio: str, fin: str) -> pd.DataFrame:
    return df_all[
        (df_all["date"] >= inicio)
        & (df_all["date"] <= fin)
        & (df_all["tournament"] == "FIFA World Cup")
    ].copy()


def _result_outcome(row) -> str:
    if row.home_goals > row.away_goals:
        return "home"
    if row.home_goals < row.away_goals:
        return "away"
    return "draw"


def run_backtest(df_all: pd.DataFrame) -> dict:
    resultados_por_torneo = []
    all_dc_probs, all_elo_probs, all_outcomes = [], [], []

    for edition in WC_EDITIONS:
        nombre = edition["torneo"]
        cutoff = edition["inicio"]
        fin    = edition["fin"]

        print(f"\n{'─'*50}")
        print(f"  {nombre}  (cutoff: {cutoff})")

        df_train = df_all[df_all["date"] < cutoff]
        df_test  = _wc_matches(df_all, cutoff, fin)

        if df_test.empty:
            print("  Sin partidos en el dataset, saltando.")
            continue

        # Elo primero para usar sus ratings como pesos de calidad en DC.
        elo = EloModel()
        elo.fit(df_train, cutoff_date=cutoff)

        dc = DixonColesModel()
        dc.fit(df_train, reference_date=cutoff, elo_ratings=elo.ratings_)

        dc_probs, elo_probs, outcomes = [], [], []
        for row in df_test.itertuples(index=False):
            dc_probs.append(dc.predict_proba(row.home, row.away, neutral=True))
            elo_probs.append(elo.predict_proba(row.home, row.away, neutral=True))
            outcomes.append(_result_outcome(row))

        m = evaluate(dc_probs, outcomes, baseline_probs=elo_probs, n_buckets=10)

        print(f"  Partidos: {m['n_partidos']}  |  "
              f"DC log-loss={m['log_loss']:.4f}  Elo={m['baseline_log_loss']:.4f}  |  "
              f"DC brier={m['brier']:.4f}  Elo={m['baseline_brier']:.4f}  |  "
              f"DC hit={m['hit_rate']:.1%}  Elo={m['baseline_hit_rate']:.1%}")

        resultados_por_torneo.append({
            "torneo":             nombre,
            "n_partidos":         m["n_partidos"],
            "log_loss":           m["log_loss"],
            "brier":              m["brier"],
            "hit_rate":           m["hit_rate"],
            "baseline_log_loss":  m["baseline_log_loss"],
            "baseline_brier":     m["baseline_brier"],
            "baseline_hit_rate":  m["baseline_hit_rate"],
        })

        all_dc_probs.extend(dc_probs)
        all_elo_probs.extend(elo_probs)
        all_outcomes.extend(outcomes)

    global_metrics = evaluate(all_dc_probs, all_outcomes, baseline_probs=all_elo_probs)

    print(f"\n{'═'*50}")
    print(f"  GLOBAL ({global_metrics['n_partidos']} partidos, {len(WC_EDITIONS)} Mundiales)")
    print(f"  {'Métrica':<22} {'Dixon-Coles':>12} {'Elo':>12}")
    print(f"  {'-'*46}")
    print(f"  {'Log-loss':<22} {global_metrics['log_loss']:>12.4f} {global_metrics['baseline_log_loss']:>12.4f}")
    print(f"  {'Brier score':<22} {global_metrics['brier']:>12.4f} {global_metrics['baseline_brier']:>12.4f}")
    print(f"  {'Hit rate':<22} {global_metrics['hit_rate']:>12.1%} {global_metrics['baseline_hit_rate']:>12.1%}")
    print(f"  {'═'*46}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "metadata": {
            "generado":            now,
            "modelo":              "dixon-coles-v1",
            "torneos_evaluados":   [e["torneo"] for e in WC_EDITIONS],
        },
        "por_torneo": resultados_por_torneo,
        "global": {
            "n_partidos":         global_metrics["n_partidos"],
            "log_loss":           global_metrics["log_loss"],
            "brier":              global_metrics["brier"],
            "hit_rate":           global_metrics["hit_rate"],
            "baseline_log_loss":  global_metrics["baseline_log_loss"],
            "baseline_brier":     global_metrics["baseline_brier"],
            "baseline_hit_rate":  global_metrics["baseline_hit_rate"],
        },
        "calibracion": global_metrics["calibracion"],
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="CupCast pipeline")
    parser.add_argument(
        "--backtest-only",
        action="store_true",
        help="Genera backtest.json con WC 2010–2022 y termina.",
    )
    parser.add_argument(
        "--n-simulations",
        type=int,
        default=10_000,
        help="Iteraciones Monte Carlo para la simulación del torneo (default: 10 000).",
    )
    args = parser.parse_args()

    print("Descargando / cargando dataset histórico…")
    download_historical()
    df_all = load_historical()
    print(f"  {len(df_all):,} partidos cargados.\n")

    if args.backtest_only:
        backtest = run_backtest(df_all)
        DOCS_DIR.mkdir(exist_ok=True)
        out = DOCS_DIR / "backtest.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(backtest, f, ensure_ascii=False, indent=2)
        print(f"\n  backtest.json guardado → {out}")
        return

    run_daily(df_all, n_simulations=args.n_simulations)


if __name__ == "__main__":
    main()
