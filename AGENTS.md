# AGENTS.md - Directrices de Desarrollo y Ciencia de Datos

Este repositorio sigue estándares estrictos de reproducibilidad, rigor estadístico y buenas prácticas de ingeniería de software para Ciencia de Datos y Machine Learning.

---

## 1. Stack Tecnológico y Entorno

- **Python Runtime:** 3.12 (fijado en `pyproject.toml` y gestionado con `uv`).
- **Gestión de paquetes y entorno:** `uv` con `pyproject.toml` + `uv.lock`.
- **Linter & Formatter:** `ruff` (reemplaza `flake8`, `black`, `isort`).
- **Type Checking:** `pyright` en modo estricto para módulos core.
- **Testing:** `pytest` con tests unitarios y de validación de datos (`pandera` / `great_expectations`).
- **Calidad:** `pre-commit` local (ruff, pyright y pytest); sin CI por ahora.
- **Hardware:** desarrollo en CPU; las ejecuciones pesadas corren en un dispositivo con NVIDIA (CUDA) sincronizado por git.

---

## 2. Rigor en Datos y Modelado (No Negociable)

### Fugas de Información (Data Leakage)
- **Separación estricta:** Todo preprocesamiento, escalado, imputación y codificación (`Pipeline`, `ColumnTransformer`) debe ajustarse (`.fit()`) **únicamente** en el conjunto de entrenamiento.
- **Validación temporal:** Si los datos tienen componente temporal, usar `TimeSeriesSplit` o divisiones basadas en fechas. Queda terminantemente prohibido el shuffling aleatorio en datos secuenciales.
- **Evaluación imparcial:** El test set no existe hasta la validación final. Nunca optimizar hiperparámetros contra el conjunto de test.

### Reproducibilidad
- Fijar semillas deterministas globales al inicio de cualquier pipeline (`numpy`, `random`, frameworks ML/DL) mediante una constante centralizada:

  ```python
  SEED = 42
  ```

  La constante vive en `src/utils/config.py` y no debe duplicarse en otros módulos.

## 3. Estilo de Programación
- **Vectorización** Tratar de priorizar el código vectorizado con librerias como `numpy` o `pandas` siempre que sea posible.
- **Comentarios** Tratar de evitar comentarios redundantes en el código y poner solo los necesarios, siempre tratar de usar docstrings.

## 4. Desarrollo Conceptual
- **Definición de Requisitos** No asumas nada de mis palabras ni trates de "rellenar" ninguna cosa que yo no haya dicho, ante la duda siempre pregunta, las preguntas nunca van a ser demasiados.
