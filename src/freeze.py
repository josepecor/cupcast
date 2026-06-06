"""
freeze.py — gestión del track record de predicciones congeladas.

Responsabilidad única: dado el fichero de predicciones vivas (predictions.json)
y los resultados reales (df de data.py), detectar qué partidos ya se jugaron,
puntuar las predicciones previas y añadirlas al log append-only.

Flujo de uso (llamado desde pipeline.py en este orden estricto):

    fm = FreezeManager(docs_dir)
    resolved, pending = fm.resolve(live_predictions, df_results)
    if resolved:
        fm.append(resolved)         # ANTES de reentrenar
    # ... pipeline reentrena y genera nuevas predicciones ...
    fm.write_json()                 # al final, regenera track_record.json

El orden importa: resolve() debe llamarse antes del reentrenamiento para que
las predicciones que se puntúen sean las del día anterior, no las del modelo
recién reentrenado con los resultados del partido.

Ficheros gestionados:
    docs/track_record.jsonl  — una línea JSON por partido resuelto (append-only)
    docs/track_record.json   — generado desde el JSONL; esquema para el frontend
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def make_match_id(date: str | pd.Timestamp, home: str, away: str) -> str:
    """ID determinista de partido: YYYY-MM-DD-Home-Away (espacios → guiones)."""
    d = pd.Timestamp(date).strftime("%Y-%m-%d")
    h = home.replace(" ", "-")
    a = away.replace(" ", "-")
    return f"{d}-{h}-{a}"


def _outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "local"
    if home_goals < away_goals:
        return "visitante"
    return "empate"


def _score(pred: dict, outcome: str, hg: int, ag: int) -> dict:
    """
    Añade campos de resultado y métricas a una predicción resuelta.

    Usa los nombres de campo de predictions.json (prob_local/empate/visitante).
    """
    ph = pred["prob_local"]
    pd_ = pred["prob_empate"]
    pa = pred["prob_visitante"]

    p_correct = {"local": ph, "empate": pd_, "visitante": pa}[outcome]
    ll = round(-math.log(max(p_correct, 1e-10)), 4)

    y_vec = {"local": (1, 0, 0), "empate": (0, 1, 0), "visitante": (0, 0, 1)}[outcome]
    brier = round(sum((p - y) ** 2 for p, y in zip([ph, pd_, pa], y_vec)), 4)

    max_p = max(ph, pd_, pa)
    predicted = "local" if ph == max_p else ("empate" if pd_ == max_p else "visitante")

    return {
        **pred,
        "goles_local": hg,
        "goles_visitante": ag,
        "resultado": f"{hg}-{ag}",
        "ganador": outcome,
        "log_loss": ll,
        "brier": brier,
        "acertado": predicted == outcome,
        "sorpresa": p_correct < 1 / 3,
    }


# ---------------------------------------------------------------------------
# FreezeManager
# ---------------------------------------------------------------------------

class FreezeManager:
    """
    Gestiona el log append-only de predicciones congeladas.

    Parameters
    ----------
    docs_dir : directorio donde se escriben track_record.jsonl y track_record.json
    """

    def __init__(self, docs_dir: str | Path) -> None:
        docs_dir = Path(docs_dir)
        self._jsonl = docs_dir / "track_record.jsonl"
        self._json  = docs_dir / "track_record.json"

    # ------------------------------------------------------------------
    # Resolución (paso 2 del pipeline — antes de reentrenar)
    # ------------------------------------------------------------------

    def resolve(
        self,
        live_predictions: list[dict],
        df_results: pd.DataFrame,
    ) -> tuple[list[dict], list[dict]]:
        """
        Cruza predicciones vivas con resultados reales.

        Un partido se resuelve cuando df_results contiene un resultado con la
        misma fecha y nombres de equipo que la predicción. Los IDs se construyen
        con make_match_id para que la comparación sea robusta.

        Parameters
        ----------
        live_predictions : lista de dicts con el esquema de predictions.json
            (campos obligatorios: id o [fecha, local, visitante], prob_local,
            prob_empate, prob_visitante)
        df_results : DataFrame de load_historical() con columnas date, home,
            away, home_goals, away_goals

        Returns
        -------
        resolved : predicciones puntuadas (listas para append al JSONL)
        pending  : predicciones sin resultado todavía
        """
        result_index: dict[str, tuple[int, int]] = {
            make_match_id(row.date, row.home, row.away): (int(row.home_goals), int(row.away_goals))
            for row in df_results.itertuples(index=False)
        }

        resolved: list[dict] = []
        pending:  list[dict] = []

        for pred in live_predictions:
            mid = pred.get("id") or make_match_id(
                pred["fecha"][:10], pred["local"], pred["visitante"]
            )
            if mid in result_index:
                hg, ag = result_index[mid]
                scored = _score(pred, _outcome(hg, ag), hg, ag)
                scored["id"] = mid
                resolved.append(scored)
            else:
                pred.setdefault("id", mid)
                pending.append(pred)

        return resolved, pending

    # ------------------------------------------------------------------
    # JSONL — append-only
    # ------------------------------------------------------------------

    def append(self, resolved: list[dict]) -> None:
        """Añade predicciones resueltas al JSONL. Cada llamada es atómica por partido."""
        self._jsonl.parent.mkdir(exist_ok=True)
        with open(self._jsonl, "a", encoding="utf-8") as f:
            for record in resolved:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load(self) -> list[dict]:
        """Lee todos los registros del JSONL. Devuelve [] si el fichero no existe."""
        if not self._jsonl.exists():
            return []
        records = []
        with open(self._jsonl, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    # ------------------------------------------------------------------
    # JSON para el frontend (último paso del pipeline)
    # ------------------------------------------------------------------

    def build_json(
        self, torneo: str = "FIFA World Cup 2026", n_buckets: int = 10
    ) -> dict:
        """
        Transforma el JSONL al dict completo para track_record.json.

        Calcula log-loss, brier y hit-rate globales y curva de calibración.
        Si hay campos prob_local_elo/prob_empate_elo/prob_visitante_elo en todos
        los registros, calcula también las métricas del baseline Elo.
        """
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from evaluate import evaluate as _evaluate, log_loss as _ll, brier_score as _brier

        records = self.load()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        metadata = {
            "torneo": torneo,
            "actualizado": now,
            "partidos_resueltos": len(records),
        }

        if not records:
            return {"metadata": metadata, "agregados": None, "calibracion": [], "partidos": []}

        # Convertir al formato que espera evaluate.py (prob_home/draw/away)
        _key = {"local": "home", "empate": "draw", "visitante": "away"}
        probs = [
            {"prob_home": r["prob_local"], "prob_draw": r["prob_empate"], "prob_away": r["prob_visitante"]}
            for r in records
        ]
        outcomes = [_key[r["ganador"]] for r in records]

        metrics = _evaluate(probs, outcomes, n_buckets=n_buckets)

        agregados: dict = {
            "log_loss": metrics["log_loss"],
            "brier":    metrics["brier"],
            "hit_rate": metrics["hit_rate"],
        }

        # Baseline Elo si está disponible en todos los registros
        elo_fields = ("prob_local_elo", "prob_empate_elo", "prob_visitante_elo")
        if all(all(f in r for f in elo_fields) for r in records):
            elo_probs = [
                {"prob_home": r["prob_local_elo"], "prob_draw": r["prob_empate_elo"], "prob_away": r["prob_visitante_elo"]}
                for r in records
            ]
            agregados["baseline_log_loss"] = round(_ll(elo_probs, outcomes), 4)
            agregados["baseline_brier"]    = round(_brier(elo_probs, outcomes), 4)

        return {
            "metadata":  metadata,
            "agregados": agregados,
            "calibracion": metrics["calibracion"],
            "partidos":  records,
        }

    def write_json(self, torneo: str = "FIFA World Cup 2026") -> None:
        """Construye y escribe track_record.json desde el JSONL."""
        data = self.build_json(torneo=torneo)
        self._json.parent.mkdir(exist_ok=True)
        with open(self._json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile

    print("── Smoke test FreezeManager ──")

    live = [
        {
            "id": "2026-06-15-Spain-Germany",
            "fecha": "2026-06-15T19:00:00Z",
            "fase": "grupos",
            "local": "Spain",
            "visitante": "Germany",
            "prob_local": 0.41,
            "prob_empate": 0.27,
            "prob_visitante": 0.32,
            "fecha_prediccion": "2026-06-14T08:00:00Z",
        },
        {
            "id": "2026-06-16-France-Belgium",
            "fecha": "2026-06-16T19:00:00Z",
            "fase": "grupos",
            "local": "France",
            "visitante": "Belgium",
            "prob_local": 0.52,
            "prob_empate": 0.25,
            "prob_visitante": 0.23,
            "fecha_prediccion": "2026-06-14T08:00:00Z",
        },
        {
            "id": "2026-06-17-Brazil-Colombia",
            "fecha": "2026-06-17T19:00:00Z",
            "fase": "grupos",
            "local": "Brazil",
            "visitante": "Colombia",
            "prob_local": 0.55,
            "prob_empate": 0.25,
            "prob_visitante": 0.20,
            "fecha_prediccion": "2026-06-14T08:00:00Z",
        },
    ]

    # Solo los dos primeros tienen resultado
    df_results = pd.DataFrame([
        {"date": pd.Timestamp("2026-06-15"), "home": "Spain",  "away": "Germany", "home_goals": 2, "away_goals": 1},
        {"date": pd.Timestamp("2026-06-16"), "home": "France", "away": "Belgium", "home_goals": 0, "away_goals": 1},
    ])

    with tempfile.TemporaryDirectory() as tmpdir:
        fm = FreezeManager(tmpdir)
        resolved, pending = fm.resolve(live, df_results)

        print(f"\nResueltos: {len(resolved)}  |  Pendientes: {len(pending)}")
        for r in resolved:
            print(f"  {r['id']:<35}  ganador={r['ganador']}  brier={r['brier']}  log_loss={r['log_loss']}  sorpresa={r['sorpresa']}")

        fm.append(resolved)
        fm.write_json()

        tr = fm.build_json()
        print("\nAgregados:")
        for k, v in tr["agregados"].items():
            print(f"  {k}: {v}")
        print(f"Calibración: {len(tr['calibracion'])} buckets")
        print(f"Partidos en JSONL: {tr['metadata']['partidos_resueltos']}")
        print(f"\nPendientes ({len(pending)}):")
        for p in pending:
            print(f"  {p['id']}")
