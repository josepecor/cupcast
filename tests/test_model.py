"""Tests de model.py — Dixon-Coles con datos sintéticos."""
import pytest
import numpy as np
import pandas as pd
from model import DixonColesModel


@pytest.fixture
def training_df():
    """DataFrame con datos suficientes para que DC converja (>5 partidos por equipo)."""
    rng = np.random.default_rng(42)
    teams = ["Brazil", "Argentina", "France", "Germany", "Spain", "England"]
    rows = []
    base = pd.Timestamp("2020-01-01")
    for i, h in enumerate(teams):
        for j, a in enumerate(teams):
            if h == a:
                continue
            for k in range(3):
                rows.append({
                    "date":        base + pd.Timedelta(days=i * 30 + j * 5 + k),
                    "home":        h,
                    "away":        a,
                    "home_goals":  int(rng.poisson(1.5)),
                    "away_goals":  int(rng.poisson(1.1)),
                    "tournament":  "Friendly",
                    "neutral":     False,
                })
    return pd.DataFrame(rows)


def test_fit_runs(training_df):
    dc = DixonColesModel()
    dc.fit(training_df, reference_date="2023-01-01")
    assert dc._fitted


def test_predict_proba_sums_to_one(training_df):
    dc = DixonColesModel()
    dc.fit(training_df, reference_date="2023-01-01")
    p = dc.predict_proba("Brazil", "France", neutral=True)
    assert p["prob_home"] + p["prob_draw"] + p["prob_away"] == pytest.approx(1.0, abs=1e-4)


def test_predict_proba_keys(training_df):
    dc = DixonColesModel()
    dc.fit(training_df, reference_date="2023-01-01")
    p = dc.predict_proba("Brazil", "France", neutral=True)
    for key in ("prob_home", "prob_draw", "prob_away", "lambda_home", "lambda_away", "most_likely_score"):
        assert key in p


def test_score_matrix_shape(training_df):
    dc = DixonColesModel()
    dc.fit(training_df, reference_date="2023-01-01")
    M = dc.score_matrix("Brazil", "France", neutral=True)
    assert M.shape == (11, 11)
    assert M.sum() == pytest.approx(1.0, abs=1e-3)


def test_score_matrix_sums_to_one(training_df):
    dc = DixonColesModel()
    dc.fit(training_df, reference_date="2023-01-01")
    M = dc.score_matrix("Brazil", "France", neutral=True)
    assert M.sum() == pytest.approx(1.0, abs=1e-3)


def test_score_matrix_diagonal_is_draws(training_df):
    dc = DixonColesModel()
    dc.fit(training_df, reference_date="2023-01-01")
    p = dc.predict_proba("Brazil", "France", neutral=True)
    M = dc.score_matrix("Brazil", "France", neutral=True)
    assert np.trace(M) == pytest.approx(p["prob_draw"], abs=0.02)


def test_home_advantage(training_df):
    dc = DixonColesModel()
    dc.fit(training_df, reference_date="2023-01-01")
    p_home    = dc.predict_proba("Brazil", "France", neutral=False)
    p_neutral = dc.predict_proba("Brazil", "France", neutral=True)
    assert p_home["prob_home"] > p_neutral["prob_home"]


def test_antileakage(training_df):
    # training_df tiene partidos hasta ~2020-06-27; cutoff intermedio = 2020-03-01
    dc_early = DixonColesModel()
    dc_early.fit(training_df, reference_date="2020-03-01")

    dc_full = DixonColesModel()
    dc_full.fit(training_df, reference_date="2021-01-01")

    p_early = dc_early.predict_proba("Brazil", "France", neutral=True)
    p_full  = dc_full.predict_proba("Brazil", "France", neutral=True)
    assert p_early["prob_home"] != p_full["prob_home"]


def test_predict_before_fit():
    dc = DixonColesModel()
    with pytest.raises(RuntimeError):
        dc.predict_proba("A", "B", neutral=True)


def test_strength_table(training_df):
    dc = DixonColesModel()
    dc.fit(training_df, reference_date="2023-01-01")
    table = dc.strength_table()
    assert "attack" in table.columns
    assert "defense" in table.columns
    assert len(table) > 0
