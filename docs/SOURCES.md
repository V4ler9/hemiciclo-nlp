# Fuentes externas (SOURCES)

Registro único de los recursos externos del proyecto: corpus, modelos, software, eventos y asistente de etiquetado. Cada entrada incluye el identificador exacto, el origen y la forma de reproducir su descarga.

> Política: cualquier recurso externo nuevo se registra aquí en el mismo commit en el que se incorpora al proyecto (D-29).

## 1. Corpus

| Recurso | Identificador | Origen | Uso en el proyecto |
|---|---|---|---|
| ParlaMint 5.0 ES (plano) | handle `11356/2004` | <https://www.clarin.si/repository/xmlui/handle/11356/2004> | Texto y metadatos (Fase 1) |
| ParlaCAP 1.0 ES | DOI `10.23669/1ZTELP` | <https://doi.org/10.23669/1ZTELP> | Sentimiento ParlaSent y tópico CAP |
| ParlaSent 1.0 | handle `11356/1868` | <http://hdl.handle.net/11356/1868> | Origen de las anotaciones de sentimiento; no se descarga en el pipeline |

Descarga verificada por MD5 en [`src/corpus/downloader.py`](../src/corpus/downloader.py):

| Archivo | URL exacta | MD5 |
|---|---|---|
| `ParlaMint-ES.tgz` | `https://www.clarin.si/repository/xmlui/bitstream/handle/11356/2004/ParlaMint-ES.tgz?sequence=8&isAllowed=y` | `2ba1216f3fcf1300ee74f50efe42ec6a` |
| `ParlaCAP-ES_speeches_no_text.tsv.zip` | `https://data.crossda.hr/api/access/datafile/540` | `c7706d1f45f238b7bfdde6a503ee8d49` |

Licencia de ambos corpus: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). El repositorio no redistribuye los datos.

```bash
uv run python -m src.corpus.downloader
uv run python -m src.corpus.parser
```

## 2. Modelos

### Embeddings

| Rol | Modelo | Dimensiones | Contexto máximo | Origen |
|---|---|---|---|---|
| Principal (`configs/experiment_01.yaml`) | `intfloat/multilingual-e5-large` | 1024 | 512 tokens | <https://huggingface.co/intfloat/multilingual-e5-large> |
| Sensibilidad (`configs/experiment_02.yaml`) | `BAAI/bge-m3` | 1024 | 8192 tokens | <https://huggingface.co/BAAI/bge-m3> |

- `multilingual-e5-large` espera el prefijo `passage: ` en los documentos que se indexan (y `query: ` en consultas; aquí solo se indexa).
- `bge-m3` no necesita prefijo.
- La descarga es automática desde HuggingFace la primera vez que se ejecutan los embeddings, con caché en `~/.cache/huggingface`. Para precargarlos en la máquina NVIDIA:

```bash
uv run huggingface-cli download intfloat/multilingual-e5-large
uv run huggingface-cli download BAAI/bge-m3
```

### Asistente de etiquetado y pre-anotación

