import { HEATMAP_LOG_EPS } from "@/lib/constants";
import type { HeatmapData, ResultChange, TimelinePoint, TopicCard } from "@/lib/changes";
import type { ChartOption } from "@/lib/echarts";
import type { EventsView } from "@/lib/events";
import type {
  ActorChangeRow,
  ActorPoint,
  EventAlignmentRow,
  HomeChange,
  ToneCounterfactualPoint,
} from "@/lib/api";
import {
  CHANGE_TYPE_COLORS,
  FAMILY_COLORS,
  alignmentColor,
  changeType,
  hypothesisLabel,
  topActorForChange,
} from "@/lib/home";
import {
  fmtDecimal,
  fmtDelta,
  fmtInt,
  fmtMonth,
  fmtP,
  fmtQuota,
  intervalLine,
  statsLine,
} from "@/lib/format";

type TooltipParam = {
  axisValue?: string;
  seriesName?: string;
  value?: number | number[] | string | null;
};

type TooltipEntry = TooltipParam & {
  componentType?: string;
  name?: string;
};

/**
 * Formateador de tooltip de eje tipado en `unknown` para que sea asignable a
 * cualquier firma de ECharts sin perder seguridad en el cuerpo.
 */
export function axisTooltip(params: unknown, format: (value: number) => string): string {
  const list = (Array.isArray(params) ? params : [params]) as TooltipParam[];
  const first = list[0];
  if (!first) return "";
  const raw = first.value;
  const value = typeof raw === "number" ? format(raw) : String(raw ?? "");
  return `${first.axisValue ?? ""}<br/>${first.seriesName ?? ""}: ${value}`;
}

const AXIS_LABEL = { color: "#71717a", fontSize: 11 } as const;
const INK = "#18181b";
const RULE = "#d4d4d8";

function changeMarks(changes: ResultChange[], labels: Set<string>) {
  return changes
    .filter((change) => labels.has(fmtMonth(change.fecha)))
    .map((change) => ({ xAxis: fmtMonth(change.fecha), name: fmtMonth(change.fecha) }));
}

/**
 * Tooltip del héroe: mes + valor como base y, al tocar una línea de cambio,
 * la ficha completa del cambio (fecha, Δ, medias, `r`, `p`, `n` e intervalo).
 */
function toneTooltip(params: unknown, changesByLabel: Map<string, ResultChange>): string {
  const list = (Array.isArray(params) ? params : [params]) as TooltipEntry[];
  const lines: string[] = [];

  const serie = list.find((entry) => entry.componentType === "series");
  if (serie) {
    const raw = serie.value;
    const value = typeof raw === "number" ? fmtDecimal(raw, 3) : String(raw ?? "");
    lines.push(`${serie.axisValue ?? ""}<br/>${serie.seriesName ?? ""}: ${value}`);
  }

  const marca = list.find((entry) => entry.componentType === "markLine");
  const change = marca ? changesByLabel.get(String(marca.name ?? "")) : undefined;
  if (change) {
    lines.push(
      "",
      `<b>${fmtMonth(change.fecha)}</b> · Δ ${fmtDelta(change.delta)}`,
      `${fmtDecimal(change.mediaAntes)} → ${fmtDecimal(change.mediaDespues)}`,
      statsLine(change)
    );
    const intervalo = intervalLine(change);
    if (intervalo) lines.push(intervalo);
  }

  if (lines.length === 0) {
    return axisTooltip(params, (value) => fmtDecimal(value, 3));
  }
  return lines.join("<br/>");
}

/** Opción de la serie de tono global con líneas de cambio en cada corte. */
export function buildToneOption(points: TimelinePoint[], changes: ResultChange[]): ChartOption {
  const labels = points.map((point) => fmtMonth(point.month));
  const changesByLabel = new Map(changes.map((change) => [fmtMonth(change.fecha), change]));
  return {
    animation: false,
    grid: { left: 40, right: 20, top: 34, bottom: 28 },
    xAxis: {
      type: "category",
      data: labels,
      boundaryGap: false,
      axisLine: { lineStyle: { color: RULE } },
      axisTick: { show: false },
      axisLabel: { ...AXIS_LABEL, interval: 11, formatter: (value: string) => value.slice(-4) },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: 6,
      name: "senti_n (0–6)",
      nameTextStyle: AXIS_LABEL,
      axisLabel: { ...AXIS_LABEL, formatter: (value: number) => String(value) },
      splitLine: { lineStyle: { color: "#e4e4e7", type: "dashed" } },
    },
    tooltip: {
      trigger: "axis",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => toneTooltip(params, changesByLabel),
    },
    series: [
      {
        type: "line",
        name: "Tono medio mensual",
        data: points.map((point) => point.value),
        showSymbol: false,
        lineStyle: { width: 2, color: INK },
        itemStyle: { color: INK },
        markLine: {
          silent: false,
          triggerLineEvent: true,
          symbol: ["none", "none"],
          lineStyle: { type: "dashed", color: "#a1a1aa", width: 1.5 },
          label: {
            position: "insideEndTop",
            distance: 6,
            formatter: "{b}",
            color: "#71717a",
            fontSize: 11,
          },
          data: changeMarks(changes, new Set(labels)),
        },
      },
    ],
  };
}

