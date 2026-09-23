"use client";

import { useMemo } from "react";
import { Chart } from "@/components/charts/chart";
import { ChangeChip } from "@/components/change-chip";
import type { ToneView } from "@/lib/changes";
import { buildToneOption } from "@/lib/chart-options";
import { fmtDecimal, fmtMonth } from "@/lib/format";

/**
 * Héroe de la portada: serie mensual del tono global con las líneas de cada
 * cambio detectado y una ficha por cambio (fecha, medias antes/después y
 * estadísticos `r`, `p`, `n` en el tooltip del delta).
 */
export function ToneHero({ view }: { view: ToneView }) {
  const option = useMemo(() => buildToneOption(view.points, view.changes), [view]);
  const first = view.points[0]?.month;
  const last = view.points[view.points.length - 1]?.month;
  const ariaLabel =
    first && last
      ? `Tono medio mensual de ${fmtMonth(first)} a ${fmtMonth(last)} con ${view.changes.length} cambios detectados: ${view.changes.map((change) => fmtMonth(change.fecha)).join(", ")}.`
      : "Tono medio mensual.";

  return (
    <section aria-labelledby="tono-heading" className="mt-10">
      <h2
        id="tono-heading"
        className="text-muted-foreground text-xs font-medium tracking-[0.25em] uppercase"
      >
        Cambios de tono detectados
      </h2>
      <p className="text-muted-foreground mt-2 max-w-3xl text-sm">
        Media mensual de <code className="font-mono text-xs">senti_n</code> (escala 0–6) en el
        Pleno. Las líneas discontinuas marcan los {view.changes.length} cambios de régimen
        detectados con PELT; pasa el ratón por el delta de cada ficha (o enfócalo con el teclado)
        para ver <span className="text-foreground font-medium">r</span>,{" "}
        <span className="text-foreground font-medium">p</span> y el intervalo comparado.
      </p>
      <Chart option={option} className="mt-4 h-72 w-full" ariaLabel={ariaLabel} />
      <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {view.changes.map((change) => (
          <li key={change.fecha} className="border-border rounded border p-4">
            <p className="text-muted-foreground text-[0.7rem] tracking-[0.2em] uppercase">
              Cambio de tono
            </p>
            <p className="text-foreground mt-1 font-serif text-2xl font-semibold">
              {fmtMonth(change.fecha)}
            </p>
            <p className="text-muted-foreground mt-2 text-sm tabular-nums">
              media <span className="text-foreground">{fmtDecimal(change.mediaAntes)}</span> →{" "}
              <span className="text-foreground">{fmtDecimal(change.mediaDespues)}</span>
            </p>
            <div className="mt-3">
              <ChangeChip change={change} showDate={false} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
