# hemiciclo-nlp

Análisis de la evolución temática y tonal del Congreso de los Diputados entre 2015 y 2023, y detección de cambios de régimen asociados a eventos políticos.

## Objetivo

Responder dos preguntas sobre el corpus [ParlaMint-ES](https://www.clarin.eu/parlamint) (01/01/2015 - 23/02/2023):

1. ¿Cómo evolucionan los temas y el tono de las intervenciones?
2. ¿En qué momentos se detectan cambios de régimen temático o tonal, y cómo se relacionan con eventos como elecciones, investiduras, la COVID-19 o la guerra de Ucrania?

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

La especificación completa del proyecto, fase por fase, está en [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md).

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
