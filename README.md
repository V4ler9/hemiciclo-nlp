# hemiciclo-nlp

Análisis NLP longitudinal del discurso parlamentario del **Congreso de los Diputados de España**: cuantificación temática y de carga emocional frente al tiempo, con detección de puntos de cambio de régimen discursivo.

> Corpus principal: **ParlaMint-ES** (2015–2023). La extensión previa a congreso.es vía scrapping queda fuera del scope inicial, como ampliación de marco temporal a futuro.

---

## 🎯 Objetivo

Cuantificar la evolución del discurso parlamentario español en dos dimensiones:

1. **Temática** — qué se debate y cómo cambian los tópicos a lo largo de la legislatura.
2. **Emocional** — carga afectiva (polaridad/tono) de las intervenciones y su agregación temporal.

Sobre esas dos series se detectan **puntos de cambio estructural** (PELT) que segmentan el parlamento en «regímenes discursivos».

## 🏗️ Stack

- **Lenguaje:** Python 3.11+
- **Datos:** `pandas` / `polars` (si excede RAM) / `pyarrow` (parquet)
- **NLP:** `sentence-transformers` (embeddings multilingües), `bertopic` (UMAP + HDBSCAN + c-TF-IDF), `transformers` + BETO (sentimiento)
- **Detección de cambios:** `ruptures` (PELT)
- **Optimización:** `optuna` (bayesiana sobre hiperparámetros de BERTopic/sentimiento)
- **Servicio:** `fastapi` + `uvicorn`, `streamlit`
- **Calidad:** `pytest`, `ruff`/`mypy`, `pre-commit`
- **Reproducibilidad:** `pyproject.toml` con versiones fijadas, `DVC` opcional para modelos/datos, `random_seed` global, `Dockerfile` + `docker-compose`

## 🗺️ Roadmap

### Fase 1 — Corpus ✅
- [x] Decisión: **ParlaMint-ES** (XML/TEI con metadatos, 2015–2023).
- [ ] *Futuro:* scrapping de congreso.es para ampliar marco temporal.

### Fase 2 — Preprocesado
- [ ] Descomprimir + parsear `.xml`/`.txt` TEI de ParlaMint-ES.
- [ ] Filtrado de intervenciones no sustantivas: fórmulas de apertura/cierre, llamadas de orden, fragmentos cortos sin carga temática (regex + longitud mínima).
- [ ] Segmentación por **intervención × párrafo** (no por discurso) para capturar variabilidad intra-intervención.
- [ ] Normalización de orador, partido, legislatura, fecha.
- [ ] Salida particionada en **parquet** por legislatura/año en `data/processed/`.
- [ ] **No** eliminar stop-words ni lematizar agresivamente (los transformers las aprovechan); solo para modelos baseline/sensibilidad.

### Fase 3 — Procesamiento
- [ ] **Embeddings:** `paraphrase-multilingual-mpnet-base-v2` o BETO sentence.
- [ ] **Topic Modeling (BERTopic):** UMAP (reducción) → HDBSCAN (clustering) → c-TF-IDF (representación). Hiperparámetros (`n_neighbors`, `n_components`, `min_cluster_size`, `min_samples`) optimizados con **Optuna** maximizando `C_V + Topic Diversity`.
- [ ] **Sentimiento — rama A (Zero-Shot):** BETO-NLI / classifier multilingüe zero-shot (sin necesidad de gold). Útil para arranque rápido.
- [ ] **Sentimiento — rama B (Fine-Tuned):** BETO fine-tuned sobre corpus español etiquetado (transfer desde `pysentimiento`/`tweeteval`-es), generando polaridad continua.
- [ ] **Agregación temporal:** frecuencias relativas de tópicos + sentimiento medio por ventana (mensual/trimestral).
- [ ] **Detección de cambios (PELT):** `ruptures` con coste L2/RBF sobre la serie multivariante; `penalty` ajustado por elbow/BIC.

