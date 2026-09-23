"use client";

import { useMemo } from "react";
import { Chart } from "@/components/charts/chart";
import { buildEventsOption } from "@/lib/chart-options";
import type { EventsView } from "@/lib/events";

/** Heatmap «asociación exploratoria evento × tópico» (Spearman ρ; D-09). */
export function EventsHeatmap({ view }: { view: EventsView }) {
  const option = useMemo(() => buildEventsOption(view), [view]);
  const significant = view.q.filter((row) =>
    row.some((value) => value !== null && value < 0.05)
  ).length;
  const ariaLabel =
    `Mapa de calor de asociación exploratoria de Spearman entre ${view.columns.length} eventos y los ${view.labels.length} tópicos con mayor ρ absoluto, con rango simétrico de ${view.maxAbs.toFixed(2)}. ` +
    (significant > 0
      ? `${significant} filas con algún contraste significativo tras BH.`
      : "Ningún contraste supera q < 0,05 tras Benjamini-Hochberg.");

  return (
    <figure className="mt-4">
      <Chart option={option} className="h-[34rem] w-full" ariaLabel={ariaLabel} />
      <figcaption className="text-muted-foreground mt-2 text-xs">
        Asociación exploratoria (Spearman ρ) evento × tópico; ★ marca q &lt; 0,05 tras
        Benjamini-Hochberg. Lectura equivalente a{" "}
        <code className="font-mono">fig_eventos_correlaciones</code>.
      </figcaption>
    </figure>
  );
}
