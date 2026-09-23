"use client";

import { useMemo } from "react";
import { Chart } from "@/components/charts/chart";
import type { HeatmapData } from "@/lib/changes";
import { buildTopicHeatmapOption } from "@/lib/chart-options";
import { fmtQuota } from "@/lib/format";

/** Heatmap «cuota relativa por tópico y mes» (top tópicos por tamaño). */
export function TopicHeatmap({ data }: { data: HeatmapData }) {
  const option = useMemo(() => buildTopicHeatmapOption(data), [data]);
  const ariaLabel = `Mapa de calor de cuota mensual de los ${data.labels.length} tópicos mayores, de ${data.months[0] ?? ""} a ${data.months[data.months.length - 1] ?? ""}; máxima cuota ${fmtQuota(data.max)}.`;

  return (
    <figure className="mt-4">
      <Chart option={option} className="h-[32rem] w-full" ariaLabel={ariaLabel} />
      <figcaption className="text-muted-foreground mt-2 text-xs">
        Cuota relativa por tópico y mes (top {data.labels.length} por intervenciones). Celdas
        vacías: meses sin datos. Misma lectura que la figura histórica{" "}
        <code className="font-mono">fig_heatmap_topicos</code>.
      </figcaption>
    </figure>
  );
}