### Fase 4 — Evaluación
- [ ] **Topic Coherence (C_V)** — calidad semántica de los tópicos.
- [ ] **Topic Diversity** — tópicos disjuntos entre sí (top-k palabras).
- [ ] **Macro F1** — modelo de sentimiento fine-tuned vs gold etiquetado.
- [ ] **Correlación de Spearman** — polaridad continua automática vs gold humano.
- [ ] *Opcionales:* estabilidad temporal de tópicos entre ventanas; validación human-in-the-loop sobre muestra de tópicos.

### Fase 5 — Servicio y visualización
- [ ] **FastAPI** endpoints: `/topics`, `/sentiment`, `/regime-change`, `/intervention/{id}`. Modelos serializados en **ONNX** (inferencia reproducible).
- [ ] **Streamlit** dashboard: filtros legislatura/partido/orador, series temporales Plotly, anotación PELT superpuesta.

### Fase 6 — Calidad y despliegue
- [ ] `pytest` con fixtures sintéticos + tests contractuales del endpoint.
- [ ] `Dockerfile` + `docker-compose` (API + dashboard).
- [ ] CI en GitHub Actions (lint, typecheck, tests).
- [ ] `pyproject.toml` deps fijadas; `DVC` opcional para versionar modelos y `data/processed`.

## 📁 Estructura del repositorio

```
data/{raw,processed,intermediate,external}/
notebooks/                # exploración por fases
src/{scraping,preprocessing,nlp,analysis,visualization,utils}/
tests/
configs/                  # default.yaml, experiment_*.yaml
models/                   # topic_model, sentiment (ONNX)
reports/{figures,tables}/
app/                      # FastAPI + Streamlit
```

> **Inmutabilidad:** `data/raw/` es de solo lectura. Toda transformación aterriza en `data/processed/`. `data/` está en `.gitignore`.

## 📊 Técnicas clave

| Fase | Técnica | Referencia |
|------|---------|-----------|
| 3 | BERTopic (UMAP → HDBSCAN → c-TF-IDF) | `bertopic` |
| 3 | Sentimiento Zero-Shot y Fine-Tuned BETO | `transformers` |
| 3 | PELT (cambio de régimen) | `ruptures` |
| 4 | Coherencia C_V, Diversity, F1-Macro, Spearman | `gensim`/`sklearn`/`scipy` |

## ⚙️ Configuración y ejecución (placeholder)

```bash
pip install -e .          # o poetry install
dvc pull                  # datos procesados versionados (opcional)
pytest
uvicorn app.api:app --reload
streamlit run app/dashboard.py
```

## 🔬 Reproducibilidad

- `random_seed` global en `configs/default.yaml` (NumPy, PyTorch, transformers).
- Versiones fijadas en `pyproject.toml`.
- Modelos versionados en `models/` con etiqueta (`_v1`, `_v2`); opcionalmente vía DVC.
- `DECISIONS.md` registra el log de decisiones técnicas.

## ⚠️ Puntos débiles conocidos

- **Marco temporal limitado a 2015–2023** (ParlaMint-ES); se mitiga futuramente con scrapping de congreso.es.
- **Domain shift:** el dominio parlamentario difiere de los datasets de sentimiento en español (tweets, reseñas) → posible transfer domain shift; mitigado con fine-tuning sobre muestra anotada del propio corpus.
- **Zero-Shot sin gold directo** → validación semántica (no cuantitativa) hasta contar con muestra etiquetada.
- **PELT sensible al `penalty`** → ajuste por elbow/BIC y revisión humana de los puntos detectados.

## 📓 Log de decisiones

| Fecha | Decisión |
|-------|----------|
| 2026-08-02 | Corpus principal: **ParlaMint-ES** (2015–2023). Scrapping de congreso.es = extensión futura. |
| 2026-08-02 | Optimización de hiperparámetros con **Optuna** (no GridSearchCV). |
| 2026-08-02 | Modelos de inferencia serializados en **ONNX**. |

## 📜 Licencia

Por definir.
