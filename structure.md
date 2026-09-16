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
├── notebooks/                  # EDA y generación de figuras (01_... a 06_...)
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
│   ├── visualization/
│   │   ├── __init__.py
│   │   ├── charts.py           # Figuras y tablas
│   │   └── dashboard.py        # Utilidades de la UI
│   ├── api/                    # Fase 5: servicio FastAPI
│   │   ├── __init__.py
│   │   └── main.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuración, paths y SEED
│   │   └── helpers.py          # Funciones auxiliares
│
├── tests/
│   ├── __init__.py
│   ├── fixtures/               # Mini-corpus sintético para los tests
│   │   └── parlamint_es_mini/
│   ├── test_corpus.py
│   ├── test_preprocessing.py
│   ├── test_nlp.py
│   └── test_analysis.py
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
│   ├── figures/                # Figuras finales (versionadas)
│   └── tables/                 # Tablas de resultados (versionadas)
│
├── app/
│   ├── app.py                  # UI Streamlit (consume la API)
│   └── components/             # Componentes de la UI
│
├── docs/
│   ├── resumen.canvas          # Mapa visual del plan (Obsidian Canvas)
│   ├── PROJECT_SPEC.md         # Especificación canónica del proyecto
│   ├── DECISIONS.md            # Registro de decisiones técnicas
│   └── SOURCES.md              # Fuentes externas y descargas reproducibles
│
├── Dockerfile                  # Fase 5: imagen de API/dashboard
├── compose.yaml                # Fase 5: ejecución local
├── .gitignore
├── .pre-commit-config.yaml
├── pyproject.toml              # Dependencias y herramientas (uv)
├── uv.lock
├── README.md
├── structure.md                # Este contrato
├── AGENTS.md
└── LICENSE                     # Pendiente: se decidirá si el repo se publica
```

## Reglas

1. El contenido de `data/` y `models/` no se versiona jamás; solo se conserva la carpeta con `.gitkeep`.
2. `reports/figures` y `reports/tables` sí se versionan: son el entregable visible.
3. `src/` es un paquete plano (`src/__init__.py`); se mantiene así por contrato.
4. Los notebooks son solo para EDA y figuras; la lógica reproducible vive en `src/`.
5. `src/corpus/` sustituye al antiguo `src/scrapping/`; el scraping de congreso.es queda aplazado y fuera de v1.
6. `requirements.txt` y `setup.py` quedan descartados: el entorno es `pyproject.toml` + `uv.lock`.