/** Opción de un sparkline de cuota para las tarjetas de la rejilla. */
export function buildSparklineOption(card: TopicCard): ChartOption {
  const labels = card.points.map((point) => fmtMonth(point.month));
  return {
    animation: false,
    grid: { left: 4, right: 4, top: 8, bottom: 4 },
    xAxis: {
      type: "category",
      data: labels,
      boundaryGap: false,
      show: false,
    },
    yAxis: { type: "value", min: 0, show: false },
    tooltip: {
      trigger: "axis",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 11 },
      formatter: (params: unknown) => axisTooltip(params, (value) => fmtQuota(value)),
    },
    series: [
      {
        type: "line",
        name: "Cuota",
        data: card.points.map((point) => point.value),
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#3f3f46" },
        itemStyle: { color: "#3f3f46" },
        markLine: {
          silent: true,
          symbol: ["none", "none"],
          lineStyle: { type: "dashed", color: "#a1a1aa", width: 1 },
          label: { show: false },
          data: changeMarks(card.changes, new Set(labels)),
        },
      },
    ],
  };
}

function temporalAxis(data: string[]) {
  return {
    type: "category" as const,
    data,
    axisLine: { lineStyle: { color: RULE } },
    axisTick: { show: false },
    axisLabel: { ...AXIS_LABEL, interval: 11, formatter: (value: string) => value.slice(-4) },
  };
}

/** Opción del volumen mensual de intervenciones (barras). */
export function buildVolumeOption(points: TimelinePoint[]): ChartOption {
  const labels = points.map((point) => fmtMonth(point.month));
  return {
    animation: false,
    grid: { left: 48, right: 16, top: 24, bottom: 28 },
    xAxis: temporalAxis(labels),
    yAxis: {
      type: "value",
      axisLabel: { ...AXIS_LABEL, formatter: (value: number) => fmtInt(value) },
      splitLine: { lineStyle: { color: "#e4e4e7", type: "dashed" } },
    },
    tooltip: {
      trigger: "axis",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => axisTooltip(params, (value) => fmtInt(Math.round(value))),
    },
    series: [
      {
        type: "bar",
        name: "Intervenciones",
        data: points.map((point) => point.value),
        itemStyle: { color: "#52525b" },
        barCategoryGap: "25%",
      },
    ],
  };
}

/** Opción de la tasa mensual de outliers (línea, eje en porcentaje). */
export function buildOutliersOption(points: TimelinePoint[]): ChartOption {
  const labels = points.map((point) => fmtMonth(point.month));
  return {
    animation: false,
    grid: { left: 44, right: 16, top: 24, bottom: 28 },
    xAxis: temporalAxis(labels),
    yAxis: {
      type: "value",
      min: 0,
      axisLabel: {
        ...AXIS_LABEL,
        formatter: (value: number) =>
          `${(value * 100).toLocaleString("es-ES", { maximumFractionDigits: 0 })} %`,
      },
      splitLine: { lineStyle: { color: "#e4e4e7", type: "dashed" } },
    },
    tooltip: {
      trigger: "axis",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => axisTooltip(params, (value) => fmtQuota(value)),
    },
    series: [
      {
        type: "line",
        name: "Tasa de outliers",
        data: points.map((point) => point.value),
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#71717a" },
        itemStyle: { color: "#71717a" },
      },
    ],
  };
}

/** Viridis muestreado: rampa del heatmap (misma familia que la figura original). */
const VIRIDIS = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"];

/** RdBu de ColorBrewer con extremos en rojo (negativo) y azul (positivo), como RdBu_r. */
const RDBU = [
  "#67001f",
  "#b2182b",
  "#d6604d",
  "#f4a582",
  "#fddbc7",
  "#f7fbff",
  "#c6dbef",
  "#6baed6",
  "#2171b5",
  "#08519c",
  "#08306b",
];

