"""
schedule.py — descarga y cachea el calendario del Mundial 2026 desde football-data.org.

El JSON resultante (data/wc2026_schedule.json) es la fuente de verdad del calendario.
Si la API no está disponible o falla, el pipeline sigue con el JSON de la última
descarga exitosa.

Requiere la variable de entorno FOOTBALL_DATA_API_KEY con la clave gratuita de
https://www.football-data.org  (registro en ~1 minuto, plan gratuito suficiente)
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

_ROOT = Path(__file__).parent.parent
SCHEDULE_PATH = _ROOT / "data" / "wc2026_schedule.json"

_API_BASE = "https://api.football-data.org/v4"
_WC_CODE = "WC"
_TIMEOUT = 30

# football-data.org stage codes → nuestros nombres de fase
_PHASE_MAP: dict[str, str] = {
    "GROUP_STAGE":        "grupos",
    "LAST_32":            "r32",
    "LAST_16":            "octavos",
    "ROUND_OF_16":        "octavos",   # alias alternativo de la API
    "QUARTER_FINALS":     "cuartos",
    "SEMI_FINALS":        "semifinal",
    "THIRD_PLACE":        "tercer_puesto",
    "FINAL":              "final",
}

# Nombres de equipo de la API → nombre canónico del proyecto
# (misma tabla que data.py, ampliada con variantes de football-data.org)
_TEAM_NAME_MAP: dict[str, str] = {
    "United States":                 "USA",
    "USA":                           "USA",
    "Korea Republic":                "South Korea",
    "South Korea":                   "South Korea",
    "Ivory Coast":                   "Côte d'Ivoire",
    "IR Iran":                       "Iran",
    "Türkiye":                       "Turkey",
    "Czech Republic":                "Czechia",
    "Democratic Republic of Congo":  "DR Congo",
    "Congo DR":                      "DR Congo",
    "DR Congo":                      "DR Congo",
    "Bosnia-Herzegovina":            "Bosnia and Herzegovina",
    "Cape Verde Islands":            "Cape Verde",
    "Curacao":                       "Curaçao",
    "Macedonia":                     "North Macedonia",
    "Swaziland":                     "Eswatini",
    "China PR":                      "China",
    "Korea DPR":                     "North Korea",
}


def _canonical(name: str | None) -> str:
    """Normaliza el nombre de equipo; devuelve 'TBD' si es nulo o vacío."""
    if not name or name.strip() in ("", "null"):
        return "TBD"
    name = name.strip()
    return _TEAM_NAME_MAP.get(name, name)


def _make_id(date_iso: str, home: str, away: str) -> str:
    """
    Genera el ID de partido en el mismo formato que freeze.make_match_id:
        YYYY-MM-DD-Home-Away  (espacios → guiones)
    """
    date_part = date_iso[:10]
    h = home.replace(" ", "-")
    a = away.replace(" ", "-")
    return f"{date_part}-{h}-{a}"


def _group_label(raw: str | None) -> str:
    """'GROUP_A' → 'A';  None / '' → ''."""
    if not raw:
        return ""
    return re.sub(r"^GROUP_", "", raw)


def fetch_and_save(api_key: str | None = None) -> bool:
    """
    Descarga el calendario completo del Mundial 2026 desde football-data.org
    y sobreescribe data/wc2026_schedule.json.

    Devuelve True si se actualizó correctamente, False si se mantuvo el caché.
    """
    key = api_key or os.environ.get("FOOTBALL_DATA_API_KEY", "")
    if not key:
        print("  FOOTBALL_DATA_API_KEY no configurada — calendario en caché sin cambios.")
        return False

    try:
        resp = requests.get(
            f"{_API_BASE}/competitions/{_WC_CODE}/matches",
            headers={"X-Auth-Token": key},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  Error al contactar football-data.org: {exc} — calendario en caché sin cambios.")
        return False

    payload = resp.json()
    raw_matches: list[dict] = payload.get("matches", [])
    if not raw_matches:
        print("  La API devolvió 0 partidos — calendario en caché sin cambios.")
        return False

    matches: list[dict] = []
    for m in raw_matches:
        stage  = m.get("stage", "")
        fase   = _PHASE_MAP.get(stage, stage.lower())
        grupo  = _group_label(m.get("group"))
        fecha  = m.get("utcDate", "")

        home_info = m.get("homeTeam") or {}
        away_info = m.get("awayTeam") or {}
        home = _canonical(home_info.get("name") or home_info.get("shortName"))
        away = _canonical(away_info.get("name") or away_info.get("shortName"))

        # Para partidos TBD usamos el ID numérico de la API para evitar duplicados
        if home == "TBD" or away == "TBD":
            mid = f"fd-{m['id']}"
        else:
            mid = _make_id(fecha, home, away)

        entry: dict = {
            "id":         mid,
            "fecha":      fecha,
            "fase":       fase,
            "grupo":      grupo,
            "local":      home,
            "visitante":  away,
        }

        # Incluir resultado si ya se jugó
        ft = (m.get("score") or {}).get("fullTime") or {}
        if ft.get("home") is not None and ft.get("away") is not None:
            entry["goles_local"]      = ft["home"]
            entry["goles_visitante"]  = ft["away"]

        matches.append(entry)

    out = {
        "metadata": {
            "fuente":           "football-data.org",
            "actualizado":      datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_partidos":   len(matches),
        },
        "matches": matches,
    }

    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SCHEDULE_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"  Calendario actualizado: {len(matches)} partidos → {SCHEDULE_PATH.name}")
    return True


if __name__ == "__main__":
    ok = fetch_and_save()
    if not ok and not SCHEDULE_PATH.exists():
        print("No hay calendario en caché y la API falló. Configura FOOTBALL_DATA_API_KEY.")
