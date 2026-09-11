# Registro de decisiones (DECISIONS)

Cada decisión incluye fecha, contexto y motivo. La especificación completa vive en [`PROJECT_SPEC.md`](PROJECT_SPEC.md).

## 2026-09-10 — Diseño inicial

### D-01 · Cobertura del corpus: 01/01/2015 - 23/02/2023

La nota inicial del vault decía "2015-2022" y el canvas "2015-2023". El README oficial del sample confirma que ParlaMint-ES 5.0 cubre hasta el 23/02/2023. Se adopta la cobertura completa: no cuesta trabajo extra, completa la XIV legislatura y da más serie para PELT. El scraping de congreso.es queda aplazado y fuera de v1.

### D-02 · Unidad de análisis: intervención

El canvas hablaba de párrafos y `structure.md` de intervenciones/sesiones. Se elige la intervención porque es donde se adhieren orador, partido y fecha, imprescindibles para series temporales y metadatos. El párrafo queda como unidad interna de limpieza.

### D-03 · Texto y metadatos de ParlaMint; anotaciones de ParlaCAP

El texto y los metadatos salen de ParlaMint 5.0 plano (TXT/TSV). El sentimiento ParlaSent y el tópico CAP se toman de ParlaCAP 1.0 ES, extensión oficial de ParlaMint 5.0 en formato tabular: mismos discursos, mismos IDs (76.351 de 76.369, 99,98 %) y los mismos modelos, sin necesidad de descargar el corpus anotado completo (1 GB). Revisada el 2026-09-10 tras verificar la release real.

### D-04 · Metadatos conservados

Se conservan los metadatos con valor analítico (fecha, legislatura, subcorpus, rol, partido, gobierno/oposición, género, edad, tipo de intervención) y las anotaciones de ParlaCAP (`topic` y `topic_prob`, `senti_n`, `senti_3`, `senti_6`, `n_words`). Se excluyen los identificativos (nombre, ID) salvo para muestreo y control de calidad.

### D-05 · Objetivo: descripción + cambios de régimen, sin comparación de modelos

Se combinan la caracterización de la evolución temática/tonal y la detección de cambios de régimen ligados a eventos. Se descarta el capítulo de comparación metodológica (zero-shot vs fine-tuned, LDA vs BERTopic).

### D-06 · Tópicos: BERTopic propio con validación externa

BERTopic es el núcleo técnico del plan y aporta granularidad que los 23 tópicos del Comparative Agendas de ParlaMint no tienen. Esos tópicos se usan como validación externa (ARI/NMI) y la granularidad se elige con coherencia y diversidad.

### D-07 · Sentimiento: ParlaSent + validación manual

ParlaSent está entrenado sobre debates parlamentarios (ParlaSent 1.0) y es el mismo modelo que anotó ParlaMint 5.0 y ParlaCAP; afinidad de dominio y comparabilidad garantizadas. ParlaCAP entrega `sent_logit` ya agregado por discurso (media ponderada por longitud, escala 0-6) más las clases de 3 y 6 categorías. Se valida con una muestra estratificada de ~200 intervenciones anotadas a mano (accuracy/F1). Robertuito queda como chequeo de robustez opcional en anexo. Descartado el fine-tuning: no hay etiquetas propias suficientes.

### D-08 · Agregación mensual y PELT

Las frecuencias relativas mensuales absorben el parón estival y la irregularidad del calendario. PELT con coste l2 sobre cuota relativa por tópico y tono medio; la penalización se elige por BIC y se reporta análisis de sensibilidad.

### D-09 · Eventos y Spearman exploratorio

CSV curado a mano en `data/external/eventos.csv`, deliberadamente sencillo de modificar. Spearman se reporta como asociación exploratoria con corrección por comparaciones múltiples y lenguaje no causal.

### D-10 · Stack: uv, Python 3.12, pre-commit local