/** Escala logarítmica de cuota con piso en {@link HEATMAP_LOG_EPS} (evita −∞). */
export function heatmapLog(quota: number): number {
  return Math.log10(Math.max(quota, HEATMAP_LOG_EPS));
}

function heatmapLogLabel(value: number): string {
  const quota = 10 ** value;
  if (quota <= HEATMAP_LOG_EPS * 1.5) return `< ${fmtQuota(HEATMAP_LOG_EPS)}`;
  return `${quota.toLocaleString("es-ES", { maximumSignificantDigits: 2 })} %`;
}

/** Opción del heatmap «cuota relativa por tópico y mes» (escala log, top tópicos). */
export function buildTopicHeatmapOption(data: HeatmapData): ChartOption {
  const months = data.months.map((month) => fmtMonth(month));
  const floorLog = Math.log10(HEATMAP_LOG_EPS);
  const maxLog = data.max > HEATMAP_LOG_EPS ? Math.log10(data.max) : floorLog + 1;
  const cells: number[][] = [];
  data.values.forEach((row, y) => {
    row.forEach((value, x) => {
      if (value !== null) cells.push([x, y, heatmapLog(value)]);
    });
  });
  return {
    animation: false,
    grid: { left: 210, right: 24, top: 16, bottom: 72 },
    xAxis: {
      type: "category",
      data: months,
      axisLine: { lineStyle: { color: RULE } },
      axisTick: { show: false },
      axisLabel: { ...AXIS_LABEL, interval: 11, formatter: (value: string) => value.slice(-4) },
    },
    yAxis: {
      type: "category",
      data: data.labels,
      inverse: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        ...AXIS_LABEL,
        width: 190,
        overflow: "truncate",
      },
    },
    visualMap: {
      min: floorLog,
      max: maxLog,
      splitNumber: 5,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 4,
      itemWidth: 12,
      itemHeight: 120,
      textStyle: AXIS_LABEL,
      formatter: (value: number) => heatmapLogLabel(value),
      inRange: { color: VIRIDIS },
    },
    tooltip: {
      trigger: "item",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => {
        const item = params as { data?: [number, number, number] };
        const [x = 0, y = 0] = item.data ?? [];
        const month = months[x] ?? "";
        const topic = data.labels[y] ?? "";
        const original = data.values[y]?.[x];
        const count = data.counts[y]?.[x];
        const cuota = original !== null && original !== undefined ? fmtQuota(original) : "n/d";
        const intervenciones =
          count !== null && count !== undefined ? ` · ${fmtInt(count)} interv.` : "";
        return `${topic}<br/>${month}: ${cuota}${intervenciones}`;
      },
    },
    series: [
      {
        type: "heatmap",
        name: "Cuota (log)",
        data: cells,
        itemStyle: { borderWidth: 0.5, borderColor: "rgba(255, 255, 255, 0.6)" },
      },
    ],
  };
}

/** Opción ampliada de un tópico para el diálogo de la portada (Q1c: sin `q`). */
export function buildTopicDetailOption(card: TopicCard): ChartOption {
  const labels = card.points.map((point) => fmtMonth(point.month));
  return {
    animation: false,
    grid: { left: 56, right: 20, top: 32, bottom: 32 },
    xAxis: temporalAxis(labels),
    yAxis: {
      type: "value",
      min: 0,
      axisLabel: { ...AXIS_LABEL, formatter: (value: number) => fmtQuota(value) },
      splitLine: { lineStyle: { color: "#e4e4e7", type: "dashed" } },
    },
    tooltip: {
      trigger: "axis",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => axisTooltip(params, (value) => fmtQuota(value)),
    },
    series: [
      {
        type: "line",
        name: "Cuota",
        data: card.points.map((point) => point.value),
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#3f3f46" },
        itemStyle: { color: "#3f3f46" },
        markLine: {
          silent: true,
          symbol: ["none", "none"],
          lineStyle: { type: "dashed", color: "#a1a1aa", width: 1.5 },
          label: {
            position: "insideEndTop",
            distance: 6,
            formatter: "{b}",
            color: "#71717a",
            fontSize: 11,
          },
          data: changeMarks(card.changes, new Set(labels)),
        },
      },
    ],
  };
}

function significantQ(value: number | null | undefined): boolean {
  return value !== null && value !== undefined && value < 0.05;
}

