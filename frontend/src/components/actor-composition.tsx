"use client";

import { useMemo } from "react";
import { Chart } from "@/components/charts/chart";
import type { ActorChangeRow, ActorPoint } from "@/lib/api";
import { buildActorShareOption } from "@/lib/chart-options";
import { fmtDelta } from "@/lib/format";

const FAMILIES = ["PP", "PSOE", "Vox"] as const;

function contribution(row: ActorChangeRow): number {
  return (row.contribucion_dentro ?? 0) + (row.contribucion_composicion ?? 0);
}

/**
 * Acto 4: quién habla. La serie muestra la cuota de intervenciones de PP,
 * PSOE y Vox; la tabla descompone el cambio de share negativo de 2020-06 en
 * contribución intra-partido y de composición.
 */
export function ActorComposition({
  points,
  actorChanges,
}: {
  points: ActorPoint[];
  actorChanges: ActorChangeRow[];
}) {
  const option = useMemo(() => buildActorShareOption(points, [...FAMILIES]), [points]);
  const toneRows = useMemo(
    () =>
      actorChanges
        .filter(
          (row) =>
            row.serie === "tone" &&
            row.fecha.startsWith("2020-06") &&
            row.metrica === "negative_share" &&
            row.nivel === "partido" &&
            row.partido !== "__residual__"
        )
        .sort((a, b) => Math.abs(contribution(b)) - Math.abs(contribution(a)))
        .slice(0, 6),
    [actorChanges]
  );

  return (
    <section aria-labelledby="actores-home-heading" className="border-border mt-14 border-t pt-8">
      <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">Acto 4 · Quién habla</p>
      <h2
        id="actores-home-heading"
        className="text-foreground mt-2 font-serif text-3xl font-semibold tracking-tight"
      >
        La Cámara cambia antes de que cambie el tono
      </h2>
      <p className="text-foreground mt-3 max-w-3xl text-[0.95rem] leading-7">
        El PP pierde peso tras las elecciones de 2019; el PSOE lo recupera y Vox entra con fuerza
        en la XIV legislatura. Esa mezcla cambia el tono agregado incluso si cada partido hablara
        igual. La tabla inferior descompone el cambio de junio de 2020: cuánto aporta cada partido
        por su propio tono y cuánto por ganar o perder peso.
      </p>
      <Chart
        option={option}
        className="mt-5 h-72 w-full"
        ariaLabel="Cuota mensual de intervenciones de PP, PSOE y Vox entre 2015 y 2023, suavizada a seis meses."
      />
      <p className="text-muted-foreground mt-2 text-xs">
        Media móvil centrada de 6 meses ponderada por intervenciones: los meses con pocas
        intervenciones no distorsionan la tendencia.
      </p>
      <div
        role="region"
        aria-label="Aportación de cada partido al cambio de share negativo de junio de 2020"
        tabIndex={0}
        className="border-border focus-visible:outline-foreground mt-6 overflow-x-auto rounded border focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        <table className="w-full text-sm tabular-nums">
          <caption className="text-muted-foreground px-4 pt-4 pb-2 text-left text-xs">
            Aportación al cambio de share negativo de 2020-06 (pp). «Dentro» es el cambio de tono
            del partido; «composición» es el cambio de su peso.
          </caption>
          <thead>
            <tr className="border-border text-muted-foreground border-b text-left text-xs tracking-wider uppercase">
              <th scope="col" className="px-4 py-2 font-medium">Partido</th>
              <th scope="col" className="px-4 py-2 font-medium">Total</th>
              <th scope="col" className="px-4 py-2 font-medium">Dentro</th>
              <th scope="col" className="px-4 py-2 font-medium">Composición</th>
            </tr>
          </thead>
          <tbody>
            {toneRows.map((row) => (
              <tr key={row.partido} className="border-border/60 border-b">
                <td className="text-foreground px-4 py-2 font-medium">{row.partido}</td>
                <td className="text-foreground px-4 py-2 font-medium">
                  {fmtDelta(contribution(row) * 100)} pp
                </td>
                <td className="text-muted-foreground px-4 py-2">
                  {fmtDelta((row.contribucion_dentro ?? 0) * 100)} pp
                </td>
                <td className="text-muted-foreground px-4 py-2">
                  {fmtDelta((row.contribucion_composicion ?? 0) * 100)} pp
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-muted-foreground mt-4 max-w-3xl text-xs leading-relaxed">
        Vox aporta +8,0 pp: casi todo composición. El PP aporta +4,4 pp: sobre todo su propio
        endurecimiento. PSOE y UP moderan y restan. No es una radicalización uniforme; es un
        cambio de mezcla con un PP más negativo.
      </p>
    </section>
  );
}
