"use client";

import { useMemo } from "react";
import { Chart } from "@/components/charts/chart";
import type { Episode, ToneCounterfactualPoint } from "@/lib/api";
import { buildToneCompositionOption } from "@/lib/chart-options";
import { fmtDecimal, fmtDelta, fmtMonth } from "@/lib/format";

/**
 * Acto 2: share negativo real frente al contrafactual que fija las cuotas de
 * partido de las legislaturas X-XIII. La brecha entre líneas es el efecto de
 * composición; no es una atribución causal.
 */
export function HomeTone({
  points,
  episode,
}: {
  points: ToneCounterfactualPoint[];
  episode: Episode | null;
}) {
  const option = useMemo(() => buildToneCompositionOption(points), [points]);
  const first = points[0];
  const last = points[points.length - 1];
  const tone = episode?.tono ?? null;
  const negative = tone?.intervalos.find((item) => item.metrica === "negative_share");
  const ariaLabel =
    first && last
      ? `Share negativo real y contrafactual por composición, trimestral, de ${fmtMonth(first.month)} a ${fmtMonth(last.month)}.`
      : "Share negativo real y contrafactual por composición.";

  return (
    <section aria-labelledby="home-tono-heading" className="border-border mt-14 border-t pt-8">
      <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">Acto 2 · El tono</p>
      <h2
        id="home-tono-heading"
        className="text-foreground mt-2 font-serif text-3xl font-semibold tracking-tight"
      >
        El tono cae, pero no porque todos hablen peor
      </h2>
      <p className="text-foreground mt-3 max-w-3xl text-[0.95rem] leading-7">
        La línea continua es el share trimestral suavizado de intervenciones negativas. La discontinua
        mantiene fija la mezcla de partidos del segmento pre-cambio (2015-01 – 2020-05) y deja
        variar solo el tono dentro de cada partido. La brecha es una comparación descriptiva con esa
        mezcla; el efecto del cambio de 2020-06 se descompone en la tabla del acto 4.
      </p>
      <Chart option={option} className="mt-5 h-80 w-full" ariaLabel={ariaLabel} />
      <p className="text-muted-foreground mt-2 text-xs">
        Media móvil de 3 trimestres ponderada por intervenciones: la sesión atípica de marzo de
        2020 (95 intervenciones) se diluye en la serie. La lectura se apoya en el cambio de régimen
        de 2020-06, no en un mes aislado.
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-muted-foreground">Share negativo 2020-06</dt>
          <dd className="text-foreground mt-1 font-serif text-2xl font-semibold tabular-nums">
            {tone?.delta_share_negativo !== null && tone?.delta_share_negativo !== undefined
              ? `${fmtDelta(tone.delta_share_negativo * 100)} pp`
              : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">IC 95 %</dt>
          <dd className="text-foreground mt-1 font-serif text-2xl font-semibold tabular-nums">
            {negative
              ? `[${fmtDecimal((negative.ic_inf ?? 0) * 100, 1)}; ${fmtDecimal((negative.ic_sup ?? 0) * 100, 1)}]`
              : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">senti_n 2020-06 (intervención)</dt>
          <dd className="text-foreground mt-1 font-serif text-2xl font-semibold tabular-nums">
            {tone?.delta_senti_n !== null && tone?.delta_senti_n !== undefined
              ? fmtDelta(tone.delta_senti_n)
              : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Base del contrafactual</dt>
          <dd className="text-foreground mt-1 text-sm tabular-nums">
            {first ? `${first.base_start} – ${first.base_end}` : "—"}
          </dd>
        </div>
      </dl>
      <p className="text-muted-foreground mt-4 max-w-3xl text-xs leading-relaxed">
        Lectura: el cambio de 2020-06 no es una radicalización uniforme. Vox gana peso y aporta
        +8,0 pp al share negativo; el PP aporta +4,4 pp, sobre todo porque su propio tono se
        endurece; PSOE y UP moderan y restan. El detalle está en el acto 4.
      </p>
    </section>
  );
}