/** Opción del heatmap «asociación exploratoria evento × tópico» (ρ; ★ si q < 0,05). */
export function buildEventsOption(view: EventsView): ChartOption {
  const cells: number[][] = [];
  view.rho.forEach((row, y) => {
    row.forEach((value, x) => {
      if (value !== null) cells.push([x, y, value]);
    });
  });
  return {
    animation: false,
    grid: { left: 210, right: 24, top: 16, bottom: 104 },
    xAxis: {
      type: "category",
      data: view.columns,
      axisLine: { lineStyle: { color: RULE } },
      axisTick: { show: false },
      axisLabel: { ...AXIS_LABEL, rotate: 42, hideOverlap: true },
    },
    yAxis: {
      type: "category",
      data: view.labels,
      inverse: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { ...AXIS_LABEL, width: 190, overflow: "truncate" },
    },
    visualMap: {
      min: -view.maxAbs,
      max: view.maxAbs,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 4,
      itemWidth: 12,
      itemHeight: 120,
      textStyle: AXIS_LABEL,
      formatter: (value: number) =>
        value.toLocaleString("es-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      inRange: { color: RDBU },
    },
    tooltip: {
      trigger: "item",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => {
        const item = params as { data?: [number, number, number] };
        const [x = 0, y = 0, value = 0] = item.data ?? [];
        const topic = view.labels[y] ?? "";
        const evento = view.columns[x] ?? "";
        const qValue = view.q[y]?.[x];
        const nValue = view.n[y]?.[x];
        const lines = [
          `${topic}`,
          `${evento}`,
          `ρ = ${fmtDecimal(value, 3)} · q = ${qValue !== null && qValue !== undefined ? fmtP(qValue) : "n/d"}${nValue !== null && nValue !== undefined ? ` · n = ${nValue}` : ""}`,
        ];
        if (significantQ(qValue)) lines.push("q < 0,05");
        return lines.join("<br/>");
      },
    },
    series: [
      {
        type: "heatmap",
        name: "ρ",
        data: cells,
        itemStyle: { borderWidth: 0 },
        label: {
          show: true,
          formatter: (params: unknown) => {
            const item = params as { data?: [number, number, number] };
            const [x = 0, y = 0] = item.data ?? [];
            return significantQ(view.q[y]?.[x]) ? "★" : "";
          },
          color: INK,
          fontSize: 13,
        },
      },
    ],
  };
}

/** Opción del acto de tono: share negativo real frente al contrafactual. */
function quarterLabel(month: string): string {
  const year = month.slice(0, 4);
  const quarter = Math.floor((Number(month.slice(5, 7)) - 1) / 3) + 1;
  return `${year} Q${quarter}`;
}

function quarterAxis(data: string[]) {
  return {
    type: "category" as const,
    data,
    axisLine: { lineStyle: { color: RULE } },
    axisTick: { show: false },
    axisLabel: {
      ...AXIS_LABEL,
      interval: 3,
      formatter: (value: string) => value.slice(0, 4),
    },
  };
}

function smoothQuarterly(
  values: (number | null)[],
  weights: number[]
): (number | null)[] {
  return values.map((_, index) => {
    let weighted = 0;
    let total = 0;
    for (const position of [index - 1, index, index + 1]) {
      const value = values[position];
      const weight = weights[position] ?? 0;
      if (value !== null && value !== undefined && weight > 0) {
        weighted += value * weight;
        total += weight;
      }
    }
    return total > 0 ? weighted / total : null;
  });
}

export function buildToneCompositionOption(points: ToneCounterfactualPoint[]): ChartOption {
  const quarters = new Map<string, { n: number; real: number; adjusted: number }>();
  for (const point of points) {
    const key = quarterLabel(point.month);
    const bucket = quarters.get(key) ?? { n: 0, real: 0, adjusted: 0 };
    bucket.n += point.n;
    bucket.real += point.neg_share_real * point.n;
    bucket.adjusted += point.neg_share_ajustado * point.n;
    quarters.set(key, bucket);
  }
  const labels = [...quarters.keys()].sort();
  const weights = labels.map((key) => quarters.get(key)?.n ?? 0);
  const rawReal = labels.map((key) => {
    const bucket = quarters.get(key);
    return bucket && bucket.n > 0 ? bucket.real / bucket.n : null;
  });
  const rawAdjusted = labels.map((key) => {
    const bucket = quarters.get(key);
    return bucket && bucket.n > 0 ? bucket.adjusted / bucket.n : null;
  });
  const realData = smoothQuarterly(rawReal, weights);
  const adjustedData = smoothQuarterly(rawAdjusted, weights);
  const maxValue = Math.max(
    ...realData.filter((value): value is number => value !== null),
    ...adjustedData.filter((value): value is number => value !== null),
    0.5
  );
  const upper = Math.ceil(maxValue * 10) / 10;
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 36, bottom: 52 },
    legend: {
      data: ["Share negativo real", "Contrafactual (cuotas pre-2020-06)"],
      bottom: 0,
      textStyle: AXIS_LABEL,
      itemWidth: 18,
      itemHeight: 8,
    },
    xAxis: quarterAxis(labels),
    yAxis: {
      type: "value",
      min: 0,
      max: upper,
      axisLabel: {
        ...AXIS_LABEL,
        formatter: (value: number) => `${Math.round(value * 100)} %`,
      },
      splitLine: { lineStyle: { color: "#e4e4e7", type: "dashed" } },
    },
    tooltip: {
      trigger: "axis",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => {
        const list = (Array.isArray(params) ? params : [params]) as TooltipEntry[];
        const month = list[0]?.axisValue ?? "";
        const real = list.find((entry) => entry.seriesName === "Share negativo real")?.value;
        const adjusted = list.find(
          (entry) => entry.seriesName === "Contrafactual (cuotas pre-2020-06)"
        )?.value;
        const realValue = typeof real === "number" ? real : Number.NaN;
        const adjustedValue = typeof adjusted === "number" ? adjusted : Number.NaN;
        return [
          month,
          `Real: ${fmtQuota(realValue)}`,
          `Ajustado: ${fmtQuota(adjustedValue)}`,
          `Brecha: ${fmtDelta((realValue - adjustedValue) * 100)} pp`,
        ].join("<br/>");
      },
    },
    series: [
      {
        type: "line",
        name: "Share negativo real",
        data: realData,
        showSymbol: false,
        lineStyle: { width: 2, color: INK },
        itemStyle: { color: INK },
        markLine: {
          silent: true,
          symbol: ["none", "none"],
          lineStyle: { type: "dashed", color: "#a1a1aa", width: 1 },
          label: {
            position: "insideEndTop",
            formatter: "2020 Q2",
            color: "#71717a",
            fontSize: 11,
          },
          data: [{ xAxis: "2020 Q2" }],
        },
      },
      {
        type: "line",
        name: "Contrafactual (cuotas pre-2020-06)",
        data: adjustedData,
        showSymbol: false,
        lineStyle: { width: 1.5, color: "#71717a", type: "dashed" },
        itemStyle: { color: "#71717a" },
      },
    ],
  };
}

