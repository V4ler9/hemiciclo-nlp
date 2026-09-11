# hemiciclo-nlp

Análisis de la evolución temática y tonal del Congreso de los Diputados entre 2015 y 2023, y detección de cambios de régimen asociados a eventos políticos.

## Estado

**Fase 2 completada**: 30.018 intervenciones limpias (≥ 20 palabras, sin notas ni fórmulas de cortesía) en `data/processed/intervenciones_limpias.parquet`, a partir de las 32.739 consolidadas en la Fase 1.

**Fase 3 planificada y documentada**, dividida en 3a (representación, tópicos y sentimiento) y 3b (series, regímenes y eventos). Aún no hay implementación ni análisis publicados. El plan está en [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md) y las decisiones en [`docs/DECISIONS.md`](docs/DECISIONS.md).

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
| 3a | Representación, BERTopic, etiquetado y sentimiento | Planificada |
| 3b | Series mensuales, PELT y eventos | Planificada |
| 4 | Evaluación (coherencia, diversidad, ARI/NMI, F1, Spearman) | Absorbida en 3a y 3b (D-21) |
| 5 | API FastAPI + dashboard Streamlit + Docker local | Pendiente |
| 6 | Pasada final de calidad y reproducibilidad end-to-end | Pendiente |

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

## Datos

El corpus de trabajo es **ParlaMint 5.0 ES** (texto y metadatos) junto con las anotaciones de **ParlaCAP 1.0 ES** (sentimiento ParlaSent y tópico CAP), ambos bajo licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Este repositorio no redistribuye los datos:

```bash
uv run python -m src.corpus.downloader  # descarga y extrae en data/raw/corpus (con verificación MD5)
uv run python -m src.corpus.parser      # consolida data/processed/intervenciones.parquet
uv run python -m src.preprocessing.cleaner  # limpia data/processed/intervenciones_limpias.parquet
```

Todo queda en `data/`, ignorado por git. Las URLs exactas, los MD5 de la release y las fuentes de los modelos están en [`docs/SOURCES.md`](docs/SOURCES.md).

## Licencia

Pendiente de decisión: el repositorio es privado por ahora.
