"use client";

import { useMemo } from "react";
import { Chart } from "@/components/charts/chart";
import type { SeriesPoint } from "@/lib/api";
import { buildOutliersOption, buildVolumeOption } from "@/lib/chart-options";
import { toTimeline } from "@/lib/changes";
import { fmtInt, fmtQuota } from "@/lib/format";

/** Gráficas de calidad: volumen mensual de intervenciones y tasa de outliers. */
export function QualityCharts({
  volume,
  outliers,
}: {
  volume: SeriesPoint[];
  outliers: SeriesPoint[];
}) {
  const volumePoints = useMemo(() => toTimeline(volume), [volume]);
  const outlierPoints = useMemo(() => toTimeline(outliers), [outliers]);
  const volumeOption = useMemo(() => buildVolumeOption(volumePoints), [volumePoints]);
  const outliersOption = useMemo(() => buildOutliersOption(outlierPoints), [outlierPoints]);

  const totalInterventions = volumePoints.reduce((sum, point) => sum + point.value, 0);
  const meanOutliers =
    outlierPoints.length > 0
      ? outlierPoints.reduce((sum, point) => sum + point.value, 0) / outlierPoints.length
      : 0;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <figure>
        <figcaption className="text-muted-foreground text-xs tracking-widest uppercase">
          Volumen mensual · {fmtInt(Math.round(totalInterventions))} intervenciones en{" "}
          {volumePoints.length} meses
        </figcaption>
        <Chart
          option={volumeOption}
          className="mt-3 h-56 w-full"
          ariaLabel={`Volumen mensual de intervenciones: ${fmtInt(Math.round(totalInterventions))} intervenciones repartidas en ${volumePoints.length} meses con sesión.`}
        />
      </figure>
      <figure>
        <figcaption className="text-muted-foreground text-xs tracking-widest uppercase">
          Tasa mensual de outliers · media {fmtQuota(meanOutliers)}
        </figcaption>
        <Chart
          option={outliersOption}
          className="mt-3 h-56 w-full"
          ariaLabel={`Tasa mensual de outliers de BERTopic, con media de ${fmtQuota(meanOutliers)}.`}
        />
      </figure>
    </div>
  );
}
