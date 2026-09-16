# Especificación del proyecto: hemiciclo-nlp

Documento canónico del proyecto. El canvas [`resumen.canvas`](resumen.canvas) es el mapa visual del plan; en caso de conflicto, manda este documento.

- **Tipo:** investigación personal.
- **Última actualización:** 2026-09-10.

## 1. Pregunta de investigación

Sobre las intervenciones del Pleno del Congreso de los Diputados entre el 01/01/2015 y el 23/02/2023:

1. ¿Cómo evolucionan los temas y el tono del discurso?
2. ¿En qué momentos se detectan cambios de régimen temático o tonal, y cómo se relacionan con eventos políticos (elecciones, investiduras, moción de censura, COVID-19, guerra de Ucrania)?

Queda **fuera de alcance** un capítulo de comparación metodológica entre modelos.

## 2. Corpus

| Aspecto | Decisión |
|---|---|
| Fuente | ParlaMint 5.0 ES (texto y metadatos) + ParlaCAP 1.0 ES (sentimiento ParlaSent y tópico CAP) |
| Cobertura | 01/01/2015 - 23/02/2023 (X-XIV legislaturas) |
| Cámara | Congreso de los Diputados (no Senado) |
| Licencia | CC BY 4.0; atribución obligatoria |
| Formatos | ParlaMint: TXT (intervención por línea) y TSV de metadatos por componente; ParlaCAP: TSV por discurso |
| Versiones | ParlaMint plano (11356/2004) + ParlaCAP (10.23669/1ZTELP) |
| Scraping | Aplazado: congreso.es queda fuera de v1 |

Notas verificadas sobre el corpus: la presidencia (metadatos UNKNOWN por diseño del corpus original) supone ~57 % de las intervenciones y se excluye en la consolidación; el corpus resultante tiene 32.739 intervenciones, de las que 32.721 (99,94 %) tienen sentimiento y tópico de ParlaCAP. Las 18 restantes son discursos cortos. La concordancia entre los metadatos de ParlaMint y ParlaCAP es del 100 % en los campos comparables (fecha, rol, partido, estatus, género, año de nacimiento y tópico).

El corpus es multilingüe en la práctica: unas 1.999 intervenciones (6,1 % como cota superior) contienen catalán, gallego o euskera, a menudo mezclados con español dentro de la misma intervención. Se conservan sin traducir ni filtrar y se modelan con embeddings multilingües (D-22).

### Unidad de análisis

La **intervención** (`<u>`), que es donde se adhieren orador, partido y fecha. El párrafo es solo una unidad interna de limpieza. El sentimiento llega ya agregado a nivel de discurso por ParlaCAP (media ponderada por longitud, escala 0-6) y el tópico es la categoría CAP con su probabilidad.

### Metadatos

Se conservan: `Date` (agregada a mes), `Term`, `Subcorpus` (reference/covid/war), `Speaker_role`, `Speaker_party`, `Speaker_party_name`, `Party_status` (gobierno/oposición), `Speaker_gender`, `Speaker_birth` (edad), `Speaker_minister`, `Session`, `topic` y `topic_prob` (categoría CAP de ParlaCAP y su probabilidad), `senti_n`, `senti_3`, `senti_6`, `n_words` y `n_words_clean` (palabras tras la limpieza).

Se excluyen: `Speaker_name`, `Speaker_ID` (solo muestreo y control de calidad), `Title`, `Body`, `Sitting`, `Lang` y `Speaker_MP` (redundante con el rol).

## 3. Pipeline

1. **Corpus:** descarga de ParlaMint 5.0 plano y de ParlaCAP ES, consolidación en una tabla de intervenciones (excluida la presidencia) con metadatos, tópico CAP y sentimiento ParlaSent (`data/processed/intervenciones.parquet`).
2. **Preprocesado:** eliminación de las notas no verbales (`[[...]]`) y de las fórmulas de saludo, vocativo y despedida; normalización de espacios y filtro de longitud (≥ 20 palabras tras limpiar). El filtro descarta las intervenciones cortas y las reglas de expresiones regulares intentan eliminar las expresiones de cortesía, pero al basarse en regex esta limpieza nunca es perfecta. Reglas versionadas en `configs/default.yaml`; salida en `data/processed/intervenciones_limpias.parquet`. Los turnos de presidencia ya se excluyeron en la Fase 1 y los párrafos del TEI no se recuperan (D-20).
3. **Fase 3a · Representación, tópicos y sentimiento (completada; ver D-35):**
   - **Texto:** ventanas de hasta 384 tokens con paso de 320 (solape de 64) sobre el texto limpio; enfoque multilingüe, sin traducir ni filtrar (D-22, D-23).
   - **Embeddings:** `intfloat/multilingual-e5-large` como principal y `BAAI/bge-m3` como sensibilidad; embedding de intervención por media de chunks normalizados (D-23, D-24).
   - **Tópicos:** BERTopic propio (UMAP → HDBSCAN → c-TF-IDF) con rejilla de hiperparámetros; granularidad elegida por coherencia c_v y diversidad; outliers excluidos de las cuotas reportando su tasa.
   - **Etiquetado:** propuesta automática a partir de la evidencia (términos c-TF-IDF e intervenciones representativas) con revisión del autor y trazabilidad del modelo (D-25).
   - **Sentimiento:** ParlaSent (3 y 6 clases); validación sobre ~200 intervenciones con pre-anotación por LLM y revisión humana (D-26). Robertuito solo como chequeo opcional en anexo.
   - **Evaluación de modelo:** coherencia y diversidad; ARI/NMI contra los 23 tópicos de ParlaMint. La lógica vive en `src/nlp/`.
