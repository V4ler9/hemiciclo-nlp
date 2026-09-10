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

Verificado sobre la release real: la presidencia supone ~57 % de las intervenciones (43.630 de 76.369) y sus metadatos son UNKNOWN por diseño del corpus original; entre las intervenciones regulares la cobertura de género, partido y fecha de nacimiento es del 100 %. La Fase 2 excluye los turnos de presidencia, de modo que el análisis trabajará sobre ~32.500 intervenciones con metadatos completos.
