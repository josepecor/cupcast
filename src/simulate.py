"""
simulate.py — Monte Carlo del cuadro completo del Mundial 2026.

Formato WC 2026:
    48 equipos en 12 grupos de 4.
    Clasifican: 2 primeros de cada grupo (24) + 8 mejores terceros (8) = 32.
    R32 → R16 (octavos) → QF (cuartos) → SF (semis) → Final.
    Todos los partidos se juegan en sede neutral.

Probabilidades de salida:
    prob_clasificado : llegar a la fase eliminatoria (32 equipos)
    prob_octavos     : pasar R32 y jugar octavos (16 equipos)
    prob_cuartos     : pasar octavos (8 equipos)
    prob_semifinal   : pasar cuartos (4 equipos)
    prob_final       : llegar a la final (2 equipos)
    prob_campeon     : ganar el torneo (1 equipo)

Uso básico:
    from simulate import TournamentSimulator, WC2026_GROUPS
    from model import DixonColesModel

    sim = TournamentSimulator(model)
    results = sim.run(WC2026_GROUPS, n_simulations=10_000)
    print(results["prob_campeon"])
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Protocol

import numpy as np

_DATA_DIR = Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# Protocolo de modelo (duck typing — compatible con DixonColesModel y EloModel)
# ---------------------------------------------------------------------------

class MatchModel(Protocol):
    def predict_proba(self, home: str, away: str, neutral: bool) -> dict[str, float]:
        ...


# ---------------------------------------------------------------------------
# Carga de grupos desde fichero
# ---------------------------------------------------------------------------

def load_groups(path: str | Path | None = None) -> dict[str, list[str]]:
    """
    Carga los grupos del torneo desde un JSON.

    El fichero debe tener la clave "groups": {grupo: [e1, e2, e3, e4], ...}.
    Por defecto usa data/wc2026_groups.json.

    Parameters
    ----------
    path : ruta al JSON (opcional). Si es None usa data/wc2026_groups.json.

    Returns
    -------
    dict {grupo: [equipo1, equipo2, equipo3, equipo4]}
    """
    if path is None:
        path = _DATA_DIR / "wc2026_groups.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if "groups" not in data:
        raise ValueError(f"El fichero {path} debe tener la clave 'groups'.")
    return data["groups"]


# ---------------------------------------------------------------------------
# Caché de predicciones
# ---------------------------------------------------------------------------

class _PredCache:
    """Evita recalcular predict_proba para el mismo enfrentamiento."""

    def __init__(self, model: MatchModel) -> None:
        self._model = model
        self._cache: dict[tuple[str, str, bool], dict[str, float]] = {}

    def get(self, home: str, away: str, neutral: bool) -> dict[str, float]:
        key = (home, away, neutral)
        if key not in self._cache:
            self._cache[key] = self._model.predict_proba(home, away, neutral)
        return self._cache[key]


# ---------------------------------------------------------------------------
# Simulación de un partido
# ---------------------------------------------------------------------------

def _simulate_match(
    home: str, away: str, cache: _PredCache, allow_draw: bool = True
) -> str:
    """
    Simula un partido y devuelve el nombre del ganador (o "draw").

    En eliminatorias (allow_draw=False) los empates se resuelven proporcionalmente:
        P(home_advance) = prob_home / (prob_home + prob_away)
    Esto captura la incertidumbre de la prórroga y penales sin modelarlos explícitamente.
    """
    p = cache.get(home, away, neutral=True)
    ph, pd_, pa = p["prob_home"], p["prob_draw"], p["prob_away"]

    if allow_draw:
        r = random.random()
        if r < ph:
            return home
        if r < ph + pd_:
            return "draw"
        return away
    else:
        return home if random.random() < ph / (ph + pa) else away


# ---------------------------------------------------------------------------
# Fase de grupos
# ---------------------------------------------------------------------------

def _simulate_group(teams: list[str], cache: _PredCache) -> list[dict]:
    """
    Simula un grupo round-robin (6 partidos) y devuelve la clasificación.

    Orden de desempate: puntos → diferencia de goles aproximada → aleatorio.
    (No se modelan goles exactos: victoria da +1 GD al ganador como proxy.)
    """
    stats: dict[str, dict] = {
        t: {"pts": 0, "gd": 0, "gf": 0, "team": t} for t in teams
    }

    for home, away in combinations(teams, 2):
        result = _simulate_match(home, away, cache, allow_draw=True)
        if result == "draw":
            stats[home]["pts"] += 1
            stats[away]["pts"] += 1
        else:
            winner, loser = result, (away if result == home else home)
            stats[winner]["pts"] += 3
            stats[winner]["gd"] += 1
            stats[winner]["gf"] += 1
            stats[loser]["gd"] -= 1

    ranking = sorted(
        stats.values(),
        key=lambda s: (s["pts"], s["gd"], s["gf"], random.random()),
        reverse=True,
    )
    for pos, s in enumerate(ranking):
        s["pos"] = pos + 1
    return ranking


# ---------------------------------------------------------------------------
# Selección de los 8 mejores terceros
# ---------------------------------------------------------------------------

def _best_thirds(thirds: list[dict]) -> list[dict]:
    """Selecciona los 8 mejores terceros de los 12 grupos (criterio FIFA: pts→GD→GF)."""
    return sorted(
        thirds,
        key=lambda s: (s["pts"], s["gd"], s["gf"], random.random()),
        reverse=True,
    )[:8]


# ---------------------------------------------------------------------------
# Bracket del R32
# ---------------------------------------------------------------------------

def _build_r32(
    group_standings: dict[str, list[dict]],
    top8_thirds: list[dict],
) -> list[tuple[str, str]]:
    """
    Construye 16 enfrentamientos para el R32.

    Esquema (approximación estructuralmente correcta — actualizar con bracket FIFA):

    12 enfrentamientos cruzados ganador-segundo entre grupos adyacentes:
        A1 vs B2, B1 vs A2
        C1 vs D2, D1 vs C2
        E1 vs F2, F1 vs E2
        G1 vs H2, H1 vs G2
        I1 vs J2, J1 vs I2
        K1 vs L2, L1 vs K2
    → 24 equipos (12 ganadores + 12 segundos), 12 partidos

    4 enfrentamientos entre los 8 mejores terceros (emparejados en orden de ranking):
        T1 vs T2, T3 vs T4, T5 vs T6, T7 vs T8
    → 8 equipos, 4 partidos

    Total: 16 partidos, 32 equipos. ✓
    """
    winners = {g: group_standings[g][0]["team"] for g in group_standings}
    runners = {g: group_standings[g][1]["team"] for g in group_standings}

    matchups: list[tuple[str, str]] = []

    group_pairs = [
        ("A", "B"), ("C", "D"), ("E", "F"),
        ("G", "H"), ("I", "J"), ("K", "L"),
    ]
    for g1, g2 in group_pairs:
        matchups.append((winners[g1], runners[g2]))
        matchups.append((winners[g2], runners[g1]))

    thirds = [t["team"] for t in top8_thirds]
    for i in range(0, 8, 2):
        matchups.append((thirds[i], thirds[i + 1]))

    return matchups  # 16 partidos


# ---------------------------------------------------------------------------
# Rondas de eliminatoria
# ---------------------------------------------------------------------------

def _simulate_round(bracket: list[tuple[str, str]], cache: _PredCache) -> list[str]:
    """Simula una ronda completa y devuelve los ganadores (en orden de bracket)."""
    return [_simulate_match(h, a, cache, allow_draw=False) for h, a in bracket]


def _next_round_pairs(teams: list[str]) -> list[tuple[str, str]]:
    """Genera pares para la siguiente ronda respetando el orden del bracket."""
    return [(teams[i], teams[i + 1]) for i in range(0, len(teams), 2)]


# ---------------------------------------------------------------------------
# Simulador principal
# ---------------------------------------------------------------------------

class TournamentSimulator:
    """
    Simulador Monte Carlo del cuadro completo del Mundial.

    Parameters
    ----------
    model : objeto con método predict_proba(home, away, neutral) -> dict
        Compatible con DixonColesModel y EloModel.
    """

    def __init__(self, model: MatchModel) -> None:
        self._cache = _PredCache(model)

    def run(
        self,
        groups: dict[str, list[str]],
        n_simulations: int = 10_000,
        seed: int | None = None,
    ) -> dict:
        """
        Ejecuta n_simulations del torneo completo.

        Parameters
        ----------
        groups : dict {grupo: [e1, e2, e3, e4]}
        n_simulations : int
        seed : int opcional (reproducibilidad)

        Returns
        -------
        dict con prob_clasificado, prob_octavos, prob_cuartos, prob_semifinal,
             prob_final, prob_campeon, n_simulations
        """
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        all_teams = [t for g in groups.values() for t in g]

        stages = ["clasificado", "octavos", "cuartos", "semifinal", "final", "campeon"]
        counts: dict[str, defaultdict] = {s: defaultdict(int) for s in stages}

        for _ in range(n_simulations):
            self._run_once(groups, counts)

        def to_prob(counter: defaultdict) -> dict[str, float]:
            return {t: round(counter[t] / n_simulations, 4) for t in all_teams if counter[t]}

        return {f"prob_{s}": to_prob(counts[s]) for s in stages} | {"n_simulations": n_simulations}

    def _run_once(
        self,
        groups: dict[str, list[str]],
        counts: dict[str, defaultdict],
    ) -> None:
        cache = self._cache

        # ── Fase de grupos ──────────────────────────────────────────────────
        group_standings: dict[str, list[dict]] = {}
        thirds: list[dict] = []

        for g_name, teams in groups.items():
            standing = _simulate_group(teams, cache)
            group_standings[g_name] = standing
            thirds.append(standing[2])

        top8 = _best_thirds(thirds)

        for standing in group_standings.values():
            counts["clasificado"][standing[0]["team"]] += 1
            counts["clasificado"][standing[1]["team"]] += 1
        for t in top8:
            counts["clasificado"][t["team"]] += 1

        # ── R32 → octavos (16 equipos) ──────────────────────────────────────
        r32 = _build_r32(group_standings, top8)
        r16_teams = _simulate_round(r32, cache)           # 16 equipos

        for t in r16_teams:
            counts["octavos"][t] += 1

        # ── Octavos → cuartos (8 equipos) ───────────────────────────────────
        qf_teams = _simulate_round(_next_round_pairs(r16_teams), cache)   # 8 equipos

        for t in qf_teams:
            counts["cuartos"][t] += 1

        # ── Cuartos → semis (4 equipos) ─────────────────────────────────────
        sf_teams = _simulate_round(_next_round_pairs(qf_teams), cache)    # 4 equipos

        for t in sf_teams:
            counts["semifinal"][t] += 1

        # ── Semis → final (2 finalistas) ────────────────────────────────────
        finalists = _simulate_round(_next_round_pairs(sf_teams), cache)   # 2 equipos

        for t in finalists:
            counts["final"][t] += 1

        # ── Final (1 campeón) ────────────────────────────────────────────────
        champion = _simulate_match(finalists[0], finalists[1], cache, allow_draw=False)
        counts["campeon"][champion] += 1


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))

    from data import load_historical
    from model import DixonColesModel

    CUTOFF = "2026-06-06"
    N_SIM = 5_000

    print(f"Cargando datos hasta {CUTOFF}…")
    df = load_historical()
    df_train = df[df["date"] < CUTOFF]
    print(f"  {len(df_train):,} partidos de entrenamiento.")

    print("\nEntrenando Dixon-Coles…")
    dc = DixonColesModel()
    dc.fit(df_train, reference_date=CUTOFF)

    groups = load_groups()
    print(f"\nSimulando WC 2026 ({N_SIM:,} simulaciones)…")
    sim = TournamentSimulator(dc)
    results = sim.run(groups, n_simulations=N_SIM, seed=42)

    print("\n─── Top 16 favoritos (prob. campeón) ───")
    campeon = sorted(results["prob_campeon"].items(), key=lambda x: x[1], reverse=True)
    for i, (team, prob) in enumerate(campeon[:16], 1):
        bar = "█" * int(prob * 200)
        print(f"  {i:>2}. {team:<22}  {prob:>5.1%}  {bar}")

    print("\n─── Top 10 (prob. llegar a final) ───")
    final = sorted(results["prob_final"].items(), key=lambda x: x[1], reverse=True)
    for team, prob in final[:10]:
        print(f"  {team:<22}  {prob:>5.1%}")

    print("\n─── Top 10 (prob. clasificar desde grupos) ───")
    clas = sorted(results["prob_clasificado"].items(), key=lambda x: x[1], reverse=True)
    for team, prob in clas[:10]:
        print(f"  {team:<22}  {prob:>5.1%}")
