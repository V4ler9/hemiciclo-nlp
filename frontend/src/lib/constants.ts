/**
 * Intervenciones mínimas de un tópico en un mes para que su cuota se considere
 * fiable (ruido muestral de Poisson manejable).
 */
export const INTERVENCIONES_MES_MIN = 5;

/**
 * Meses «regulares» (≥ {@link INTERVENCIONES_MES_MIN} intervenciones) por debajo
 * de los cuales una serie se marca como de baja potencia.
 *
 * Umbral fijado en 10 meses, equivalente al primer cuartil de la distribución
 * actual (p25 = 10;12 de58 tópicos quedan marcados). La propuesta inicial de
 * 24 meses marcaba38 de58 y anulaba el distintivo.
 */
export const MESES_REGULARES_MIN = 10;

/**
 * Tópicos que muestra el heatmap de cuota por mes (top por intervenciones
 * totales). Reproduce el valor por defecto de `heatmap_topics` en
 * `configs/experiment_03.yaml` / `src/visualization/charts.py`.
 */
export const HEATMAP_TOPICS = 20;

/** Longitud máxima de la etiqueta en el eje del heatmap (charts.py usa 42). */
export const LABEL_MAX_LENGTH = 42;

/**
 * Tópicos del heatmap de asociaciones evento × tópico (top por |ρ|). Reproduce
 * `association_topics` de `configs/experiment_03.yaml` (20).
 */
export const ASSOCIATION_TOPICS = 20;

/**
 * Piso de la escala logarítmica del heatmap de cuota (0,01 %): las cuotas por
 * debajo —incluidos los ceros— se pintan en el extremo de la leyenda. Sin él,
 * `log10(0)` sería −∞ (Q4: escala log + render fino, D-42).
 */
export const HEATMAP_LOG_EPS = 1e-4;
