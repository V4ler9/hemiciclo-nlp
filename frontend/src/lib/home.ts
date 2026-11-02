import type { ActorChangeRow, EventAlignmentRow, HomeChange } from "@/lib/api";

/** Tipos editoriales del timeline de cambios. */
export type ChangeType = "shock" | "eleccion" | "legislatura" | "territorial" | "contexto";

export const CHANGE_TYPE_LABELS: Record<ChangeType, string> = {
  shock: "Shock externo",
  eleccion: "Elecciones",
  legislatura: "Legislatura / Gobierno",
  territorial: "Crisis territorial",
  contexto: "Otros cambios",
};

/** Paleta sobria y accesible para el timeline (contraste sobre blanco). */
export const CHANGE_TYPE_COLORS: Record<ChangeType, string> = {
  shock: "#9f1239",
  eleccion: "#1d4ed8",
  legislatura: "#52525b",
  territorial: "#a16207",
  contexto: "#a1a1aa",
};

/** Colores sobrios para las familias de partido del acto de composición. */
export const FAMILY_COLORS: Record<string, string> = {
  PP: "#1d4ed8",
  PSOE: "#b91c1c",
  Vox: "#15803d",
  Cs: "#a16207",
  UP: "#7e22ce",
  ERC: "#0f766e",
  JxCat: "#0369a1",
  PNV: "#4d7c0f",
  "EH Bildu": "#9a3412",
  BNG: "#6b21a8",
  CC: "#a21caf",
  Otros: "#71717a",
};

/** Etiquetas cortas de las 14 hipótesis del event study. */
export const HYPOTHESIS_LABELS: Record<string, string> = {
  H01: "2015 · elección → confrontación",
  H02: "2016 · gobierno → confrontación",
  H03: "2016 · gobierno → energía",
  H04: "2018 · moción → corrupción",
  H05: "2018 · moción → pensiones",
  H06: "2019 · elección → confrontación",
  H07: "2020 · COVID → sanidad",
  H08: "2020 · COVID → ERTE",
  H09: "2020 · COVID → share negativo",
  H10: "2020 · fin alarma → share negativo",
  H11: "2020 · fin alarma → COVID",
  H12: "2022 · guerra → Ucrania",
  H13: "2022 · guerra → energía",
  H14: "2022 · guerra → agricultura",
};

/** Episodios editoriales del MVP, ordenados por fecha. */
export const EPISODE_ORDER = [
  "EP01_2016_11",
  "EP02_2018_06",
  "EP03_2020_03",
  "EP04_2020_06",
  "EP05_2022_02",
] as const;

function startsWithAny(fecha: string, prefixes: readonly string[]): boolean {
  return prefixes.some((prefix) => fecha.startsWith(prefix));
}

/** Clasifica un cambio en el tipo editorial del timeline. */
export function changeType(change: Pick<HomeChange, "serie" | "fecha">): ChangeType {
  if (change.serie === "tone") return "shock";
  if (startsWithAny(change.fecha, ["2015-12", "2016-06", "2019-04", "2019-11"])) {
    return "eleccion";
  }
  if (startsWithAny(change.fecha, ["2016-01", "2016-07", "2016-11", "2018-06", "2019-12", "2020-01"])) {
    return "legislatura";
  }
  if (startsWithAny(change.fecha, ["2017-10", "2019-10"])) return "territorial";
  if (startsWithAny(change.fecha, ["2020-03", "2020-06", "2020-10", "2021", "2022"])) {
    return "shock";
  }
  return "contexto";
}

function changeKey(row: Pick<ActorChangeRow, "serie" | "serie_id" | "fecha">): string {
  return `${row.serie}|${row.serie_id}|${row.fecha.slice(0, 10)}`;
}

/** Índice de filas de actores por cambio, solo nivel partido. */
export function indexActorChanges(rows: ActorChangeRow[]): Map<string, ActorChangeRow[]> {
  const index = new Map<string, ActorChangeRow[]>();
  for (const row of rows) {
    if (row.nivel !== "partido" || row.partido === "__residual__") continue;
    const key = changeKey(row);
    const bucket = index.get(key);
    if (bucket) bucket.push(row);
    else index.set(key, [row]);
  }
  return index;
}

function actorContribution(row: ActorChangeRow): number {
  return Math.abs(row.contribucion_dentro ?? 0) + Math.abs(row.contribucion_composicion ?? 0);
}

/** Partido con mayor contribución absoluta a un cambio. */
export function topActorForChange(
  change: Pick<HomeChange, "serie" | "serie_id" | "fecha">,
  index: Map<string, ActorChangeRow[]>
): ActorChangeRow | null {
  const rows = index.get(changeKey(change)) ?? [];
  return [...rows].sort((a, b) => actorContribution(b) - actorContribution(a))[0] ?? null;
}

/** Periodos del explorador final. */
export type ChangePeriod = "todos" | "2015-2017" | "2018-2020" | "2021-2023";

/** Filtro del explorador final. */
export interface ChangeFilters {
  type: ChangeType | "todos";
  actor: string | "todos";
  period: ChangePeriod;
}

function inPeriod(fecha: string, period: ChangePeriod): boolean {
  if (period === "todos") return true;
  const year = Number(fecha.slice(0, 4));
  if (period === "2015-2017") return year >= 2015 && year <= 2017;
  if (period === "2018-2020") return year >= 2018 && year <= 2020;
  return year >= 2021 && year <= 2023;
}

/** Filtra los cambios del timeline por tipo, actor y periodo. */
export function filterChanges(
  changes: HomeChange[],
  actorIndex: Map<string, ActorChangeRow[]>,
  filters: ChangeFilters
): HomeChange[] {
  return changes.filter((change) => {
    if (change.significativo_bh !== 1) return false;
    if (filters.type !== "todos" && changeType(change) !== filters.type) return false;
    if (!inPeriod(change.fecha, filters.period)) return false;
    if (filters.actor !== "todos") {
      const top = topActorForChange(change, actorIndex);
      if (!top || top.partido !== filters.actor) return false;
    }
    return true;
  });
}

/** Actores disponibles para el filtro, ordenados por frecuencia. */
export function availableActors(actorIndex: Map<string, ActorChangeRow[]>): string[] {
  const counts = new Map<string, number>();
  for (const rows of actorIndex.values()) {
    const top = [...rows].sort((a, b) => actorContribution(b) - actorContribution(a))[0];
    if (top) counts.set(top.partido, (counts.get(top.partido) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([name]) => name);
}

/** Etiqueta corta de una hipótesis del event study. */
export function hypothesisLabel(row: EventAlignmentRow): string {
  return hypothesisLabelById(row.hipotesis_id);
}

/** Etiqueta corta de una hipótesis por identificador. */
export function hypothesisLabelById(id: string): string {
  return HYPOTHESIS_LABELS[id] ?? id;
}

/** Color de una hipótesis según significación. */
export function alignmentColor(row: EventAlignmentRow): string {
  return row.significativo_bh === 1 ? "#9f1239" : "#a1a1aa";
}