- Identificador declarado: **DeepSeek V4.1 Flash** (según la UI de OpenCode, sesión del 2026-09-10).
- Pesos y despliegue: organización [`deepseek-ai`](https://huggingface.co/deepseek-ai) en HuggingFace (releases `DeepSeek-V4.1-Flash` / `DeepSeek-V4-Flash-0731`); disponible también en [NVIDIA NIM](https://build.nvidia.com/deepseek-ai/deepseek-v4-flash), [DeepInfra](https://deepinfra.com/deepseek-ai/DeepSeek-V4.1-Flash) y Azure AI Foundry.
- Uso en el proyecto: etiquetado de tópicos (D-25) y pre-anotación de la muestra de validación de sentimiento (D-26), siempre con revisión del autor.
- Trazabilidad: `reports/tables/topics_labels.csv` y `reports/tables/validacion_sentimiento_*.csv` guardan `model`, `prompt_version`, `date` y `reviewed_by`.
- Reproducibilidad: por su tamaño (cientos de miles de millones de parámetros) no se descarga localmente; los proveedores pueden actualizar el modelo, así que se versionan las salidas y los prompts, no la inferencia.

## 3. Software

La lista exacta y las versiones están en [`pyproject.toml`](../pyproject.toml) y [`uv.lock`](../uv.lock). Grupos relevantes:

- Núcleo y calidad: `numpy`, `pandas`, `pyyaml`; `pytest`, `ruff`, `pyright`, `pre-commit`.
- Extra `corpus` (Fase 1): `requests`, `lxml`, `pyarrow`.
- Extra `nlp` (Fase 3a): `bertopic`, `sentence-transformers`, `torch`, `scikit-learn` (ARI/NMI) y `gensim` (coherencia c_v, D-32). `py3langid` queda pendiente para la caracterización lingüística.
- Extra `analysis` (Fase 3b): `ruptures`, `scipy`, `matplotlib`, `seaborn`.
- Extra `app` (Fase 5): `fastapi`, `uvicorn`, `streamlit`, `plotly`.
- **Nota Windows/NVIDIA:** la rueda `torch` que publica PyPI para Windows es solo CPU, así que las ejecuciones con GPU requieren instalar la rueda CUDA del índice oficial de PyTorch (D-31). Comando en la sección 5.

## 4. Eventos

`data/external/eventos.csv` se redactará en la Fase 3b con la lista definitiva de eventos, sus fechas y su fuente. Esta tabla replica las fuentes candidatas; la versión exacta usada se guardará además en `reports/tables/eventos.csv` porque `data/` no se versiona (D-13).

| Evento | Fecha | Fuente candidata |
|---|---|---|
| Elecciones generales 20-D | 2015-12-20 | Resultados oficiales: [Ministerio del Interior](https://infoelectoral.interior.gob.es/) |
| Elecciones generales 26-J | 2016-06-26 | Resultados oficiales: [Ministerio del Interior](https://infoelectoral.interior.gob.es/) |
| Moción de censura de 2018 | 2018-06-01 | [Congreso de los Diputados](https://www.congreso.es/) (expediente de la moción) |
| Elecciones generales 28-A | 2019-04-28 | Resultados oficiales: [Ministerio del Interior](https://infoelectoral.interior.gob.es/) |
| Elecciones generales 10-N | 2019-11-10 | Resultados oficiales: [Ministerio del Interior](https://infoelectoral.interior.gob.es/) |
| Investidura de 2020 | 2020-01-05 / 2020-01-07 | [Congreso de los Diputados](https://www.congreso.es/) (debate de investidura) |
| COVID-19: estado de alarma | 2020-03-14 | [BOE-A-2020-3692](https://www.boe.es/buscar/doc.php?id=BOE-A-2020-3692); [OMS](https://www.who.int/emergencies/diseases/novel-coronavirus-2019) |
| Guerra de Ucrania | 2022-02-24 | [ONU](https://news.un.org/en/focus/ukraine); [Consejo Europeo](https://www.consilium.europa.eu/en/policies/eu-response-ukraine-invasion/) |

Las fechas se verificarán contra el expediente o la publicación oficial correspondiente al construir `eventos.csv` en 3b.

## 5. Reproducción por fase

```bash
uv sync --extra corpus --extra nlp --extra analysis

# Máquina NVIDIA en Windows: habilitar CUDA antes de las ejecuciones pesadas (D-31)
uv pip install "torch==2.14.0+cu130" --index-url https://download.pytorch.org/whl/cu130

# Fase 1
uv run python -m src.corpus.downloader
uv run python -m src.corpus.parser

# Fase 2
uv run python -m src.preprocessing.cleaner

# Fase 3a (pendiente de implementación)
# uv run python -m src.nlp.embeddings
# uv run python -m src.nlp.topic_model

# Fase 3b (pendiente de implementación)
# uv run python -m src.analysis.temporal
# uv run python -m src.analysis.regime_change
```

## 6. Registro de cambios

| Fecha | Cambio |
|---|---|
| 2026-09-10 | Creación: corpus, modelos de embeddings, asistente de etiquetado, software, eventos candidatos y comandos de reproducción. |
| 2026-09-13 | Nota Windows/NVIDIA: instalación de la rueda CUDA de `torch` desde el índice de PyTorch (D-31) y comando en la reproducción por fase. |