/** Opción del acto de actores: cuota de intervenciones de PP, PSOE y Vox. */
export function buildActorShareOption(points: ActorPoint[], families: string[]): ChartOption {
  const months = [...new Set(points.map((point) => point.month.slice(0, 10)))].sort();
  const labels = months.map((month) => fmtMonth(month));
  const byFamily = new Map<string, Map<string, { share: number; n: number }>>();
  for (const point of points) {
    if (!families.includes(point.party_family)) continue;
    const month = point.month.slice(0, 10);
    const bucket = byFamily.get(point.party_family) ?? new Map<string, { share: number; n: number }>();
    if (point.share_all !== null) bucket.set(month, { share: point.share_all, n: point.n });
    byFamily.set(point.party_family, bucket);
  }
  return {
    animation: false,
    grid: { left: 52, right: 24, top: 28, bottom: 52 },
    legend: {
      data: families,
      bottom: 0,
      textStyle: AXIS_LABEL,
      itemWidth: 18,
      itemHeight: 8,
    },
    xAxis: temporalAxis(labels),
    yAxis: {
      type: "value",
      min: 0,
      axisLabel: {
        ...AXIS_LABEL,
        formatter: (value: number) => `${Math.round(value * 100)} %`,
      },
      splitLine: { lineStyle: { color: "#e4e4e7", type: "dashed" } },
    },
    tooltip: {
      trigger: "axis",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => {
        const list = (Array.isArray(params) ? params : [params]) as TooltipEntry[];
        const lines = [list[0]?.axisValue ?? ""];
        for (const entry of list) {
          if (typeof entry.value === "number") {
            lines.push(`${entry.seriesName ?? ""}: ${fmtQuota(entry.value)}`);
          }
        }
        return lines.join("<br/>");
      },
    },
    series: families.map((family) => {
      const values = byFamily.get(family) ?? new Map<string, { share: number; n: number }>();
      const data = months.map((month, index) => {
        const window = [
          months[index - 3],
          months[index - 2],
          months[index - 1],
          month,
          months[index + 1],
          months[index + 2],
          months[index + 3],
        ].filter((candidate): candidate is string => Boolean(candidate));
        const present = window
          .map((candidate) => values.get(candidate))
          .filter((value): value is { share: number; n: number } => Boolean(value));
        const total = present.reduce((sum, value) => sum + value.n, 0);
        return total > 0
          ? present.reduce((sum, value) => sum + value.share * value.n, 0) / total
          : null;
      });
      return {
        type: "line",
        name: family,
        data,
        showSymbol: false,
        lineStyle: { width: 2, color: FAMILY_COLORS[family] ?? "#52525b" },
        itemStyle: { color: FAMILY_COLORS[family] ?? "#52525b" },
      };
    }),
  };
}