Se fija `uv` + `pyproject.toml` + `uv.lock`; `requirements.txt` y `setup.py` quedan descartados. Python 3.12. Herramientas: ruff, pyright (estricto), pytest y pre-commit local. Sin CI por ahora (repo privado); se añadirá si el repo se publica.

### D-11 · Hardware: CPU en desarrollo, NVIDIA para ejecuciones pesadas

El portátil no tiene GPU. El dispositivo con NVIDIA está sincronizado por git y se usa para embeddings e inferencia; el código detecta CUDA en runtime. Las dependencias pesadas van en extras (`nlp`, `analysis`) para no instalarlas donde no hacen falta.

### D-12 · Docker local; hosting diferido

La API y el dashboard se ejecutan con Docker Compose en local. El hosting público se decide más adelante, si el proyecto se usa como portfolio.

### D-13 · Versionado: datos y modelos fuera, informes dentro

`data/` y `models/` se ignoran por completo (copyright y tamaño); `reports/figures` y `reports/tables` se versionan por ser el entregable visible. `skills/` (copias locales de OpenCode) también se ignora.

### D-14 · `structure.md` como contrato

La estructura es un contrato: toda modificación se confirma con el usuario antes de aplicarla. `src/corpus/` sustituye al antiguo `src/scrapping/`; se añaden al contrato `src/api/`, `docs/`, `Dockerfile` y `compose.yaml`; se eliminan del árbol los modelos `.pkl` versionados.

### D-15 · Documentación canónica en el repo

`docs/PROJECT_SPEC.md` es el texto canónico; `resumen.canvas` es el mapa visual. Las notas del vault personal (`second-brain`) no se copian al repo: son notas de estudio, no documentación del proyecto. `LICENSE` queda pendiente mientras el repo sea privado.

### D-16 · `src/` como paquete plano

`src/` conserva su `__init__.py` por contrato, aunque no sea el layout más ortodoxo. Refactorizarlo a `src/hemiciclo_nlp/` sería una modificación de contrato y no aporta valor ahora; queda anotado como posible mejora futura.

### D-17 · Commits por fase

Cada fase termina con commit(s) significativos. Los mensajes van en inglés; la documentación, en español.

### D-18 · Hechos del corpus que condicionan el análisis

Verificado sobre la release real: la presidencia supone ~57 % de las intervenciones (43.630 de 76.369) y sus metadatos son UNKNOWN por diseño del corpus original; entre las intervenciones regulares la cobertura de género, partido y fecha de nacimiento es del 100 %. El drop de la presidencia se aplica ya en `build_corpus` (Fase 1), de modo que el corpus consolidado queda en 32.739 intervenciones con metadatos completos.

Concordancia de metadatos verificada el 2026-09-10: excluyendo la presidencia, ParlaMint y ParlaCAP coinciden al **100 %** en fecha, rol (mapeado ES→EN), partido, estatus, género, año de nacimiento y tópico (mapeado ES→EN), con κ = 1,000 sobre 32.721 discursos comparables. Las 18 intervenciones que ParlaCAP no anota son discursos cortos (23-97 palabras).

### D-19 · Limpieza de la Fase 2: notas, fórmulas y umbral

La Fase 2 elimina las notas no verbales (`[[...]]`), los saludos y vocativos de apertura y las fórmulas de cierre, normaliza los espacios y conserva solo las intervenciones con **≥ 20 palabras** tras la limpieza (decisión del 2026-09-10; el percentil 10 del corpus son 29 palabras). Las listas de fórmulas (español, catalán, gallego y euskera) están versionadas en `configs/default.yaml`, no en el código. No hay eliminación de stopwords ni lematización: los embeddings de la Fase 3 las aprovechan.

Resultado sobre el corpus real: 32.739 → **30.018 intervenciones** (2.721 descartadas, 8,3 %), cero notas restantes, `n_words_clean` mínimo 20 y cobertura de ParlaCAP del 100 %. La limpieza es deliberadamente conservadora: no toca usos con contenido como «dar las gracias» ni los vocativos internos.

