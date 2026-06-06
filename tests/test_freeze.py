"""Tests de freeze.py — FreezeManager con datos sintéticos."""
import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from freeze import FreezeManager, make_match_id, _outcome, _score


# ── make_match_id ─────────────────────────────────────────────────────────────

def test_make_match_id_format():
    mid = make_match_id("2026-06-11", "Spain", "Germany")
    assert mid == "2026-06-11-Spain-Germany"


def test_make_match_id_spaces():
    mid = make_match_id("2026-06-11", "South Korea", "Saudi Arabia")
    assert mid == "2026-06-11-South-Korea-Saudi-Arabia"


def test_make_match_id_timestamp():
    mid = make_match_id(pd.Timestamp("2026-06-11"), "Brazil", "France")
    assert mid.startswith("2026-06-11")


# ── _outcome ──────────────────────────────────────────────────────────────────

def test_outcome_local():  assert _outcome(2, 1) == "local"
def test_outcome_visitante(): assert _outcome(0, 1) == "visitante"
def test_outcome_empate(): assert _outcome(1, 1) == "empate"


# ── _score ────────────────────────────────────────────────────────────────────

def test_score_fields():
    pred = {"prob_local": 0.5, "prob_empate": 0.25, "prob_visitante": 0.25}
    result = _score(pred, "local", 2, 0)
    for key in ("ganador", "log_loss", "brier", "acertado", "sorpresa", "resultado"):
        assert key in result


def test_score_correct_acertado():
    pred = {"prob_local": 0.6, "prob_empate": 0.2, "prob_visitante": 0.2}
    assert _score(pred, "local", 2, 0)["acertado"] is True


def test_score_wrong_acertado():
    pred = {"prob_local": 0.6, "prob_empate": 0.2, "prob_visitante": 0.2}
    assert _score(pred, "visitante", 0, 1)["acertado"] is False


def test_score_sorpresa():
    pred = {"prob_local": 0.8, "prob_empate": 0.1, "prob_visitante": 0.1}
    assert _score(pred, "visitante", 0, 1)["sorpresa"] is True


def test_score_no_sorpresa():
    pred = {"prob_local": 0.5, "prob_empate": 0.3, "prob_visitante": 0.2}
    assert _score(pred, "local", 1, 0)["sorpresa"] is False


# ── FreezeManager ─────────────────────────────────────────────────────────────

@pytest.fixture
def live_preds():
    return [
        {
            "id":            "2026-06-11-Spain-Germany",
            "fecha":         "2026-06-11T19:00:00Z",
            "fase":          "grupos",
            "local":         "Spain",
            "visitante":     "Germany",
            "prob_local":    0.41,
            "prob_empate":   0.27,
            "prob_visitante": 0.32,
            "fecha_prediccion": "2026-06-10T08:00:00Z",
        },
        {
            "id":            "2026-06-12-France-Belgium",
            "fecha":         "2026-06-12T19:00:00Z",
            "fase":          "grupos",
            "local":         "France",
            "visitante":     "Belgium",
            "prob_local":    0.52,
            "prob_empate":   0.25,
            "prob_visitante": 0.23,
            "fecha_prediccion": "2026-06-10T08:00:00Z",
        },
    ]


@pytest.fixture
def results_df():
    return pd.DataFrame([{
        "date":        pd.Timestamp("2026-06-11"),
        "home":        "Spain",
        "away":        "Germany",
        "home_goals":  2,
        "away_goals":  1,
        "tournament":  "FIFA World Cup",
        "neutral":     True,
    }])


def test_resolve_splits_correctly(live_preds, results_df):
    with tempfile.TemporaryDirectory() as tmp:
        fm = FreezeManager(tmp)
        resolved, pending = fm.resolve(live_preds, results_df)
    assert len(resolved) == 1
    assert len(pending)  == 1
    assert resolved[0]["local"] == "Spain"
    assert pending[0]["local"]  == "France"


def test_resolve_scores_resolved(live_preds, results_df):
    with tempfile.TemporaryDirectory() as tmp:
        fm = FreezeManager(tmp)
        resolved, _ = fm.resolve(live_preds, results_df)
    r = resolved[0]
    assert r["ganador"] == "local"
    assert r["resultado"] == "2-1"
    assert "log_loss" in r and "brier" in r


def test_append_and_load(live_preds, results_df):
    with tempfile.TemporaryDirectory() as tmp:
        fm = FreezeManager(tmp)
        resolved, _ = fm.resolve(live_preds, results_df)
        fm.append(resolved)
        loaded = fm.load()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "2026-06-11-Spain-Germany"


def test_append_is_additive(live_preds, results_df):
    """Dos llamadas a append acumulan, no sobreescriben."""
    with tempfile.TemporaryDirectory() as tmp:
        fm = FreezeManager(tmp)
        resolved, _ = fm.resolve(live_preds, results_df)
        fm.append(resolved)
        fm.append(resolved)   # segunda vez
        assert len(fm.load()) == 2


def test_write_json_creates_file(live_preds, results_df):
    with tempfile.TemporaryDirectory() as tmp:
        fm = FreezeManager(tmp)
        resolved, _ = fm.resolve(live_preds, results_df)
        fm.append(resolved)
        fm.write_json()
        out = Path(tmp) / "track_record.json"
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["metadata"]["partidos_resueltos"] == 1
        assert data["agregados"] is not None


def test_load_empty_if_no_file():
    with tempfile.TemporaryDirectory() as tmp:
        fm = FreezeManager(tmp)
        assert fm.load() == []
