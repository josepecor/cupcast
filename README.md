# CupCast — Predictor probabilístico · Mundial 2026

Modelo estadístico de fútbol aplicado al **Mundial 2026** (48 equipos, 104 partidos).  
Genera probabilidades de victoria partido a partido, simula el cuadro completo por Monte Carlo y lleva un **track record** honesto comparando cada predicción congelada contra el resultado real.

🌐 **[cupcast en vivo →](https://josepecor.github.io/cupcast)**

---

## Cómo funciona

### Modelo principal — Dixon-Coles ("Forma reciente")
Poisson bivariada con corrección para resultados bajos (0-0, 1-0, 0-1, 1-1) y **decaimiento temporal** (ξ = 0.003, half-life ~8 meses). Entrena con los ~49.000 partidos internacionales del dataset `martj42/international_results` (1872–hoy), ponderando más los recientes. Estima fuerza de ataque y defensa por selección y ventaja de local.

Cada partido se pondera adicionalmente por la calidad del rival: `(elo_medio_partido / elo_medio_global)^0.5`. Así un resultado contra Argentina cuenta más que uno contra un equipo débil, sin depender de categorías arbitrarias de torneo.

### Baseline — Elo ("Historial y reputación")
Ratings Elo adaptados al fútbol (K escalado por torneo y diferencia de goles). Captura el historial acumulado de cada selección a lo largo de los años. Sirve como segunda perspectiva en la UI y como referencia para evaluar si Dixon-Coles aporta valor añadido.

### Simulación — Monte Carlo
10.000 simulaciones del cuadro completo respetando el formato 2026 (12 grupos × 4 → R32 → octavos → ...). Resultado: probabilidad de campeón y de alcanzar cada ronda para los 48 equipos.

### UI — dos perspectivas por partido
Cada tarjeta de partido muestra las dos predicciones en paralelo con sus barras de probabilidad (local / empate / visitante) y una nota generada automáticamente que explica si los modelos coinciden o discrepan, en lenguaje no técnico.

### Track record honesto
Antes de cada partido se congela la predicción. Al conocerse el resultado se puntúa con **log-loss** y **Brier score** y se archiva. La predicción congelada nunca se recalcula.

---

## Validación histórica (backtest WC 2010–2022)

| Torneo | DC log-loss | Elo log-loss | DC Brier | Elo Brier |
|---|---|---|---|---|
| WC 2010 | **0.933** | 0.989 | **0.549** | 0.580 |
| WC 2014 | **0.934** | 0.959 | **0.554** | 0.563 |
| WC 2018 | **0.978** | 0.997 | **0.579** | 0.589 |
| WC 2022 | 1.078 | **1.031** | 0.622 | **0.612** |
| **Global** | **0.981** | 0.994 | **0.576** | 0.586 |

Dixon-Coles supera al Elo en 3 de 4 torneos y en el global. WC 2022 es el único outlier (probable sesgo de Argentina/Brasil en qualifiers CONMEBOL). Los modelos se entrenaron estrictamente con datos anteriores a cada torneo (anti-leakage por fecha exacta).

---

## Ejecución local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Descargar datos históricos (~3.6 MB)
python src/data.py

# Pipeline completo (descarga → reentrenar → predecir → escribir JSONs)
python src/pipeline.py

# Simular con menos iteraciones (más rápido para desarrollo)
python src/pipeline.py --n-simulations 1000

# Solo regenerar backtest
python src/pipeline.py --backtest-only

# Tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Servir la web en local (necesario para que fetch() funcione)
cd docs && python3 -m http.server 8080
```

---

## Arquitectura

```
src/
├── data.py       # Descarga y limpieza del histórico (martj42); anti-leakage por fecha
├── schedule.py   # Descarga el calendario WC 2026 desde football-data.org
├── model.py      # Dixon-Coles: ajuste y predicción partido a partido
├── elo.py        # Baseline Elo adaptado al fútbol
├── evaluate.py   # Log-loss, Brier score, calibración
├── simulate.py   # Monte Carlo del cuadro completo (formato WC 2026)
├── freeze.py     # Predicciones congeladas y track record append-only
└── pipeline.py   # Orquestador: backtest o ciclo diario completo

data/
├── wc2026_groups.json    # Grupos oficiales FIFA 2026
└── wc2026_schedule.json  # 104 partidos (72 grupos + 32 eliminatorias); incluye resultados cuando están disponibles

docs/                     # Raíz de GitHub Pages
├── index.html / app.js / styles.css
├── predictions.json      # Predicciones actuales (regenerado a diario)
├── track_record.jsonl    # Log append-only de predicciones resueltas (fuente de verdad)
├── track_record.json     # Track record agregado para el frontend (generado desde el JSONL)
└── backtest.json         # Validación histórica (estático)
```

El flujo de datos es estrictamente unidireccional:  
`data.py + schedule.py → model.py / elo.py → simulate.py → freeze.py → pipeline.py → docs/`

---

## Actualización automática

GitHub Actions ejecuta el pipeline diariamente a las **9:00 UTC** (después de que `martj42/international_results` actualiza sus resultados, entre las 05:00–08:30 UTC). Los JSONs actualizados se despliegan automáticamente en GitHub Pages.

CI corre en cada push: tests, lint y regeneración del backtest para verificar reproducibilidad.

---

## Fuentes

- Datos históricos (entrenamiento): [martj42/international_results](https://github.com/martj42/international_results) — ~49.000 partidos internacionales, actualizado diariamente
- Calendario en vivo (fixtures + resultados WC 2026): [football-data.org](https://www.football-data.org) — plan gratuito, vía `src/schedule.py`
- Banderas: [Flagpedia / flagcdn.com](https://flagpedia.net)
