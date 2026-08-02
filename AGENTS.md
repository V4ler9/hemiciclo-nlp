# AGENTS.md — hemiciclo-nlp

Instrucciones para agentes de código que trabajen en este repositorio.

## Reglas inquebrantables

1. **Trazabilidad:** prohibido `print()` para depuración en código de producción; instrumentar con `logging`.
2. **Tipado estricto:** todo código Python con **type hints** y **docstrings**.
3. **Inmutabilidad del dato:** `data/raw/` es de solo lectura. Nunca escribir, editar ni eliminar archivos ahí. Toda transformación → `data/processed/`.
4. **Rigor analítico:** priorizar librerías de alto rendimiento y técnicas modernas. Optimización **bayesiana con Optuna** (no GridSearchCV). Para modelado tabular, evaluar ensambles (CatBoost/XGBoost) antes de modelos base. Control exhaustivo del data leakage con validación cruzada.
5. **Vectorización:** preferir `pandas`/`numpy` vectorizados; considerar `polars` si el dataset excede la RAM.
6. **Reproducibilidad:** fijar random seeds, versionar datasets procesados y documentar hiperparámetros finales.

## Convenciones del proyecto

- Layout en `src/<módulo>/`; tests en `tests/test_<módulo>.py` (pytest).
- Configuración en `configs/*.yaml` (paths, seeds, hiperparámetros) — cargar vía `src/utils/config.py`.
- Modelos versionados en `models/` con sufijo `_v1`, `_v2`, ... e idealmente en ONNX.
- No commitear `data/` (gitignored), ni `.tar` crudos, ni modelos grandes.
- Métricas del proyecto: Topic Coherence (C_V), Topic Diversity, Macro F1 (sentimiento), Correlación de Spearman.
- Reportes y figuras finales → `reports/`.

## Flujo de trabajo sugerido

1. Exploración en `notebooks/` (archivos inmutable; no son source).
2. Implementación modular en `src/` con tests unitarios.
3. Experimentos vía `configs/experiment_*.yaml` + estudios Optuna.
4. Servir con `app/` (FastAPI + Streamlit) y containerizar en Fase 6.