4. **Fase 3b · Series, regímenes y eventos (planificada):**
   - **Series temporales:** agregación mensual de cuota relativa por tópico y tono medio (con sensibilidad ponderada por longitud).
   - **Cambios de régimen:** PELT sobre las series mensuales (coste l2; penalización por criterio tipo BIC y análisis de sensibilidad).
   - **Eventos:** Spearman exploratorio con `data/external/eventos.csv` (ventana ±3 meses), corrección por comparaciones múltiples (Benjamini-Hochberg) y redacción no causal; figuras y tablas en `reports/`.
5. **Producto:** API FastAPI (JSON precalculado) + dashboard Streamlit + Docker local.
6. **Cierre:** tests end-to-end, pre-commit y reproducibilidad documentada.

La «Fase 4: Métricas» del canvas queda absorbida por 3a (coherencia, diversidad, ARI/NMI, F1) y 3b (Spearman), según D-21.

### Artefactos

| Artefacto | Fase | Productor | Consumidor |
|---|---|---|---|
| `data/processed/intervenciones.parquet` | 1 | `src/corpus/parser.py` | Fase 2 |
| `data/processed/intervenciones_limpias.parquet` | 2 | `src/preprocessing/cleaner.py` | Fase 3a |
| `data/intermediate/chunks.parquet` | 3a | `src/nlp/embeddings.py` | embeddings y control de calidad |
| `data/intermediate/embeddings.parquet` | 3a | `src/nlp/embeddings.py` | BERTopic |
| `data/processed/intervenciones_topicos.parquet` | 3a | `src/nlp/topic_model.py` | Fase 3b y dashboard |
| `models/` (modelo BERTopic) | 3a | `src/nlp/topic_model.py` | reutilización y dashboard; no versionado |
| `reports/tables/topics_evidence.csv` | 3a | `src/nlp/topic_model.py` | etiquetado (D-25) |
| `reports/tables/topics_selection.csv` | 3a | `src/nlp/topic_model.py` | trazabilidad de la rejilla y la selección (D-32) |
| `reports/tables/topics_labels.csv` | 3a | etiquetado asistido con revisión | figuras y dashboard |
| `reports/tables/validacion_sentimiento_*.csv` | 3a | `src/nlp/sentiment.py` | métricas de sentimiento |
| `reports/validacion_sentimiento_revision.html` | 3a | `src/nlp/sentiment.py` | informe HTML de la revisión humana (D-37) |
| `data/intermediate/series_mensuales.parquet` | 3b | `src/analysis/temporal.py` | PELT y figuras |
| `reports/tables/cambios_regimen.csv` | 3b | `src/analysis/regime_change.py` | figuras y memoria |
| `reports/tables/cambios_regimen_sensibilidad.csv` | 3b | `src/analysis/regime_change.py` | robustez de la penalización de PELT (D-08) |
| `reports/tables/eventos.csv` | 3b | espejo versionado de `data/external/eventos.csv` | trazabilidad del contraste |
| `reports/figures/*` | 3b | `src/visualization/charts.py` | entregable visible |

## 4. Eventos externos

CSV editable a mano en `data/external/eventos.csv` (diseño deliberadamente sencillo para poder modificarlo después): elecciones de 2015, 2016 y 2019 (abril y noviembre), moción de censura de 2018, investidura de 2020, COVID-19 (2020-03) y guerra de Ucrania (2022-02), con fuente citada.

## 5. Reproducibilidad

- Semilla global `SEED = 42` en `src/utils/config.py`.
- Entorno `uv` + `pyproject.toml` + `uv.lock`; Python 3.12.
- Configuración en `configs/*.yaml`; nada de constantes mágicas en el código.
- Desarrollo en CPU; ejecuciones pesadas en la máquina con NVIDIA (D-27): clona el repositorio, descarga el corpus y ejecuta; git solo transporta código y `reports/`.
- Fuentes externas, modelos y comandos de descarga: [`SOURCES.md`](SOURCES.md).
- Los modelos pesados se cargan en tiempo de ejecución y sus tests van marcados `heavy`, saltados por defecto hasta disponer de cómputo (D-30).
- Un commit al cerrar cada fase (3a y 3b incluidas, D-21).

## 6. Gobernanza

- `structure.md` es el contrato de estructura; toda modificación requiere confirmación del usuario.
- `docs/DECISIONS.md` registra las decisiones y su porqué.
- Documentación en español; identificadores y mensajes de commit en inglés.

## 7. Referencias

- Fuentes de corpus, modelos, software y eventos: [`SOURCES.md`](SOURCES.md).
- ParlaMint 5.0, corpus plano: <http://hdl.handle.net/11356/2004>
- ParlaCAP 1.0, anotaciones (sentimiento y tópico): <https://doi.org/10.23669/1ZTELP>
- ParlaSent 1.0: <http://hdl.handle.net/11356/1868>
- Documentación de la iniciativa: <https://clarin-eric.github.io/ParlaMint/>