/** Opción del event study: delta de cada hipótesis, rojo si supera BH. */
export function buildEventAlignmentOption(rows: EventAlignmentRow[]): ChartOption {
  const sorted = [...rows].sort((a, b) => a.delta - b.delta);
  return {
    animation: false,
    grid: { left: 236, right: 72, top: 16, bottom: 28 },
    xAxis: {
      type: "value",
      axisLabel: {
        ...AXIS_LABEL,
        formatter: (value: number) => `${Math.round(value * 100)} pp`,
      },
      splitLine: { lineStyle: { color: "#e4e4e7", type: "dashed" } },
    },
    yAxis: {
      type: "category",
      data: sorted.map((row) => hypothesisLabel(row)),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { ...AXIS_LABEL, width: 220, overflow: "truncate" },
    },
    tooltip: {
      trigger: "item",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => {
        const item = params as { data?: { row?: EventAlignmentRow } };
        const row = item.data?.row;
        if (!row) return "";
        return [
          hypothesisLabel(row),
          `Δ = ${fmtQuota(row.delta)}`,
          `q = ${fmtP(row.q)} · n = ${row.n_antes + row.n_despues}`,
          row.significativo_bh === 1 ? "Supera BH (q < 0,05)" : "No supera BH",
        ].join("<br/>");
      },
    },
    series: [
      {
        type: "bar",
        data: sorted.map((row) => ({
          value: row.delta,
          itemStyle: { color: alignmentColor(row) },
          row,
        })),
        barMaxWidth: 14,
        label: {
          show: true,
          position: "right",
          color: INK,
          fontSize: 11,
          formatter: (params: unknown) => {
            const item = params as { value?: number };
            return `${fmtDelta((item.value ?? 0) * 100)} pp`;
          },
        },
      },
    ],
  } as ChartOption;
}

/** Opción del explorador final: fecha, impacto y tipo de cada cambio de tópico. */
export function buildChangeTimelineOption(
  changes: HomeChange[],
  actorIndex: Map<string, ActorChangeRow[]>
): ChartOption {
  const topics = changes.filter((change) => change.serie === "topic" && change.impacto !== null);
  const maxImpact = Math.max(...topics.map((change) => change.impacto ?? 0), 0.001);
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 24, bottom: 36 },
    xAxis: {
      type: "time",
      axisLabel: AXIS_LABEL,
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      name: "interv./mes desplazadas",
      nameTextStyle: AXIS_LABEL,
      axisLabel: AXIS_LABEL,
      splitLine: { lineStyle: { color: "#e4e4e7", type: "dashed" } },
    },
    tooltip: {
      trigger: "item",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => {
        const item = params as { data?: { change?: HomeChange; top?: string } };
        const change = item.data?.change;
        if (!change) return "";
        return [
          `<b>${change.label}</b>`,
          `${fmtMonth(change.fecha)} · Δ ${fmtDelta(change.delta * 100)} pp`,
          `q = ${fmtP(change.q)} · impacto = ${fmtDecimal(change.impacto ?? 0, 2)} interv./mes`,
          `Actor principal: ${item.data?.top ?? "—"}`,
        ].join("<br/>");
      },
    },
    series: [
      {
        type: "scatter",
        data: topics.map((change) => {
          const top = topActorForChange(change, actorIndex);
          const type = changeType(change);
          return {
            value: [change.fecha, change.impacto ?? 0],
            symbolSize: 8 + 18 * Math.sqrt((change.impacto ?? 0) / maxImpact),
            itemStyle: { color: CHANGE_TYPE_COLORS[type], opacity: 0.85 },
            change,
            top: top?.partido ?? "—",
          };
        }),
      },
    ],
  } as ChartOption;
}