El filtrado descarta las intervenciones cortas y las reglas de expresiones regulares intentan eliminar las expresiones de cortesía, pero al basarse en regex esta limpieza nunca es perfecta: puede dejar fórmulas residuales o recortar texto legítimo. Limitación asumida a cambio de limpiar la mayoría de los turnos sin intervención manual.

### D-20 · Párrafos del TEI: no se recuperan por ahora

El TXT plano de ParlaMint concatenó los párrafos (`<seg>`) del TEI sin separador y la Fase 1 se construyó desde el TXT. La unidad de análisis es la intervención (D-02) y ningún paso posterior consume párrafos, así que no se añade un parser TEI en v1; `src/preprocessing/segmenter.py` deja utilidades de segmentación. Si la Fase 3 necesita embeddings por tramos para las intervenciones largas, se reevaluará con el TEI que ya está en `data/raw`.

## 2026-09-10 — Planificación de la Fase 3

### D-21 · Fase 3 dividida en 3a y 3b

La Fase 3 se divide en **3a (representación, tópicos y sentimiento)** y **3b (series mensuales, regímenes y eventos)**, cada una con su commit de cierre (extiende D-17). Motivo: 3a concentra las ejecuciones pesadas (embeddings y BERTopic) y 3b el análisis temporal, con dependencias y tiempos distintos.

La «Fase 4: Métricas» del canvas queda absorbida: coherencia, diversidad, ARI/NMI y F1 se calculan en 3a (en `src/nlp/topic_model.py` y `src/nlp/sentiment.py`); Spearman con eventos, en 3b (`src/analysis/regime_change.py`). No se añaden módulos nuevos al contrato para la evaluación.

### D-22 · Enfoque multilingüe: sin traducción ni filtrado

El corpus conserva catalán, gallego y euskera mezclados con español (~1.999 intervenciones, 6,1 % como cota superior). Se decide **no traducir y no filtrar**: filtrar introduciría un sesgo sistemático contra ERC, JxCat, Compromís, PNV, EH Bildu y BNG en un análisis del Congreso, y traducir añadiría ruido de traducción automática y dependencias. Se usan embeddings multilingües (D-24).

Limitaciones asumidas: ParlaSent anota el texto original mezclado, y parte del material no español ya se perdió dentro de notas `[[...]]` eliminadas en la Fase 2 (D-19).

### D-23 · Chunking y embedding a nivel de intervención

Los chunks se construyen con ventanas de tokens: hasta 384 tokens con paso de 320 (solape de 64), usando el tokenizer del modelo de embeddings (no se fuerza la frontera de frase; el solape conserva el contexto entre ventanas). El embedding de la intervención es la media de los embeddings de sus chunks normalizados en L2, renormalizada. La unidad de análisis sigue siendo la intervención (D-02); el chunk existe para no truncar las intervenciones largas (hasta ~17.000 palabras). Parámetros en `configs/experiment_01.yaml`.

### D-24 · Modelos de embeddings: e5-large principal, bge-m3 sensibilidad

`intfloat/multilingual-e5-large` es el modelo principal (1024 dimensiones, 512 tokens, prefijo `passage: `) y `BAAI/bge-m3` el de sensibilidad (`configs/experiment_02.yaml`, 1024 dimensiones, 8192 tokens). La sensibilidad se reporta como anexo de robustez, no como comparación de modelos (D-05). Si el smoke test en la máquina NVIDIA muestra problemas, se revisa antes de fijar la rejilla definitiva. Fuentes y comandos en `SOURCES.md`.

### D-25 · Etiquetado de tópicos: asistente DeepSeek V4.1 Flash con evidencia

El asistente **DeepSeek V4.1 Flash** (según la UI de OpenCode) propone etiqueta y descripción para cada tópico a partir de la evidencia exportada por `topic_model.py`: top-15 términos c-TF-IDF y 8 intervenciones representativas por tópico (`reports/tables/topics_evidence.csv`). El autor revisa y aprueba.

