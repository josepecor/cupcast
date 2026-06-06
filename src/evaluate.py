"""
evaluate.py — métricas de evaluación para predicciones probabilísticas de fútbol.

Métricas implementadas:
    log_loss     — penaliza confianza equivocada; métrica principal
    brier_score  — error cuadrático sobre las 3 probabilidades; más intuitivo
    hit_rate     — % de veces que el outcome más probable fue correcto (informativo)

Calibración:
    calibration_curve — agrupa todos los pares (p_predicha, outcome_real) de los
                        3 outcomes en buckets; compara media predicha vs observada.

Todas las funciones son puras (sin estado) y aceptan listas de dicts estándar:
    probs   : [{"prob_home": 0.41, "prob_draw": 0.29, "prob_away": 0.30}, ...]
    outcomes: ["home", "draw", "away", ...]   — outcome real de cada partido
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# Tipo interno
_KEYS = ("prob_home", "prob_draw", "prob_away")
_IDX = {"home": 0, "draw": 1, "away": 2}

EPS = 1e-10   # evita log(0)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _probs_array(probs: list[dict]) -> np.ndarray:
    """Convierte lista de dicts en matriz (N, 3)."""
    return np.array([[p["prob_home"], p["prob_draw"], p["prob_away"]] for p in probs])


def _outcomes_onehot(outcomes: list[str]) -> np.ndarray:
    """Convierte lista de outcomes en matriz one-hot (N, 3)."""
    n = len(outcomes)
    y = np.zeros((n, 3))
    for i, o in enumerate(outcomes):
        y[i, _IDX[o]] = 1.0
    return y


# ---------------------------------------------------------------------------
# Métricas por partido
# ---------------------------------------------------------------------------

def match_log_loss(prob: dict, outcome: str) -> float:
    """Log-loss de un solo partido."""
    p = max(prob[f"prob_{outcome}"], EPS)
    return -np.log(p)


def match_brier(prob: dict, outcome: str) -> float:
    """Brier score de un solo partido (suma sobre los 3 outcomes)."""
    y = np.zeros(3)
    y[_IDX[outcome]] = 1.0
    p = np.array([prob["prob_home"], prob["prob_draw"], prob["prob_away"]])
    return float(np.sum((p - y) ** 2))


# ---------------------------------------------------------------------------
# Métricas agregadas
# ---------------------------------------------------------------------------

def log_loss(probs: list[dict], outcomes: list[str]) -> float:
    """
    Log-loss medio sobre N partidos.
    Penaliza fuertemente la confianza equivocada.
    Rango: [0, ∞). Modelo aleatorio (1/3 cada outcome) ≈ 1.099.
    """
    P = _probs_array(probs)
    Y = _outcomes_onehot(outcomes)
    # Solo la columna del outcome real importa
    p_correct = np.clip((P * Y).sum(axis=1), EPS, 1.0)
    return float(-np.mean(np.log(p_correct)))


def brier_score(probs: list[dict], outcomes: list[str]) -> float:
    """
    Brier score medio sobre N partidos (suma de los 3 outcomes).
    Rango: [0, 2]. Modelo aleatorio (1/3 cada outcome) ≈ 0.667.
    """
    P = _probs_array(probs)
    Y = _outcomes_onehot(outcomes)
    return float(np.mean(np.sum((P - Y) ** 2, axis=1)))


def hit_rate(probs: list[dict], outcomes: list[str]) -> float:
    """
    Fracción de partidos donde el outcome más probable fue correcto.
    Métrica intuitiva pero NO probabilística — usar solo como referencia.
    """
    keys = ["prob_home", "prob_draw", "prob_away"]
    outcome_names = ["home", "draw", "away"]
    hits = sum(
        outcome_names[np.argmax([p[k] for k in keys])] == o
        for p, o in zip(probs, outcomes)
    )
    return hits / len(outcomes)


# ---------------------------------------------------------------------------
# Calibración
# ---------------------------------------------------------------------------

def calibration_curve(
    probs: list[dict],
    outcomes: list[str],
    n_buckets: int = 10,
) -> list[dict]:
    """
    Curva de calibración: ¿se cumplen las probabilidades predichas?

    Agrupa TODOS los pares (p_predicha, outcome_real) de los 3 outcomes
    (3×N pares en total) en n_buckets y compara media predicha vs observada.

    Returns
    -------
    Lista de dicts: {bucket, predicho, observado, n}
    Un modelo perfecto tiene predicho ≈ observado en todos los buckets.
    """
    P = _probs_array(probs).ravel()   # (3N,) — todas las probabilidades
    Y = _outcomes_onehot(outcomes).ravel()  # (3N,) — 0/1 si ese outcome ocurrió

    edges = np.linspace(0.0, 1.0, n_buckets + 1)
    result = []

    for i in range(n_buckets):
        lo, hi = edges[i], edges[i + 1]
        # El último bucket incluye el extremo derecho
        mask = (P >= lo) & (P < hi) if i < n_buckets - 1 else (P >= lo) & (P <= hi)
        n = int(mask.sum())
        if n == 0:
            continue
        result.append({
            "bucket": f"{lo:.1f}-{hi:.1f}",
            "predicho": round(float(P[mask].mean()), 3),
            "observado": round(float(Y[mask].mean()), 3),
            "n": n,
        })

    return result


# ---------------------------------------------------------------------------
# Evaluación completa
# ---------------------------------------------------------------------------

def evaluate(
    probs: list[dict],
    outcomes: list[str],
    baseline_probs: list[dict] | None = None,
    n_buckets: int = 10,
) -> dict:
    """
    Calcula todas las métricas para un conjunto de predicciones.

    Parameters
    ----------
    probs : list of dicts
        Predicciones del modelo principal (Dixon-Coles).
    outcomes : list of str
        Outcomes reales: "home", "draw" o "away".
    baseline_probs : list of dicts, optional
        Predicciones del baseline (Elo). Si se provee, se calculan también
        sus métricas para comparación directa.
    n_buckets : int
        Número de buckets para la curva de calibración.

    Returns
    -------
    dict con esquema compatible con backtest.json y track_record.json:
        log_loss, brier, hit_rate, [baseline_log_loss, baseline_brier],
        calibracion, n_partidos
    """
    result: dict = {
        "n_partidos": len(outcomes),
        "log_loss": round(log_loss(probs, outcomes), 4),
        "brier": round(brier_score(probs, outcomes), 4),
        "hit_rate": round(hit_rate(probs, outcomes), 4),
        "calibracion": calibration_curve(probs, outcomes, n_buckets),
    }

    if baseline_probs is not None:
        result["baseline_log_loss"] = round(log_loss(baseline_probs, outcomes), 4)
        result["baseline_brier"] = round(brier_score(baseline_probs, outcomes), 4)
        result["baseline_hit_rate"] = round(hit_rate(baseline_probs, outcomes), 4)

    return result


# ---------------------------------------------------------------------------
# Smoke test: backtest mini sobre WC 2022
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    from data import load_historical
    from model import DixonColesModel
    from elo import EloModel

    CUTOFF = "2022-11-20"

    df_all = load_historical()
    df_train = df_all[df_all["date"] < CUTOFF]

    # Partidos de WC 2022 con resultado conocido
    df_wc22 = df_all[
        (df_all["date"] >= CUTOFF)
        & (df_all["date"] <= "2022-12-18")
        & (df_all["tournament"] == "FIFA World Cup")
    ].copy()

    print(f"WC 2022: {len(df_wc22)} partidos encontrados en el dataset.")
    print(f"Train: {len(df_train):,} partidos hasta {CUTOFF}.\n")

    # Entrenar modelos
    print("Entrenando Dixon-Coles…")
    dc = DixonColesModel()
    dc.fit(df_train, reference_date=CUTOFF)

    print("Entrenando Elo…")
    elo = EloModel()
    elo.fit(df_train, cutoff_date=CUTOFF)

    # Generar predicciones (todos los WC 2022 son en sede neutral)
    dc_probs, elo_probs, outcomes = [], [], []
    for row in df_wc22.itertuples(index=False):
        dc_probs.append(dc.predict_proba(row.home, row.away, neutral=True))
        elo_probs.append(elo.predict_proba(row.home, row.away, neutral=True))
        if row.home_goals > row.away_goals:
            outcomes.append("home")
        elif row.home_goals < row.away_goals:
            outcomes.append("away")
        else:
            outcomes.append("draw")

    print(f"\nOutcomes WC 2022: {outcomes.count('home')} local, "
          f"{outcomes.count('draw')} empate, {outcomes.count('away')} visitante\n")

    # Evaluar
    metrics = evaluate(dc_probs, outcomes, baseline_probs=elo_probs)

    print("=" * 50)
    print(f"  Partidos evaluados : {metrics['n_partidos']}")
    print(f"  {'Métrica':<22} {'Dixon-Coles':>12} {'Elo (baseline)':>15}")
    print(f"  {'-'*49}")
    print(f"  {'Log-loss':<22} {metrics['log_loss']:>12.4f} {metrics['baseline_log_loss']:>15.4f}")
    print(f"  {'Brier score':<22} {metrics['brier']:>12.4f} {metrics['baseline_brier']:>15.4f}")
    print(f"  {'Hit rate':<22} {metrics['hit_rate']:>12.2%} {metrics['baseline_hit_rate']:>15.2%}")
    print("=" * 50)

    print("\nCalibración Dixon-Coles (bucket → predicho vs observado):")
    for b in metrics["calibracion"]:
        bar = "█" * int(b["observado"] * 20)
        print(f"  {b['bucket']:>7}  pred={b['predicho']:.2f}  obs={b['observado']:.2f}"
              f"  n={b['n']:>4}  {bar}")
