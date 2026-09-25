# hemiciclo-nlp

Análisis de la evolución temática y tonal del Congreso de los Diputados entre 2015 y 2023, y detección de cambios de régimen asociados a eventos políticos.

## Estado

**Fase 2 completada**: 30.018 intervenciones limpias (≥ 20 palabras, sin notas ni fórmulas de cortesía) en `data/processed/intervenciones_limpias.parquet`, a partir de las 32.739 consolidadas en la Fase 1.

**Fase 3a completada**: embeddings multilingües del corpus limpio, modelo BERTopic de 58 tópicos elegido por coherencia c_v y diversidad (D-32 y D-34) en `data/processed/intervenciones_topicos.parquet`, etiquetas propuestas en `reports/tables/topics_labels.csv` (pendientes de revisión) y trazabilidad de la rejilla en `reports/tables/topics_selection.csv`. La validación de sentimiento está revisada por el autor y medida contra ParlaSent-ES: 0,675 de accuracy re-ponderada en 3 clases (kappa cuadrática 0,656) y 0,374 en 6 (kappa cuadrática 0,701), con acuerdo a tres bandas en `reports/tables/validacion_sentimiento_acuerdo_3bandas.csv` e informe en `reports/validacion_sentimiento_revision.html` (D-36 y D-37).

**Fase 3b completada**: series mensuales por tópico y tono (`data/intermediate/series_mensuales.parquet`, local), cambios de régimen con PELT y análisis de sensibilidad de la penalización (`reports/tables/cambios_regimen*.csv`), contraste exploratorio con eventos sin asociaciones que superen Benjamini-Hochberg (`reports/tables/eventos_relaciones.csv`) y notebooks de EDA ejecutados en `notebooks/` (D-38). Anexo de sensibilidad de embeddings: bge-m3 con el mismo troceado e hiperparámetros produce 72 tópicos con ARI 0,71 y NMI 0,88 frente a e5 (D-39). Las cinco figuras PNG originales se retiran en D-42: su contenido vive ahora en el panel web.

**Fase 5 completada**: API FastAPI que sirve los artefactos precalculados como JSON (`src/api/main.py`), con `Dockerfile` y `compose.yaml` para ejecución local (D-12 y D-40). El panel de presentación es el de Next.js de `frontend/` (D-42; el dashboard Streamlit original se retiró al validarse el panel).

**Fase 6 completada**: auditoría de reproducibilidad — MD5 del corpus crudo verificado, cadena determinista **byte-idéntica** al re-ejecutarla (18 artefactos vigilados) y suite completa en la máquina NVIDIA (**143 tests**, incluidos `heavy` en GPU e integración con corpus real), más el contrato de estructura verificado en `tests/test_smoke.py` (D-41). Queda como único pendiente la revisión humana de las 58 etiquetas de tópicos. El plan está en [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md) y las decisiones en [`docs/DECISIONS.md`](docs/DECISIONS.md).

**Refactorización del frontend completada** (plan en [`docs/plan_refactor_frontend.md`](docs/plan_refactor_frontend.md), D-42): panel web Next.js 16 + TypeScript en `frontend/` con cuatro secciones —portada con los cambios de tono y la rejilla por tópico, métricas, evidencias por tópico y metodología—, gráficos interactivos en ECharts, nuevo contraste Mann-Whitney con BH por cambio (`reports/tables/cambios_regimen_test.csv`), arranque único `npm run dev:all` desde la raíz y calidad automatizada: 29 tests unitarios (Vitest), 17 E2E (Playwright) y 4 auditorías axe **WCAG2A/AA sin violaciones**. Se retiran el dashboard Streamlit (`app/`), `src/visualization/charts.py` y los cinco PNG de `reports/figures/`, sustituidos por el panel (D-42).

## Objetivo

