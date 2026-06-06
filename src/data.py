"""
data.py — descarga, limpieza y carga del dataset de resultados internacionales.

Fuente histórica: martj42/international_results (~49 000 partidos)
Columnas del DataFrame devuelto:
    date (datetime64), home, away, home_goals (int), away_goals (int),
    tournament (str), neutral (bool)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

_ROOT = Path(__file__).parent.parent
RAW_PATH = _ROOT / "data" / "raw" / "results.csv"

_HISTORICAL_URL = (
    "https://raw.githubusercontent.com/martj42/international_results"
    "/master/results.csv"
)

# Inconsistencias conocidas del dataset → nombre FIFA canónico
_TEAM_NAME_MAP: dict[str, str] = {
    "China PR": "China",
    "IR Iran": "Iran",
    "Korea Republic": "South Korea",
    "Korea DPR": "North Korea",
    "United States": "USA",
    "Ivory Coast": "Côte d'Ivoire",
    "Cape Verde Islands": "Cape Verde",
    "Czech Republic": "Czechia",
    "Macedonia": "North Macedonia",
    "Swaziland": "Eswatini",
    "Türkiye": "Turkey",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "DR Congo",
    "Curacao": "Curaçao",
}


def download_historical(force: bool = False) -> None:
    """Descarga results.csv de martj42/international_results a data/raw/."""
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)

    if RAW_PATH.exists() and not force:
        size_mb = RAW_PATH.stat().st_size / 1_048_576
        print(
            f"Ya existe: {RAW_PATH} ({size_mb:.1f} MB). "
            "Usa --force para re-descargar."
        )
        return

    print("Descargando histórico desde GitHub…")
    response = requests.get(_HISTORICAL_URL, timeout=60, stream=True)
    response.raise_for_status()

    total = 0
    with open(RAW_PATH, "wb") as f:
        for chunk in response.iter_content(chunk_size=65_536):
            f.write(chunk)
            total += len(chunk)

    print(f"Guardado {total / 1_048_576:.1f} MB → {RAW_PATH}")


def load_historical(cutoff_date: str | None = None) -> pd.DataFrame:
    """
    Carga, limpia y devuelve el dataset histórico.

    Parameters
    ----------
    cutoff_date : str o None
        Fecha ISO (ej. '2022-11-20'). Si se proporciona, solo se devuelven
        partidos estrictamente ANTERIORES a esa fecha (anti-leakage).

    Returns
    -------
    DataFrame ordenado por fecha con columnas:
        date, home, away, home_goals, away_goals, tournament, neutral
    """
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"{RAW_PATH} no encontrado. Ejecuta download_historical() primero."
        )

    df = pd.read_csv(RAW_PATH, parse_dates=["date"])

    df = df.rename(columns={
        "home_team": "home",
        "away_team": "away",
        "home_score": "home_goals",
        "away_score": "away_goals",
    })

    # Eliminar filas sin resultado (algunos amistosos antiguos no tienen marcador)
    df = df.dropna(subset=["home_goals", "away_goals"])
    df["home_goals"] = df["home_goals"].astype(int)
    df["away_goals"] = df["away_goals"].astype(int)

    df["home"] = df["home"].str.strip().replace(_TEAM_NAME_MAP)
    df["away"] = df["away"].str.strip().replace(_TEAM_NAME_MAP)
    df["neutral"] = df["neutral"].astype(bool)

    df = df[["date", "home", "away", "home_goals", "away_goals", "tournament", "neutral"]]
    df = df.sort_values("date").reset_index(drop=True)

    if cutoff_date is not None:
        cutoff = pd.Timestamp(cutoff_date)
        df = df[df["date"] < cutoff].reset_index(drop=True)

    return df


def team_list(df: pd.DataFrame | None = None) -> list[str]:
    """Devuelve lista ordenada de todas las selecciones presentes en el dataset."""
    if df is None:
        df = load_historical()
    return sorted(set(df["home"].unique()) | set(df["away"].unique()))


def _print_summary(df: pd.DataFrame) -> None:
    print(f"\n{'='*50}")
    print(f"Partidos:     {len(df):>10,}")
    print(f"Selecciones:  {len(team_list(df)):>10,}")
    print(f"Torneos:      {df['tournament'].nunique():>10,}")
    print(f"Desde:        {df['date'].min().date()!s:>10}")
    print(f"Hasta:        {df['date'].max().date()!s:>10}")
    print(f"{'='*50}")
    print("\nÚltimos 5 partidos:")
    print(df.tail(5).to_string(index=False))


if __name__ == "__main__":
    force = "--force" in sys.argv
    download_historical(force=force)
    df = load_historical()
    _print_summary(df)
