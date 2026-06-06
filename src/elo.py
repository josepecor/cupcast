"""
elo.py — Elo adaptado al fútbol con ventaja de local y peso por torneo.

Sirve como baseline contra el que comparar Dixon-Coles.
La pregunta central del proyecto es: ¿bate Dixon-Coles al Elo?

Mecánica:
    nuevo_rating = rating + K × gd_mult × (resultado_real − resultado_esperado)

    resultado_real  : victoria=1, empate=0.5, derrota=0
    resultado_esperado: 1/(1 + 10^(−delta/400)), donde delta incluye
                        la ventaja de local (si el partido no es neutral)
    K               : sensibilidad al resultado, escalada por importancia del torneo
    gd_mult         : multiplicador por diferencia de goles (goleadas actualizan más)

Uso básico:
    elo = EloModel()
    elo.fit(df, cutoff_date="2022-11-20")
    result = elo.predict_proba("France", "Morocco", neutral=True)
    print(elo.ranking(10))
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

K_BASE = 30.0            # sensibilidad base por partido
HOME_ADV = 100.0         # puntos de bonus por jugar en casa
INITIAL_RATING = 1500.0  # rating de partida para equipos desconocidos
DRAW_BASE = 0.28         # probabilidad de empate entre equipos iguales


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _tournament_weight(tournament: str) -> float:
    """Multiplica K según la importancia del torneo."""
    t = tournament.lower()
    if "world cup" in t and "qualif" not in t and "qualifier" not in t:
        return 2.0
    if any(x in t for x in ["euro", "copa america", "africa cup", "asian cup",
                              "gold cup", "nations league"]):
        if "qualif" not in t and "qualifier" not in t:
            return 1.5
    if "friendly" in t:
        return 0.5
    return 1.0   # clasificatorias, torneos regionales, etc.


def _gd_mult(gd: int) -> float:
    """
    Factor por diferencia de goles (fórmula World Football Elo).
    gd=0→1.0, gd=1→1.0, gd=2→1.5, gd≥3→(11+gd)/8
    """
    if gd <= 1:
        return 1.0
    if gd == 2:
        return 1.5
    return (11 + gd) / 8.0


def _expected_score(r_home: float, r_away: float, neutral: bool) -> float:
    """Resultado esperado ∈ [0,1] para el equipo local."""
    bonus = 0.0 if neutral else HOME_ADV
    return 1.0 / (1.0 + 10.0 ** (-(r_home - r_away + bonus) / 400.0))


def _proba_from_expected(E: float, draw_base: float) -> tuple[float, float, float]:
    """
    Convierte el resultado esperado Elo (E ∈ [0,1]) en probabilidades W/D/L.

    La probabilidad de empate decae linealmente conforme |E−0.5| crece:
        P(draw) = draw_base × (1 − |2E − 1|)
    El resto se reparte entre victoria y derrota en proporción a E.
    """
    p_draw = draw_base * (1.0 - abs(2.0 * E - 1.0))
    remaining = 1.0 - p_draw
    p_home = remaining * E
    p_away = remaining * (1.0 - E)
    return p_home, p_draw, p_away


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

class EloModel:
    """
    Elo adaptado al fútbol.

    Parameters
    ----------
    k_base : float
        Sensibilidad base. Escala con el torneo y la diferencia de goles.
    home_advantage : float
        Puntos de bonus para el equipo local (0 en partidos neutrales).
    initial_rating : float
        Rating asignado a equipos no vistos anteriormente.
    draw_base : float
        Probabilidad de empate entre dos equipos de rating idéntico.
    """

    def __init__(
        self,
        k_base: float = K_BASE,
        home_advantage: float = HOME_ADV,
        initial_rating: float = INITIAL_RATING,
        draw_base: float = DRAW_BASE,
    ) -> None:
        self.k_base = k_base
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.draw_base = draw_base
        self.ratings_: dict[str, float] = {}
        self._fitted: bool = False

    # ------------------------------------------------------------------
    # Ajuste
    # ------------------------------------------------------------------

    def fit(
        self, df: pd.DataFrame, cutoff_date: str | pd.Timestamp
    ) -> "EloModel":
        """
        Calcula ratings procesando todos los partidos en orden cronológico.

        A diferencia de Dixon-Coles, Elo necesita toda la historia porque
        los ratings son acumulativos — el pasado lejano ya fue "olvidado"
        implícitamente por las actualizaciones posteriores.

        Parameters
        ----------
        df : DataFrame
            Datos de data.load_historical(). Anti-leakage: solo se procesan
            partidos estrictamente anteriores a cutoff_date.
        cutoff_date : str o Timestamp
        """
        cutoff = pd.Timestamp(cutoff_date)
        data = df[df["date"] < cutoff].sort_values("date")

        ratings: dict[str, float] = {}

        for row in data.itertuples(index=False):
            home, away = row.home, row.away
            r_h = ratings.get(home, self.initial_rating)
            r_a = ratings.get(away, self.initial_rating)

            neutral = bool(row.neutral)
            E = _expected_score(r_h, r_a, neutral)

            hg, ag = int(row.home_goals), int(row.away_goals)
            actual = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)

            K = self.k_base * _tournament_weight(row.tournament)
            mult = _gd_mult(abs(hg - ag))
            change = K * mult * (actual - E)

            ratings[home] = r_h + change
            ratings[away] = r_a - change

        self.ratings_ = ratings
        self._fitted = True
        return self

    # ------------------------------------------------------------------
    # Predicción
    # ------------------------------------------------------------------

    def rating(self, team: str) -> float:
        """Rating Elo actual. Devuelve initial_rating si el equipo es desconocido."""
        return self.ratings_.get(team, self.initial_rating)

    def predict_proba(
        self, home: str, away: str, neutral: bool = False
    ) -> dict[str, float]:
        """
        Probabilidades de resultado (W/D/L) según Elo.

        Returns
        -------
        dict con claves: prob_home, prob_draw, prob_away, elo_home, elo_away
        """
        if not self._fitted:
            raise RuntimeError("Llama a fit() antes de predecir.")

        r_h = self.rating(home)
        r_a = self.rating(away)
        bonus = 0.0 if neutral else self.home_advantage
        E = 1.0 / (1.0 + 10.0 ** (-(r_h - r_a + bonus) / 400.0))

        p_home, p_draw, p_away = _proba_from_expected(E, self.draw_base)

        return {
            "prob_home": round(p_home, 4),
            "prob_draw": round(p_draw, 4),
            "prob_away": round(p_away, 4),
            "elo_home": round(r_h, 1),
            "elo_away": round(r_a, 1),
        }

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def ranking(self, top_n: int = 20) -> pd.DataFrame:
        """Devuelve los top_n equipos por rating Elo."""
        if not self._fitted:
            raise RuntimeError("Llama a fit() antes.")
        rows = [{"team": t, "elo": round(r, 1)} for t, r in self.ratings_.items()]
        return (
            pd.DataFrame(rows)
            .sort_values("elo", ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )

    def __repr__(self) -> str:
        status = f"fitted, {len(self.ratings_)} teams" if self._fitted else "not fitted"
        return f"EloModel(k={self.k_base}, home_adv={self.home_advantage}, {status})"


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    from data import load_historical

    CUTOFF = "2022-11-20"
    df = load_historical()   # Elo usa todos los partidos, sin filtro de fecha aquí
    print(f"Entrenando Elo con {len(df[df['date'] < CUTOFF]):,} partidos hasta {CUTOFF}…")

    elo = EloModel()
    elo.fit(df, cutoff_date=CUTOFF)

    print(f"\n{elo}")

    print("\n--- Semifinal WC 2022: Francia vs Marruecos (neutral) ---")
    print(elo.predict_proba("France", "Morocco", neutral=True))
    # Resultado real: Francia 2-0 Marruecos

    print("\n--- Final WC 2022: Argentina vs Francia (neutral) ---")
    print(elo.predict_proba("Argentina", "France", neutral=True))
    # Resultado real: Argentina 3-3 (4-2 pen) Francia

    print("\n--- Top 20 ranking Elo ---")
    print(elo.ranking(20).to_string(index=False))
