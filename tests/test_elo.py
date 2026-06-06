"""Tests de elo.py — modelo Elo con datos sintéticos."""
import pytest
import pandas as pd
from elo import EloModel


@pytest.fixture
def small_df():
    """DataFrame mínimo con 3 equipos y partidos suficientes para entrenar."""
    rows = []
    teams = [("Brazil", "Argentina"), ("France", "Germany"), ("Spain", "England"),
             ("Brazil", "France"),    ("Argentina", "Spain"), ("Germany", "England"),
             ("Brazil", "Germany"),   ("France", "Argentina"),("Spain", "Brazil")]
    for i, (h, a) in enumerate(teams):
        rows.append({"date": pd.Timestamp(f"2022-0{(i%9)//3+1}-{(i%9)+1:02d}"),
                     "home": h, "away": a,
                     "home_goals": 2, "away_goals": 1,
                     "tournament": "FIFA World Cup", "neutral": False})
    return pd.DataFrame(rows)


def test_fit_runs(small_df):
    elo = EloModel()
    elo.fit(small_df, cutoff_date="2023-01-01")
    assert elo._fitted
    assert len(elo.ratings_) > 0


def test_predict_proba_sums_to_one(small_df):
    elo = EloModel()
    elo.fit(small_df, cutoff_date="2023-01-01")
    p = elo.predict_proba("Brazil", "Argentina", neutral=True)
    total = p["prob_home"] + p["prob_draw"] + p["prob_away"]
    # Probabilidades redondeadas a 4 decimales → tolerancia de 1e-3
    assert total == pytest.approx(1.0, abs=1e-3)


def test_predict_proba_keys(small_df):
    elo = EloModel()
    elo.fit(small_df, cutoff_date="2023-01-01")
    p = elo.predict_proba("Brazil", "France", neutral=False)
    for key in ("prob_home", "prob_draw", "prob_away", "elo_home", "elo_away"):
        assert key in p


def test_home_advantage(small_df):
    elo = EloModel()
    elo.fit(small_df, cutoff_date="2023-01-01")
    p_home    = elo.predict_proba("Brazil", "France", neutral=False)
    p_neutral = elo.predict_proba("Brazil", "France", neutral=True)
    assert p_home["prob_home"] > p_neutral["prob_home"]


def test_antileakage(small_df):
    """Partidos posteriores al cutoff no deben afectar los ratings."""
    elo_early = EloModel()
    elo_early.fit(small_df, cutoff_date="2022-02-01")

    elo_full = EloModel()
    elo_full.fit(small_df, cutoff_date="2023-01-01")

    assert elo_early.ratings_ != elo_full.ratings_


def test_unknown_team(small_df):
    elo = EloModel()
    elo.fit(small_df, cutoff_date="2023-01-01")
    # Equipo desconocido → initial_rating
    assert elo.rating("Andorra") == elo.initial_rating


def test_predict_before_fit():
    elo = EloModel()
    with pytest.raises(RuntimeError):
        elo.predict_proba("A", "B", neutral=True)
