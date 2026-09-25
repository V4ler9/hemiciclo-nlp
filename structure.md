# Estructura de hemiciclo-nlp

`structure.md` es el **contrato de estructura** del proyecto: define qué carpetas y ficheros existen y para qué sirve cada uno. **Toda modificación de este contrato debe confirmarla el usuario antes de aplicarse.**

## Árbol

```
hemiciclo-nlp/
├── data/                       # Contenido ignorado por git (ver .gitignore)
│   ├── raw/                    # Corpus ParlaMint descargado (TEI, TXT, TSV)
│   ├── processed/              # Intervenciones limpias + metadatos consolidados
│   ├── intermediate/           # Embeddings, matrices de tópicos, series temporales
│   └── external/               # Eventos, calendario electoral, taxonomías auxiliares
│
├── notebooks/                  # EDA (01_... a 03_...)
│
├── src/
│   ├── __init__.py
│   ├── corpus/                 # Fase 1: descarga y parseo del corpus
│   │   ├── __init__.py
│   │   ├── downloader.py       # Descarga ParlaMint-ES 5.0 y ParlaCAP ES (con MD5)
│   │   └── parser.py           # Parseo TXT/TSV (ParlaMint + ParlaCAP) a tabla
│   ├── preprocessing/          # Fase 2: limpieza y segmentación
│   │   ├── __init__.py
│   │   ├── cleaner.py          # Limpieza (frases procedimentales, notas, ruido)
│   │   └── segmenter.py        # Segmentación por intervención y párrafos
│   ├── nlp/                    # Fase 3: modelado
│   │   ├── __init__.py
│   │   ├── topic_model.py      # BERTopic
│   │   ├── sentiment.py        # ParlaSent y validación
│   │   └── embeddings.py       # Generación de embeddings
│   ├── analysis/               # Fases 3-4: análisis temporal y evaluación
│   │   ├── __init__.py
│   │   ├── temporal.py         # Agregación mensual y tendencias
│   │   └── regime_change.py    # PELT y cambios de régimen
│   ├── api/                    # Fase 5: servicio FastAPI
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── openapi.py          # Vuelca reports/openapi.json (tipos TS del frontend)
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuración, paths y SEED
│   │   └── helpers.py          # Funciones auxiliares
│
├── tests/
│   ├── __init__.py
│   ├── fixtures/               # Mini-corpus sintético para los tests
│   │   ├── parlamint_es_mini/
│   │   └── parlacap_es_mini/
│   ├── test_corpus.py
│   ├── test_preprocessing.py
│   ├── test_nlp.py
│   ├── test_analysis.py
│   ├── test_api.py
│   └── test_smoke.py
│
├── configs/
│   ├── default.yaml            # Configuración por defecto
│   ├── experiment_01.yaml
│   ├── experiment_02.yaml
│   └── experiment_03.yaml      # Fase 3b: series, regímenes y eventos
│
├── models/                     # Modelos serializados. Contenido ignorado por git
│
├── reports/
│   ├── tables/                 # Tablas de resultados (versionadas)
│   └── openapi.json            # Esquema de la API para `npm run gen:api` (versionado)
│
├── frontend/                   # Next.js 16 + TS: panel web editorial (D-42; retira app/ y charts.py)
│   ├── src/
│   │   ├── app/                # App Router: layout, navegación y páginas por sección
│   │   ├── components/         # UI shadcn y componentes de presentación
│   │   └── lib/                # Capa de datos (api.ts), tipos OpenAPI y lógica pura con tests unitarios (Vitest)
│   ├── e2e/                    # Tests E2E de Playwright: 4 secciones + auditoría axe WCAG2A/AA
│   ├── scripts/                # sync-informes.mjs: copia el informe HTML a public/informes/
│   ├── public/                 # favicon e informe de validación servido (copia de reports/, regenerada en dev/build)
│   ├── Dockerfile              # Build multi-stage del panel (contexto en la raíz, D-42)
│   ├── AGENTS.md               # Directrices del subproyecto frontend
│   ├── CLAUDE.md               # Alias → AGENTS.md (lo reescribe `next dev`)
│   ├── package.json            # Scripts: dev, dev:all, gen:api, lint, format, test, e2e, sync:informes
│   ├── components.json         # Configuración de shadcn/ui
│   ├── eslint.config.mjs       # Reglas ESLint (flat config)
│   ├── next.config.ts          # Configuración de Next.js
│   ├── postcss.config.mjs      # PostCSS (Tailwind)
│   ├── .prettierrc / .prettierignore  # Formato del código TS/TSX
│   ├── vitest.config.mts       # Configuración de tests unitarios
│   ├── playwright.config.ts    # Configuración E2E (arranca API + web solas)
│   └── tsconfig.json           # TypeScript estricto (strict + noUncheckedIndexedAccess)
│
├── docs/
│   ├── PROJECT_SPEC.md         # Especificación canónica del proyecto
│   ├── DECISIONS.md            # Registro de decisiones técnicas
│   ├── plan_refactor_frontend.md  # Plan de la refactorización del frontend
│   └── SOURCES.md              # Fuentes externas y descargas reproducibles
│
├── Dockerfile                  # Fase 5: imagen de la API (el panel usa frontend/Dockerfile)
├── compose.yaml                # Fase 5: ejecución local
├── package.json                # Scripts npm delegados en frontend/ (dev, dev:all, build, lint, format, gen:api)
├── .dockerignore               # Excluye del contexto de build lo que no necesita Docker
├── .gitignore
├── .gitattributes              # Finales de línea normalizados a LF
├── .pre-commit-config.yaml
├── pyproject.toml              # Dependencias y herramientas (uv)
├── uv.lock
├── README.md
├── structure.md                # Este contrato
├── AGENTS.md
└── LICENSE                     # MIT (código); los datos son CC BY 4.0 de sus autores
```

## Reglas

1. El contenido de `data/` y `models/` no se versiona jamás; solo se conserva la carpeta con `.gitkeep`.
2. `reports/tables` sí se versiona: es el entregable visible (`reports/figures` se retiró en D-42).
3. `src/` es un paquete plano (`src/__init__.py`); se mantiene así por contrato.
4. Los notebooks son solo para EDA y figuras; la lógica reproducible vive en `src/`.
5. `src/corpus/` sustituye al antiguo `src/scrapping/`; el scraping de congreso.es queda aplazado y fuera de v1.
6. `requirements.txt` y `setup.py` quedan descartados: el entorno es `pyproject.toml` + `uv.lock`.
