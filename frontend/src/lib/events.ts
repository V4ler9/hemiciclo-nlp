import type { EventRelation, EventRow, Topic } from "@/lib/api";
import { ASSOCIATION_TOPICS } from "@/lib/constants";
import { fmtTopicLabel } from "@/lib/format";

/** Vista del heatmap «asociación exploratoria evento × tópico» (D-09). */
export interface EventsView {
  /** Etiquetas cortas de los tópicos (filas, por |ρ| máximo desc). */
  labels: string[];
  /** Eventos en orden cronológico (columnas). */
  columns: string[];
  /** ρ por [tópico][evento]; nulo si falta el contraste. */
  rho: (number | null)[][];
  /** q (BH) por [tópico][evento]. */
  q: (number | null)[][];
  /** n por [tópico][evento]. */
  n: (number | null)[][];
  /** Rango simétrico del color: máx(0,6, |ρ| máx), como la figura original. */
  maxAbs: number;
}

/**
 * Construye la vista del heatmap de asociaciones replicando
 * `charts.py::associations_figure`: solo tópicos, top
 * {@link ASSOCIATION_TOPICS} por |ρ| máximo, columnas de eventos y rango de
 * color simétrico como mínimo ±0,6.
 */
export function buildEventsView(
  relations: EventRelation[],
  events: EventRow[],
  topics: Topic[]
): EventsView {
  const topicRelations = relations.filter((relation) => relation.serie === "topic");

  const maxBySerie = new Map<string, number>();
  for (const relation of topicRelations) {
    const current = maxBySerie.get(relation.serie_id) ?? 0;
    maxBySerie.set(relation.serie_id, Math.max(current, Math.abs(relation.rho ?? 0)));
  }
  const topIds = new Set(
    [...maxBySerie.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, ASSOCIATION_TOPICS)
      .map(([id]) => id)
  );

  const ordered = [...events].sort((a, b) => a.fecha.localeCompare(b.fecha));
  const columns = ordered.map((event) => event.evento);
  const columnPosition = new Map(columns.map((name, index) => [name, index]));

  const labelById = new Map(topics.map((topic) => [String(topic.topic), topic.label]));
  const ids = [...topIds];
  const labels = ids.map((id) => fmtTopicLabel(labelById.get(id) ?? null, Number(id)));
  const rowPosition = new Map(ids.map((id, index) => [id, index]));

  const size = ids.length;
  const rho = Array.from({ length: size }, () => Array<number | null>(columns.length).fill(null));
  const q = Array.from({ length: size }, () => Array<number | null>(columns.length).fill(null));
  const n = Array.from({ length: size }, () => Array<number | null>(columns.length).fill(null));

  let maxAbs = 0.6;
  for (const relation of topicRelations) {
    const y = rowPosition.get(relation.serie_id);
    const x = columnPosition.get(relation.evento);
    if (y === undefined || x === undefined) continue;
    const rhoRow = rho[y];
    const qRow = q[y];
    const nRow = n[y];
    if (!rhoRow || !qRow || !nRow) continue;
    rhoRow[x] = relation.rho;
    qRow[x] = relation.q;
    nRow[x] = relation.n;
    maxAbs = Math.max(maxAbs, Math.abs(relation.rho ?? 0));
  }

  return { labels, columns, rho, q, n, maxAbs };
}
