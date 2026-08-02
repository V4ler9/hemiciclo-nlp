# PROJECT_SPEC — hemiciclo-nlp

## Propósito

Cuantificar el discurso parlamentario del **Congreso de los Diputados de España** frente al tiempo, en dos dimensiones: **temática** (qué se debate) y **emocional** (carga afectiva), y detectar **cambios de régimen discursivo** mediante PELT.

## Fuente de datos

- **Corpus principal:** [ParlaMint-ES](ParlaMint-ES) — XML/TEI con metadatos, marco temporal **2015–2023**.
- **Ubicación:** `data/raw/ParlaMint-ES.tar` (inmutable, no versionado en git).
- **Extensión futura:** scrapping de `congreso.es` para ampliar el marco temporal.

## Modelo de datos (target)

Intervenciones segmentadas por **párrafo** en `data/processed/` (parquet particionado por legislatura/año):

| Campo | Tipo | Notas |
|-------|------|-------|
| `legislatura` | int | |
| `fecha` | date | |
| `orador` | str | normalizado |
| `partido` | str | normalizado |
| `intervencion_id` | str | id en corpus |
| `parrafo_idx` | int | índice dentro de la intervención |
| `texto` | str | texto limpio del párrafo |
| `topic_id` | int | asignado en Fase 3 |
| `topic_label` | str | label humano de tópico (human-in-the-loop) |
| `sentiment_score` | float | polaridad continua (rama fine-tuned) |
| `sentiment_class` | str | {pos, neu, neg} |

`data/intermediate/` guarda embeddings y matrices tópicas; `data/external/` guarda calendarios electorales y metadatos extra.

## Restricciones

- **`data/raw/` es de solo lectura.** Ninguna transformación lo modifica; todo output va a `data/processed/`.
- `data/` está en `.gitignore` (no se versionan crudos ni procesados; opcional vía DVC).
- Todo código Python: **type hints + docstrings + `logging`** (prohibido `print()` en producción).
- Reproducibilidad: `random_seed` global en `configs/default.yaml`, dependencias fijadas en `pyproject.toml`, modelos versionados con sufijo `_vN` en `models/`.

## Pipeline

1. **Corpus** — ParlaMint-ES (decisión cerrada).
2. **Preprocesado** — parseo TEI, filtrado de intervenciones no sustantivas, segmentación por párrafo, parquet particionado.
3. **Procesamiento** — BERTopic (embeddings → UMAP → HDBSCAN → c-TF-IDF), sentimiento Zero-Shot + Fine-Tuned (BETO), agregación temporal, PELT.
4. **Evaluación** — Topic Coherence C_V, Topic Diversity, Macro F1 (sentimiento), Correlación de Spearman (polaridad vs gold).
5. **Servicio** — FastAPI (`/topics`, `/sentiment`, `/regime-change`, `/intervention/{id}`) + Streamlit.
6. **Calidad** — pytest, Docker, CI.

## Criterios de aceptación (Fase 4)

- C_V y Topic Diversity reportados por experimento y comparados entre configs (Optuna).
- Macro F1 del sentimiento fine-tuned ≥ baseline de mayoryía.
- Spearman ρ significativo (p < 0.05) entre polaridad automática y gold humano.
- Puntos de cambio PELT revisados manualmente y documentados.

## Puntos débiles conocidos

- Marco temporal limitado (2015–2023) → scrapping futuro.
- Domain shift sentimiento (corpus social vs parlamentario) → fine-tuning sobre muestra anotada propia.
- Zero-Shot sin gold directo → validación semántica hasta crear gold set.
- PELT sensible al penalty → ajuste elbow/BIC + revisión humana.
