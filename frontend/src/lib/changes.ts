import type { Change, ChangeStats, SeriesPoint, Topic } from "@/lib/api";
import { HEATMAP_TOPICS, INTERVENCIONES_MES_MIN, MESES_REGULARES_MIN } from "@/lib/constants";
import { fmtTopicLabel } from "@/lib/format";

/** Entrada mensual depurada (mes ISO normalizado a `AAAA-MM-DD` + valor). */
export interface TimelinePoint {
  month: string;
  value: number;
}

/** Cambio detectado unido a sus estadísticos, listo para presentar. */
export interface ResultChange {
  fecha: string;
  delta: number;
  mediaAntes: number;
  mediaDespues: number;
  r: number;
  p: number;
  n: number;
  nAntes: number;
  nDespues: number;
}

/** Tarjeta de la rejilla de la portada: serie + cambios + criterio de potencia. */
export interface TopicCard {
  topic: number;
  label: string | null;
  size: number;
  mesesRegulares: number;
  lowPower: boolean;
  points: TimelinePoint[];
  changes: ResultChange[];
  maxDelta: number;
}

/** Vista de la portada: serie de tono global y sus cambios con estadísticos. */
export interface ToneView {
  points: TimelinePoint[];
  changes: ResultChange[];
}

function statsKey(serieId: string, fecha: string): string {
  return `${serieId} ${fecha.slice(0, 10)}`;
}

function toResult(change: Change, stats: Map<string, ChangeStats>): ResultChange {
  const match = stats.get(statsKey(change.serie_id, change.fecha));
  return {
    fecha: change.fecha.slice(0, 10),
    delta: change.delta,
    mediaAntes: change.media_antes,
    mediaDespues: change.media_despues,
    r: match?.r ?? Number.NaN,
    p: match?.p ?? Number.NaN,
    n: match?.n ?? 0,
    nAntes: match?.n_antes ?? 0,
    nDespues: match?.n_despues ?? 0,
  };
}

function indexStats(stats: ChangeStats[]): Map<string, ChangeStats> {
  return new Map(stats.map((row) => [statsKey(row.serie_id, row.fecha), row]));
}

function usablePoints(series: SeriesPoint[]): TimelinePoint[] {
  return series
    .filter((row) => row.has_session && row.value !== null)
    .sort((a, b) => a.month.localeCompare(b.month))
    .map((row) => ({ month: row.month.slice(0, 10), value: row.value as number }));
}

/** Depura una serie mensual: solo meses con sesión y valor, en orden cronológico. */
export function toTimeline(series: SeriesPoint[]): TimelinePoint[] {
  return usablePoints(series);
}

/** Matriz del heatmap de cuota: top tópicos × meses (nulo = sin datos). */
export interface HeatmapData {
  labels: string[];
  months: string[];
  values: (number | null)[][];
  max: number;
}

function shortLabel(label: string | null, topicId: number): string {
  return fmtTopicLabel(label, topicId);
}

/**
 * Construye el heatmap «cuota relativa por tópico y mes».
 *
 * Reproduce `src/visualization/charts.py::topic_heatmap`: top
 * {@link HEATMAP_TOPICS} tópicos por intervenciones totales (descendente),
 * etiquetas truncadas a {@link LABEL_MAX_LENGTH} y celdas nulas donde no hay
 * valor (meses sin sesión).
 */
export function buildTopicHeatmap(series: SeriesPoint[], topics: Topic[]): HeatmapData {
  const topicRows = series.filter((row) => row.series_type === "topic");
  const totals = new Map<string, number>();
  for (const row of topicRows) {
    totals.set(row.series_id, (totals.get(row.series_id) ?? 0) + row.n_interventions);
  }
  const topIds = [...totals.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, HEATMAP_TOPICS)
    .map(([id]) => id);

  const labelById = new Map(topics.map((topic) => [String(topic.topic), topic.label]));
  const labels = topIds.map((id) => shortLabel(labelById.get(id) ?? null, Number(id)));

  const monthSet = new Set<string>();
  for (const row of topicRows) {
    if (row.has_session && row.value !== null) monthSet.add(row.month.slice(0, 10));
  }
  const months = [...monthSet].sort();

  const bySerie = new Map<string, Map<string, number>>();
  for (const row of topicRows) {
    if (!row.has_session || row.value === null) continue;
    const monthIndex = bySerie.get(row.series_id) ?? new Map<string, number>();
    monthIndex.set(row.month.slice(0, 10), row.value);
    bySerie.set(row.series_id, monthIndex);
  }

  let max = 0;
  const values = topIds.map((id) => {
    const serie = bySerie.get(id) ?? new Map<string, number>();
    return months.map((month) => {
      const value = serie.get(month);
      if (value === undefined) return null;
      max = Math.max(max, value);
      return value;
    });
  });

  return { labels, months, values, max };
}

function byMonth(changes: ResultChange[]): ResultChange[] {
  return [...changes].sort((a, b) => a.fecha.localeCompare(b.fecha));
}

/** Vista de la portada: serie de tono global y sus cambios con estadísticos. */
export function buildToneView(
  series: SeriesPoint[],
  changes: Change[],
  stats: ChangeStats[]
): ToneView {
  const index = indexStats(stats);
  return {
    points: usablePoints(series),
    changes: byMonth(changes.map((change) => toResult(change, index))),
  };
}

function monthsRegular(series: SeriesPoint[]): number {
  return series.filter((row) => row.has_session && row.n_interventions >= INTERVENCIONES_MES_MIN)
    .length;
}

function groupBy<T>(rows: T[], key: (row: T) => string): Map<string, T[]> {
  const groups = new Map<string, T[]>();
  for (const row of rows) {
    const bucket = groups.get(key(row));
    if (bucket) {
      bucket.push(row);
    } else {
      groups.set(key(row), [row]);
    }
  }
  return groups;
}

/**
 * Construye y ordena las tarjetas de la rejilla de tópicos.
 *
 * El orden es por magnitud máxima de cambio (`max |delta|`) descendente: es el
 * «índice de hallazgos» de la portada. El distintivo de baja potencia usa
 * {@link MESES_REGULARES_MIN} meses con al menos
 * {@link INTERVENCIONES_MES_MIN} intervenciones.
 */
export function buildTopicCards(
  topics: Topic[],
  series: SeriesPoint[],
  changes: Change[],
  stats: ChangeStats[]
): TopicCard[] {
  const index = indexStats(stats);
  const seriesBySerie = groupBy(series, (row) => row.series_id);
  const changesBySerie = groupBy(changes, (change) => change.serie_id);

  const cards = topics.map((topic) => {
    const serieId = String(topic.topic);
    const rows = seriesBySerie.get(serieId) ?? [];
    const serieChanges = byMonth(
      (changesBySerie.get(serieId) ?? []).map((change) => toResult(change, index))
    );
    const maxDelta = serieChanges.reduce((max, change) => Math.max(max, Math.abs(change.delta)), 0);
    const mesesRegulares = monthsRegular(rows);
    return {
      topic: topic.topic,
      label: topic.label,
      size: topic.size,
      mesesRegulares,
      lowPower: mesesRegulares < MESES_REGULARES_MIN,
      points: usablePoints(rows),
      changes: serieChanges,
      maxDelta,
    } satisfies TopicCard;
  });

  return cards.sort((a, b) => b.maxDelta - a.maxDelta || b.size - a.size);
}
