# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/

# Run a single test
pytest tests/test_model.py::test_name -v

# Run the full pipeline (download → retrain → predict → write JSONs)
python src/pipeline.py

# Regenerate backtest only
python src/pipeline.py --backtest-only

# Lint
ruff check src/ tests/
```

---

## Architecture overview

The project has three runtime modes sharing the same `src/` modules:

1. **Backtest** — trains on historical data strictly before each past World Cup, evaluates on that tournament, writes `docs/backtest.json`. Run once; result is static.
2. **Daily live update** — triggered by GitHub Actions: downloads new results, scores frozen predictions, retrains, predicts upcoming matches, writes `docs/predictions.json` + `docs/track_record.json`.
3. **Monte Carlo simulation** — called inside the daily update; simulates the full bracket 10k–100k times to produce champion probabilities.

The data flow is strictly one-directional: `data.py` → `model.py` / `elo.py` → `evaluate.py` / `simulate.py` → `freeze.py` → `pipeline.py` writes JSON → `docs/` is served by GitHub Pages.

**Critical invariant — anti-leakage:** `model.py` and `elo.py` must only ever train on matches with `date < prediction_cutoff_date`. Filter by exact date, never by year. Any match from the tournament being predicted leaking into training inflates results.

**Critical invariant — frozen predictions:** `freeze.py` maintains an append-only log. Once a prediction is written for a match, it is never recalculated, even after the result is known. `pipeline.py` step 2 (resolve predictions) must run before step 4 (retrain) to preserve this.

The `docs/` folder is the GitHub Pages root. `index.html` fetches the three JSON files at the same origin (`./predictions.json` etc.) — no CORS issues. The pipeline writes JSON directly into `docs/`; Actions deploys Pages automatically.

---

# World Cup Predictor — Brief de proyecto

> Documento de especificación para continuar el desarrollo en Claude Code.
> Recoge todas las decisiones de diseño ya tomadas. Léelo entero antes de empezar a programar.

---

## 1. Objetivo

Modelo predictivo de partidos de fútbol aplicado al **Mundial 2026**, con tres capas:

1. **Backtesting histórico** — validar el modelo contra Mundiales pasados. Es *la prueba* de que el método funciona, y genera resultados sólidos que no dependen de cómo salga 2026.
2. **Predicción en vivo de 2026** — predecir los partidos pendientes del torneo, actualizándose a diario. Es *la demo* atractiva.
3. **Track record en vivo** — marcador que compara cada predicción (congelada antes del partido) contra el resultado real, mostrando cómo de bien/mal lo hace el modelo según avanza el torneo.

La salida final se sirve como **web estática en GitHub Pages** que consume ficheros JSON. El usuario final solo ve la web; nunca toca el código ni los datos crudos.

---

## 2. Decisiones de diseño (el "por qué", no negociar sin motivo)

- **Entrenar con TODOS los partidos internacionales, no solo Mundiales.** Solo hay ~900 partidos de Mundial en toda la historia y la mayoría son irrelevantes hoy. El dataset internacional completo tiene ~49.000 partidos (amistosos, clasificatorias, Eurocopa, Copa América, Nations League, etc.). Ahí está la señal real.
- **Decaimiento temporal (time decay).** No se corta el histórico por años; se usa casi todo, pero ponderando: un partido reciente pesa mucho más que uno de hace años. Captura la forma actual sin tirar información.
- **Modelo núcleo: Dixon-Coles** (Poisson bivariada con corrección para resultados bajos como 0-0 y 1-1, más time decay). Modela fuerza de ataque/defensa por selección y ventaja de local. De ahí salen probabilidades de victoria/empate/derrota y marcadores.
- **Baseline obligatorio.** Un Elo adaptado al fútbol y/o el ranking FIFA (o, si se consigue, las cuotas de casas de apuestas) como referencia contra la que comparar. El titular del proyecto es: ¿bate mi modelo al baseline?
- **Anti-leakage estricto.** Entrenar SIEMPRE solo con partidos **estrictamente anteriores** a la fecha del torneo/partido que se predice. Filtrar por **fecha exacta**, nunca por año (un partido del propio torneo colándose en el entrenamiento infla los resultados de forma tramposa).
- **Predicción del torneo = simulación Monte Carlo** del cuadro completo (10.000–100.000 simulaciones) usando las probabilidades partido a partido. Da probabilidad de campeón y de alcanzar cada ronda.
- **Formato 2026: 48 equipos, ~104 partidos** (12 grupos de 4 → ronda de 32 → octavos → ...). La capa de simulación NO es year-agnostic: necesita configuración del formato por edición. El modelo a nivel de partido sí es universal.
- **Actualización diaria, no en tiempo real.** No hace falta refresco por-partido al minuto: basta con tener los resultados de la jornada anterior antes de la siguiente. Una pasada diaria lo cubre.
- **Guard de completitud.** Antes de predecir la siguiente fase, verificar que todos los partidos de la fase actual tienen resultado. Si falta alguno, NO sobrescribir nada; salir y reintentar. Mejor datos viejos correctos que un cuadro mal montado.
- **Track record con predicción congelada.** Antes de que se juegue un partido se guarda una foto fija de la predicción. Al resolverse, se compara contra el resultado y se puntúa. JAMÁS se regenera la predicción de un partido ya jugado.

---

## 3. Métricas y criterio de honestidad

- Métricas de evaluación: **log-loss** (castiga la confianza equivocada), **Brier score** (error cuadrático sobre probabilidades, más intuitivo) y **calibración** (¿de los partidos a los que di 60%, ganó ~60%?).
- Se calculan también para el baseline y se comparan. Modelo mejor que baseline = valor demostrado.
- **Juzgar el "error" por la puntuación probabilística, no por "ganó el favorito".** Que no gane el favorito no es un fallo: si le diste 40%, perder el 60% de las veces es lo esperado. Las sorpresas en fútbol son normales y un buen modelo les asigna probabilidad real.
- Se puede mostrar un *hit-rate* (% de veces que el resultado más probable ocurrió) por ser intuitivo, pero dejando claro que la métrica seria es la probabilística.
- **Una sola edición es muestra pequeña y ruidosa** (~100 partidos). El track record en vivo es la capa atractiva, pero el grueso de la evidencia es el backtest histórico. No sobreinterpretar una buena/mala racha.

---

## 4. Fuentes de datos

- **Histórico (entrenamiento):** dataset `martj42/international_results` (GitHub/Kaggle, ~49.000 partidos). OJO: se mantiene **a mano**, no se actualiza solo ni partido a partido. Perfecto para la base histórica; se descarga una vez y se refresca de vez en cuando.
- **En vivo 2026 (resultados nuevos):** preferible una **API de resultados** (p. ej. football-data.org, plan gratuito — *verificar cobertura del Mundial y límites de rate antes de comprometerse*) porque da el resultado a los minutos del pitido final. Alternativa: el dataset de Kaggle "International Football Results: Daily Updates", que se refresca automáticamente a diario.
- Separar claramente lo estable (histórico) de lo vivo (API). No depender de que una persona actualice un CSV justo cuando se necesita: ese sería el punto frágil del proyecto.

---

## 5. Estructura de carpetas

```
worldcup-predictor/
├── README.md
├── requirements.txt
├── CLAUDE.md                 # este documento
├── data/
│   ├── raw/                  # CSV descargado de partidos internacionales
│   └── processed/            # datos limpios / con features
├── src/
│   ├── data.py               # descarga + limpieza + carga histórica y en vivo
│   ├── model.py              # Dixon-Coles: ajustar y predecir (núcleo)
│   ├── elo.py                # baseline Elo (también usable como feature)
│   ├── simulate.py           # Monte Carlo del cuadro del torneo
│   ├── evaluate.py           # log-loss, Brier, calibración, comparación vs baseline
│   ├── freeze.py             # congelar predicciones y puntuarlas al resolverse (track record)
│   └── pipeline.py           # orquesta todo de principio a fin
├── outputs/
│   └── figures/              # gráficas generadas (calibración, etc.)
├── docs/                     # <- raíz de GitHub Pages
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   ├── predictions.json      # lo que viene (regenerado a diario)
│   ├── backtest.json         # validación histórica (estático)
│   └── track_record.json     # predicciones resueltas de 2026 + agregados
├── tests/
│   └── test_model.py
└── .github/workflows/
    ├── update.yml            # programada: descarga, reentrena, predice, despliega
    └── ci.yml                # tests + regenera backtest en cada push
