import { BarChart, HeatmapChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import * as echarts from "echarts/core";

echarts.use([
  BarChart,
  HeatmapChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

/** Opción de gráfico derivada de la firma real de `setOption` (ECharts 6). */
export type ChartOption = Parameters<ReturnType<typeof echarts.init>["setOption"]>[0];

export { echarts };
