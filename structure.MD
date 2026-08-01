hemiciclo-nlp/
├── data/
│   ├── raw/                    # HTMLs o descargas crudas de los diarios
│   ├── processed/              # Textos limpios, segmentados por intervención
│   ├── intermediate/           # Features, embeddings, topic matrices
│   └── external/               # Calendarios electorales, eventos, metadatos
│
├── notebooks/
│   ├── 01_scraping_exploration.ipynb
│   ├── 02_preprocessing.ipynb
│   ├── 03_topic_modeling.ipynb
│   ├── 04_sentiment_analysis.ipynb
│   ├── 05_temporal_aggregation.ipynb
│   └── 06_visualization.ipynb
│
├── src/
│   ├── __init__.py
│   ├── scraping/
│   │   ├── __init__.py
│   │   ├── downloader.py       # Lógica de descarga de diarios
│   │   └── parser.py           # Parseo de HTML a texto estructurado
│   │
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── cleaner.py          # Limpieza de texto
│   │   └── segmenter.py        # Segmentación por intervención/sesión
│   │
│   ├── nlp/
│   │   ├── __init__.py
│   │   ├── topic_model.py      # LDA, BERTopic, etc.
│   │   ├── sentiment.py        # Modelos de sentimiento/tono
│   │   └── embeddings.py       # Generación de embeddings
│   │
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── temporal.py         # Agregación temporal, tendencias
│   │   └── regime_change.py    # Detección de cambios de régimen
│   │
│   ├── visualization/
│   │   ├── __init__.py
│   │   ├── charts.py           # Gráficos principales
│   │   └── dashboard.py        # Dashboard interactivo (Streamlit, etc.)
│   │
│   └── utils/
│       ├── __init__.py
│       ├── config.py           # Configuración, paths, constantes
│       └── helpers.py          # Funciones auxiliares
│
├── tests/
│   ├── __init__.py
│   ├── test_scraping.py
│   ├── test_preprocessing.py
│   ├── test_nlp.py
│   └── test_analysis.py
│
├── configs/
│   ├── default.yaml            # Configuración por defecto
│   ├── experiment_01.yaml      # Configuraciones específicas
│   └── experiment_02.yaml
│
├── models/
│   ├── topic_model_v1.pkl
│   ├── sentiment_model_v1.pkl
│   └── embeddings_v1.pkl
│
├── reports/
│   ├── figures/                # Gráficos generados
│   └── tables/                 # Tablas de resultados
│
├── app/
│   ├── app.py                  # Aplicación Streamlit o similar
│   └── components/             # Componentes de la UI
│
├── .gitignore
├── requirements.txt
├── setup.py o pyproject.toml
├── README.md
├── PROJECT_SPEC.md             # Especificación del proyecto
├── DECISIONS.md                # Decisiones técnicas
├── AGENTS.md                   # Documentación para agentes de código
└── LICENSE