```

Nota Pages: en los ajustes del repo apuntar Pages a la carpeta `/docs`. Todo lo que haya ahí se sirve como web. Por eso el pipeline escribe (o copia) los JSON dentro de `docs/`, junto al `index.html`. La página hace `fetch('./predictions.json')` (mismo origen, sin CORS).

---

## 6. Responsabilidades por módulo

- **data.py** — descargar el histórico, limpiarlo y normalizar nombres de equipos; cargar resultados en vivo desde la API/dataset diario; exponer un dataframe unificado de partidos con fecha, equipos, goles, torneo, sede.
- **model.py** — ajuste del Dixon-Coles con time decay; dado un conjunto de partidos de entrenamiento (filtrados por fecha), devuelve para un partido futuro las probabilidades 1/X/2, la matriz de marcadores y los goles esperados.
- **elo.py** — ratings Elo adaptados a fútbol; baseline y feature.
- **simulate.py** — dado el cuadro y las probabilidades partido a partido, simula el torneo N veces respetando el formato de la edición (config por edición); devuelve probabilidad de campeón y de alcanzar cada ronda.
- **evaluate.py** — log-loss, Brier, curva de calibración; comparación contra baseline; usado tanto por el backtest como por el track record.
- **freeze.py** — gestión del log append-only de predicciones: congelar antes del partido, detectar partidos ya resueltos, puntuarlos, actualizar agregados. Nunca regenera predicciones resueltas.
- **pipeline.py** — orquestador (ver flujo abajo).

---

## 7. Flujo del pipeline (orden exacto, end-to-end)

`pipeline.py` ejecuta, en este orden:

1. **Descargar** resultados nuevos (API/dataset en vivo) y refrescar el histórico si toca.
2. **Resolver predicciones**: los partidos que estaban "por jugar" y ahora tienen resultado se mueven al track record; se calcula su puntuación (Brier/log-loss del partido) y se **congelan**. No se recalculan sus probabilidades.
3. **Guard de completitud**: si se va a predecir una nueva fase, comprobar que la fase anterior está completa. Si no, salir sin sobrescribir.
4. **Reentrenar** Dixon-Coles (y Elo) con todos los datos disponibles hasta la fecha, con time decay y filtro anti-leakage por fecha.
5. **Predecir**: probabilidades de los partidos pendientes + Monte Carlo para probabilidades de campeón/rondas.
6. **Escribir** `predictions.json` y `track_record.json` (y, en su momento, `backtest.json`) dentro de `docs/`, más las figuras en `outputs/figures/`.
7. El **despliegue** lo hace la Action (Pages se refresca solo).

---

## 8. Esquemas JSON

### `predictions.json` (lo que viene, diario)
```json
{
  "metadata": {
    "torneo": "FIFA World Cup 2026",
    "generado": "2026-06-15T08:00:00Z",
    "entrenado_hasta": "2026-06-14",
    "fase_actual": "grupos",
    "modelo": "dixon-coles-v1"
  },
  "favoritos": [
    { "equipo": "Brasil", "prob_campeon": 0.184 },
    { "equipo": "Francia", "prob_campeon": 0.142 }
  ],
  "proximos_partidos": [
    {
      "id": "2026-06-16-ESP-GER",
      "fecha": "2026-06-16T19:00:00Z",
      "fase": "grupos",
      "local": "España",
      "visitante": "Alemania",
      "prob_local": 0.41,
      "prob_empate": 0.27,
      "prob_visitante": 0.32,
      "marcador_probable": "1-1"
    }
  ]
}
```

### `backtest.json` (validación histórica, estático)
```json
{
  "metadata": { "generado": "2026-05-01T00:00:00Z", "modelo": "dixon-coles-v1" },
  "por_torneo": [
    { "torneo": "World Cup 2022", "n_partidos": 64, "log_loss": 1.01, "brier": 0.63, "baseline_log_loss": 1.08 },
    { "torneo": "World Cup 2018", "n_partidos": 64, "log_loss": 1.03, "brier": 0.64, "baseline_log_loss": 1.10 }
  ],
  "global": { "log_loss": 1.03, "brier": 0.64, "baseline_log_loss": 1.09 },
  "calibracion": [
    { "bucket": "0.0-0.1", "predicho": 0.05, "observado": 0.04, "n": 120 }
  ]
}
```

### `track_record.json` (2026 en vivo, predicciones resueltas)
```json
{
  "metadata": { "torneo": "FIFA World Cup 2026", "actualizado": "2026-06-20T08:00:00Z", "partidos_resueltos": 12 },
  "agregados": {
    "log_loss": 0.98,
    "brier": 0.62,
    "hit_rate": 0.58,
    "baseline_log_loss": 1.05
  },
  "calibracion": [
    { "bucket": "0.0-0.1", "predicho": 0.05, "observado": 0.04, "n": 8 }
  ],
  "partidos": [
    {
      "id": "2026-06-16-ESP-GER",
      "fecha_prediccion": "2026-06-15T08:00:00Z",
      "local": "España",
      "visitante": "Alemania",
      "prob_local": 0.41,
      "prob_empate": 0.27,
      "prob_visitante": 0.32,
      "resultado": "2-1",
      "ganador": "local",
      "brier": 0.34,
      "log_loss": 0.89,
      "sorpresa": false
    }
  ]
}
```

---

## 9. Web (docs/)

HTML + JS vanilla (sin framework necesario). Hace `fetch` relativo de los tres JSON y renderiza:

- **Favoritos / campeón** — tabla con probabilidades de ganar el torneo (titular).
- **Próximos partidos** — predicciones 1/X/2 de los partidos pendientes.
- **Track record** — marcador acumulado (log-loss/Brier vs baseline), curva de calibración que se rellena jornada a jornada, y tabla partido a partido con los **mayores fallos resaltados** (la sección más compartible).
- **Backtest** — resumen de la validación histórica para dar credibilidad.

Mostrar siempre "datos hasta X" / "actualizado el Y" para que la frescura sea visible.

---

## 10. GitHub Actions

- **update.yml** — programada. Diaria como base; **subir frecuencia (cada pocas horas) los días de transición de fase**, que es cuando el retraso del origen de datos puede dejarte sin los resultados a tiempo. Ejecuta `pipeline.py`, deja los JSON en `docs/`, despliega Pages.
- **ci.yml** — en cada push: corre los tests y regenera `backtest.json` + figuras, demostrando que el pipeline es reproducible.

**Gotcha importante:** el `schedule` (cron) de Actions es *best-effort*, no puntual: puede retrasarse con carga alta, y los workflows programados se **desactivan solos tras ~60 días de inactividad** del repo. Por eso: frecuencia alta + guard de completitud (sección 7, paso 3) en lugar de depender de un único disparo diario clavado a una hora.

---

## 11. Stack sugerido

- **Python**: `pandas`, `numpy`, `scipy` (optimización para el ajuste Dixon-Coles; `statsmodels` opcional), `matplotlib` para figuras, `requests` para la API, `pytest` para tests.
- **Frontend**: HTML/CSS/JS vanilla. Streamlit es un extra opcional posterior que reutilizaría los mismos JSON, sin rehacer nada.
- Sin deep learning: no hay datos suficientes y no aporta frente a Dixon-Coles para este problema.

---

## 12. Orden de construcción recomendado

1. `requirements.txt` + scaffold de carpetas.
2. `data.py`: descarga y limpieza del histórico; tenerlo cargado y validado primero.
3. `model.py`: Dixon-Coles con time decay; verificar en unos pocos partidos conocidos.
4. `elo.py`: baseline.
5. `evaluate.py`: métricas + calibración.
6. **Backtest** sobre Mundiales pasados → `backtest.json`. (Hito clave: resultados reales que prueban el método.)
7. `simulate.py`: Monte Carlo del cuadro (con config de formato 2026).
8. `freeze.py` + integración del track record.
9. `pipeline.py`: unir todo en el flujo de la sección 7.
10. `docs/` (web estática) consumiendo los JSON.
11. Workflows de Actions.
12. README con la narrativa y un par de gráficas buenas.