Responder dos preguntas sobre el corpus [ParlaMint-ES](https://www.clarin.eu/parlamint) (01/01/2015 - 23/02/2023):

1. ¿Cómo evolucionan los temas y el tono de las intervenciones?
2. ¿En qué momentos se detectan cambios de régimen temático o tonal, y cómo se relacionan con eventos como elecciones, investiduras, la COVID-19 o la guerra de Ucrania?

## Hoja de ruta

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Higiene del repo, contrato, entorno y documentación | Completada |
| 1 | Descarga y parseo del corpus ParlaMint 5.0 ES | Completada |
| 2 | Preprocesado y limpieza | Completada |
| 3a | Representación, BERTopic, etiquetado y sentimiento | Completada (etiquetas pendientes) |
| 3b | Series mensuales, PELT y eventos | Completada |
| 4 | Evaluación (coherencia, diversidad, ARI/NMI, F1, Spearman) | Absorbida en 3a y 3b (D-21) |
| 5 | API FastAPI + presentación + Docker local | Completada (presentación en `frontend/`, D-42) |
| 6 | Pasada final de calidad y reproducibilidad end-to-end | Completada |
| — | Refactorización del frontend: panel Next.js + calidad (plan en [`docs/plan_refactor_frontend.md`](docs/plan_refactor_frontend.md)) | Completada |

El detalle de cada fase está en [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md).

## Entorno

- Python 3.12 gestionado con [`uv`](https://docs.astral.sh/uv/).
- La instalación básica (`uv sync`) incluye solo el núcleo y las herramientas de desarrollo. Las dependencias pesadas están agrupadas por fase:

```bash
uv sync                 # núcleo + dev (pytest, ruff, pyright, pre-commit)
uv sync --extra corpus  # Fase 1
uv sync --extra nlp --extra analysis  # Fases 3a y 3b
uv sync --all-extras                  # todo
```

- Hooks locales: `uv run pre-commit install` una sola vez.
- Comprobaciones: `uv run pytest`, `uv run pre-commit run --all-files`.
- Los tests que descargan o ejecutan modelos van marcados `heavy` y se saltan por defecto; solo se ejecutan con `HEMICICLO_HEAVY=1` en una máquina con capacidad suficiente (D-30).
- Las ejecuciones pesadas (embeddings, BERTopic) se lanzan en la máquina NVIDIA, que clona el repositorio, descarga el corpus y ejecuta; git solo transporta código y `reports/` (decisión D-27). El portátil instala igualmente los extras (torch CPU) para que los chequeos estáticos y los tests unitarios funcionen sin descargar modelos.

## Estructura

La estructura de carpetas es un contrato: [`structure.md`](structure.md). Su modificación requiere confirmación explícita.

Las decisiones técnicas tomadas durante el diseño están registradas en [`docs/DECISIONS.md`](docs/DECISIONS.md).

Las fuentes externas (corpus, modelos, software y eventos) y sus comandos de descarga están en [`docs/SOURCES.md`](docs/SOURCES.md).

## Producto local

Requisitos: Python 3.12 con [`uv`](https://docs.astral.sh/uv/) y **Node 20.9+ con npm** (el panel vive en `frontend/`).

### Desarrollo

```bash
npm run dev:all      # desde la raíz: API (:8000) + panel (:3000), un solo comando
```

El panel se abre en <http://localhost:3000>. Comprobaciones automáticas: `uv run pytest` (Python), `npm test` (unitarios Vitest) y `npm run e2e` (Playwright + axe WCAG AA; arranca API y panel solas).

### Docker

`docker compose up --build` levanta la API en <http://localhost:8000> y el panel en <http://localhost:3000>.

## Corpus y origen de los datos

El corpus no está generado por este proyecto: procede de dos recursos externos de investigación sobre el Parlamento español, ambos bajo licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

| Recurso | Identificador | Origen | Uso en el proyecto |
|---|---|---|---|
| **ParlaMint 5.0 ES** (texto y metadatos de las intervenciones del Pleno, 01/01/2015 – 23/02/2023) | handle `11356/2004` | [CLARIN Repository](https://www.clarin.si/repository/xmlui/handle/11356/2004) | Fase 1: descarga, parseo y consolidación |
| **ParlaCAP 1.0 ES** (anotaciones de sentimiento ParlaSent y de tópico CAP sobre el mismo corpus) | DOI `10.23669/1ZTELP` | [DOI](https://doi.org/10.23669/1ZTELP) | Fase 3a: validación de sentimiento y comparación de tópicos |

El proyecto solo **descarga y transforma** esos datos; no los redistribuye. La descarga es reproducible y verificada por MD5 contra los hashes publicados por cada fuente:

```bash
uv run python -m src.corpus.downloader  # descarga y extrae en data/raw/corpus (con verificación MD5)
uv run python -m src.corpus.parser      # consolida data/processed/intervenciones.parquet
uv run python -m src.preprocessing.cleaner  # limpia data/processed/intervenciones_limpias.parquet
```

Todo queda en `data/`, ignorado por git. Las URLs exactas de los ficheros, sus MD5, las fuentes de los modelos y la lista de eventos utilizados están en [`docs/SOURCES.md`](docs/SOURCES.md).

## Generación del código

La gran mayoría del código de este repositorio (módulos Python de `src/`, componentes y lógica de `frontend/`, configuración, tests y documentación) ha sido **generado con asistencia de modelos de lenguaje (LLM)** mediante agentes de IA, siguiendo las indicaciones del autor.

Posteriormente ha habido una **revisión y validación humana**: el autor revisa los resultados, contrasta las decisiones técnicas (registradas en [`docs/DECISIONS.md`](docs/DECISIONS.md)) y verifica el proyecto con tests automatizados, auditorías de accesibilidad y comprobaciones de reproducibilidad (`uv run pytest`, `npm test`, `npm run e2e`, `pre-commit`). Pese a esa revisión, el código puede contener errores; las limitaciones conocidas quedan documentadas en la propia especificación y en el registro de decisiones.

## Licencia

El **código** de este repositorio está bajo [MIT](LICENSE).

Los **datos** no se redistribuyen aquí: ParlaMint-ES 5.0 y ParlaCAP 1.0 ES son obra de sus autores y se utilizan bajo [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); se obtienen de las fuentes enlazadas en «Corpus y origen de los datos» con `uv run python -m src.corpus.downloader`.
