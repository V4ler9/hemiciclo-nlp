import type { HeatmapData, ResultChange, TimelinePoint, TopicCard } from "@/lib/changes";
import type { ChartOption } from "@/lib/echarts";
import type { EventsView } from "@/lib/events";
import { fmtDecimal, fmtInt, fmtMonth, fmtP, fmtQuota } from "@/lib/format";

type TooltipParam = {
  axisValue?: string;
  seriesName?: string;
  value?: number | number[] | string | null;
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

/** Opción de la serie de tono global con líneas de cambio en cada corte. */
export function buildToneOption(points: TimelinePoint[], changes: ResultChange[]): ChartOption {
  const labels = points.map((point) => fmtMonth(point.month));
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
      formatter: (params: unknown) =>
        axisTooltip(params, (value) =>
          value.toLocaleString("es-ES", { minimumFractionDigits: 3, maximumFractionDigits: 3 })
        ),
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

/** Opción del heatmap «cuota relativa por tópico y mes» (top tópicos). */
export function buildTopicHeatmapOption(data: HeatmapData): ChartOption {
  const months = data.months.map((month) => fmtMonth(month));
  const cells: number[][] = [];
  data.values.forEach((row, y) => {
    row.forEach((value, x) => {
      if (value !== null) cells.push([x, y, value]);
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
      min: 0,
      max: data.max,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 4,
      itemWidth: 12,
      itemHeight: 120,
      textStyle: AXIS_LABEL,
      formatter: (value: number) => fmtQuota(value),
      inRange: { color: VIRIDIS },
    },
    tooltip: {
      trigger: "item",
      borderColor: RULE,
      backgroundColor: "#ffffff",
      textStyle: { color: INK, fontSize: 12 },
      formatter: (params: unknown) => {
        const item = params as { data?: [number, number, number] };
        const [x, y, value] = item.data ?? [0, 0, 0];
        const month = months[x] ?? "";
        const topic = data.labels[y] ?? "";
        return `${topic}<br/>${month}: ${fmtQuota(value ?? 0)}`;
      },
    },
    series: [
      {
        type: "heatmap",
        name: "Cuota",
        data: cells,
        itemStyle: { borderWidth: 0 },
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
