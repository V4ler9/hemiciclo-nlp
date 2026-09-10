# hemiciclo-nlp

Análisis de la evolución temática y tonal del Congreso de los Diputados entre 2015 y 2023, y detección de cambios de régimen asociados a eventos políticos.

## Estado

**Fase 0 completada** (preparación del repo). Aún no hay análisis publicados.

## Objetivo

Responder dos preguntas sobre el corpus [ParlaMint-ES](https://www.clarin.eu/parlamint) (01/01/2015 - 23/02/2023):

1. ¿Cómo evolucionan los temas y el tono de las intervenciones?
2. ¿En qué momentos se detectan cambios de régimen temático o tonal, y cómo se relacionan con eventos como elecciones, investiduras, la COVID-19 o la guerra de Ucrania?

## Hoja de ruta

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Higiene del repo, contrato, entorno y documentación | Completada |
| 1 | Descarga y parseo del corpus ParlaMint 5.0 ES | Pendiente |
| 2 | Preprocesado y limpieza | Pendiente |
| 3 | BERTopic, sentimiento, series mensuales y PELT | Pendiente |
| 4 | Evaluación (coherencia, diversidad, ARI/NMI, F1) y contraste con eventos | Pendiente |
| 5 | API FastAPI + dashboard Streamlit + Docker local | Pendiente |
| 6 | Pasada final de calidad y reproducibilidad end-to-end | Pendiente |

El detalle de cada fase está en [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md).

## Entorno

- Python 3.12 gestionado con [`uv`](https://docs.astral.sh/uv/).
- La instalación básica (`uv sync`) incluye solo el núcleo y las herramientas de desarrollo. Las dependencias pesadas están agrupadas por fase:

```bash
uv sync                 # núcleo + dev (pytest, ruff, pyright, pre-commit)
uv sync --extra corpus  # Fase 1
uv sync --extra nlp     # Fase 3 (recomendado en el dispositivo con NVIDIA)
uv sync --all-extras    # todo
```

- Hooks locales: `uv run pre-commit install` una sola vez.
- Comprobaciones: `uv run pytest`, `uv run pre-commit run --all-files`.
- Las ejecuciones pesadas (embeddings, inferencia, BERTopic) se lanzan en el dispositivo con NVIDIA; el código detecta CUDA en runtime.

## Estructura

La estructura de carpetas es un contrato: [`structure.md`](structure.md). Su modificación requiere confirmación explícita.

Las decisiones técnicas tomadas durante el diseño están registradas en [`docs/DECISIONS.md`](docs/DECISIONS.md).

## Datos

El corpus de trabajo es **ParlaMint 5.0 ES** (CLARIN ERIC), distribuido bajo licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Este repositorio no redistribuye los datos: se descargan con los scripts de `src/corpus/` y quedan en `data/`, ignorados por git.

## Licencia

Pendiente de decisión: el repositorio es privado por ahora.