`reports/tables/topics_labels.csv` guarda `label`, `description`, `model`, `prompt_version`, `date` y `reviewed_by`. Las etiquetas son un artefacto de anotación versionado: la exportación de evidencia es determinista, la generación de etiquetas no, así que se documentan modelo y prompt. Fuente del modelo en `SOURCES.md`.

### D-26 · Validación de sentimiento: pre-anotación por LLM y revisión humana

Muestra de ~200 intervenciones estratificada de forma proporcional por clase `senti_3` y legislatura (`term`), con `SEED=42`. El asistente DeepSeek V4.1 Flash hace una pre-anotación y el autor la revisa y corrige; la documentación indicará «pre-anotado por <modelo>, revisado por el autor». Métricas: accuracy y F1 macro con matriz de confusión para 3 y 6 clases.

Archivos versionados en `reports/tables/validacion_sentimiento_*.csv`. Limitación: no es anotación humana ciega ni hay doble anotador, así que no se reporta acuerdo inter-anotador.

### D-27 · Flujo de dispositivos: ejecución en la máquina NVIDIA (opción A)

La máquina NVIDIA clona el repositorio, ejecuta `uv sync --extra corpus --extra nlp --extra analysis`, descarga el corpus y lanza las ejecuciones pesadas. Git transporta código y `reports/` versionados; `data/` y `models/` permanecen locales y se regeneran con comandos y `SEED` (D-13).

El portátil no instala los extras pesados: el código los carga solo al ejecutar (D-30) y los tests unitarios usan dobles. Los tests que requieren modelos reales van marcados `heavy` y se saltan por defecto.

### D-30 · Sin cómputo local: los modelos y sus tests no se ejecutan en el portátil

El portátil no tiene capacidad para descargar y ejecutar los modelos de embeddings ni BERTopic, así que la Fase 3a se implementa con estas reglas:

- Las dependencias pesadas siguen en los extras `nlp`/`analysis` y se cargan en tiempo de ejecución con `import_optional` (`src/utils/helpers.py`); importar `src/nlp/` no exige torch ni transformers.
- Los tests unitarios usan dobles (tokenizadores y codificadores falsos) y se ejecutan en local.
- Los tests que descargan o ejecutan modelos van marcados `heavy` y se saltan salvo que se defina `HEMICICLO_HEAVY=1`.
- La ejecución real y los tests `heavy` se harán en la máquina NVIDIA (D-27) al cerrar la fase.

Consecuencia: los caminos pesados quedan escritos y tipados, pero no verificados por ejecución hasta que se disponga de la máquina; se asume como limitación conocida.

### D-28 · Series mensuales, PELT y eventos: parámetros de partida

- **Cuotas:** cuota del tópico = intervenciones asignadas al tópico / intervenciones asignadas ese mes; los outliers de BERTopic se excluyen y se reporta su tasa.
- **Tono:** media mensual de `senti_n` (simple); la ponderada por `n_words` se reporta como sensibilidad.
- **PELT:** una serie por tópico y una para el tono; coste l2, `min_size=6`, `jump=1`; penalización elegida por criterio tipo BIC (`n·log(RSS/n) + k·log n`) sobre rejilla logarítmica, con análisis de sensibilidad de 5 penalizaciones.
- **Eventos:** ventana de ±3 meses, Spearman + corrección de Benjamini-Hochberg y redacción no causal (D-09).
- **Alcance v1:** series solo agregadas, sin desglose por partido.
- `data/external/eventos.csv` queda fuera de git según D-13; la tabla exacta usada se copia a `reports/tables/eventos.csv` para que el análisis sea reproducible.

### D-29 · Política de fuentes: `docs/SOURCES.md`

Todo recurso externo (corpus, modelos, software, eventos y asistente de etiquetado) se registra en `docs/SOURCES.md` con identificador, origen, fecha y forma de descarga. Cualquier dependencia nueva se añade al documento en el mismo commit en que se incorpora. `docs/SOURCES.md` pasa a formar parte del contrato de estructura.
