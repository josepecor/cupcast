"""Tests de evaluate.py — métricas puras, sin modelo."""
import math
import pytest
from evaluate import log_loss, brier_score, hit_rate, calibration_curve, evaluate


def _probs(ph, pd, pa):
    return {"prob_home": ph, "prob_draw": pd, "prob_away": pa}


# ── log_loss ──────────────────────────────────────────────────────────────────

def test_log_loss_perfect():
    probs = [_probs(1.0, 0.0, 0.0)]
    assert log_loss(probs, ["home"]) == pytest.approx(0.0, abs=1e-6)


def test_log_loss_uniform():
    probs = [_probs(1/3, 1/3, 1/3)] * 9
    outcomes = ["home"] * 3 + ["draw"] * 3 + ["away"] * 3
    assert log_loss(probs, outcomes) == pytest.approx(math.log(3), rel=1e-4)


def test_log_loss_order():
    # Modelo más confiado en lo correcto → menor log-loss
    good = [_probs(0.8, 0.1, 0.1)]
    bad  = [_probs(0.4, 0.3, 0.3)]
    assert log_loss(good, ["home"]) < log_loss(bad, ["home"])


# ── brier_score ───────────────────────────────────────────────────────────────

def test_brier_perfect():
    probs = [_probs(1.0, 0.0, 0.0)]
    assert brier_score(probs, ["home"]) == pytest.approx(0.0, abs=1e-6)


def test_brier_worst():
    # Certeza total en el resultado incorrecto → brier = 2.0
    probs = [_probs(0.0, 0.0, 1.0)]
    assert brier_score(probs, ["home"]) == pytest.approx(2.0, abs=1e-6)


def test_brier_uniform():
    probs = [_probs(1/3, 1/3, 1/3)]
    # (1/3-1)^2 + (1/3)^2 + (1/3)^2 = 4/9 + 1/9 + 1/9 = 6/9 = 2/3
    assert brier_score(probs, ["home"]) == pytest.approx(2/3, rel=1e-4)


# ── hit_rate ──────────────────────────────────────────────────────────────────

def test_hit_rate_all_correct():
    probs = [_probs(0.6, 0.2, 0.2), _probs(0.2, 0.6, 0.2)]
    assert hit_rate(probs, ["home", "draw"]) == pytest.approx(1.0)


def test_hit_rate_none_correct():
    probs = [_probs(0.6, 0.2, 0.2)]
    assert hit_rate(probs, ["away"]) == pytest.approx(0.0)


# ── calibration_curve ─────────────────────────────────────────────────────────

def test_calibration_curve_returns_list():
    probs = [_probs(0.6, 0.2, 0.2)] * 10
    result = calibration_curve(probs, ["home"] * 5 + ["away"] * 5, n_buckets=5)
    assert isinstance(result, list)
    assert all("bucket" in b and "predicho" in b and "observado" in b and "n" in b for b in result)


def test_calibration_curve_no_empty_buckets():
    probs = [_probs(0.5, 0.25, 0.25)]
    result = calibration_curve(probs, ["home"], n_buckets=10)
    assert all(b["n"] > 0 for b in result)


# ── evaluate ──────────────────────────────────────────────────────────────────

def test_evaluate_keys():
    probs = [_probs(0.5, 0.25, 0.25)] * 4
    result = evaluate(probs, ["home", "draw", "away", "home"])
    for key in ("n_partidos", "log_loss", "brier", "hit_rate", "calibracion"):
        assert key in result


def test_evaluate_baseline():
    probs    = [_probs(0.5, 0.25, 0.25)] * 4
    baseline = [_probs(1/3, 1/3, 1/3)]   * 4
    result = evaluate(probs, ["home"] * 4, baseline_probs=baseline)
    assert "baseline_log_loss" in result
    assert "baseline_brier"    in result
    assert result["log_loss"] < result["baseline_log_loss"]


def test_evaluate_n_partidos():
    probs = [_probs(0.5, 0.25, 0.25)] * 7
    assert evaluate(probs, ["home"] * 7)["n_partidos"] == 7
