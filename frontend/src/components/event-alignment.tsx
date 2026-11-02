"use client";

import { useMemo } from "react";
import { Chart } from "@/components/charts/chart";
import type { EventAlignmentRow } from "@/lib/api";
import { buildEventAlignmentOption } from "@/lib/chart-options";
import { fmtDelta, fmtP, fmtQuota } from "@/lib/format";
import { hypothesisLabel } from "@/lib/home";

/**
 * Acto 5: qué explican los eventos. El gráfico muestra las 14 hipótesis
 * pre-especificadas; en rojo las que superan Benjamini-Hochberg. La lista
 * inferior evita depender del canvas y explicita el resultado nulo del
 * calendario electoral y del tono local.
 */
export function EventAlignment({ rows }: { rows: EventAlignmentRow[] }) {
  const option = useMemo(() => buildEventAlignmentOption(rows), [rows]);
  const significant = useMemo(
    () => rows.filter((row) => row.significativo_bh === 1),
    [rows]
  );

  return (
    <section aria-labelledby="eventos-home-heading" className="border-border mt-14 border-t pt-8">
      <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">Acto 5 · Los eventos</p>
      <h2
        id="eventos-home-heading"
        className="text-foreground mt-2 font-serif text-3xl font-semibold tracking-tight"
      >
        Los shocks sí; el calendario electoral, poco
      </h2>
      <p className="text-foreground mt-3 max-w-3xl text-[0.95rem] leading-7">
        Cada barra es una hipótesis fijada antes de mirar el resultado: un episodio y una serie.
        Comparamos seis meses antes y después del mes ancla, con permutación de la fecha y
        corrección de Benjamini-Hochberg dentro de cada familia. En rojo, las que superan q &lt;
        0,05.
      </p>
      <Chart
        option={option}
        className="mt-5 h-[30rem] w-full"
        ariaLabel={`Delta de las ${rows.length} hipótesis del event study; ${significant.length} superan Benjamini-Hochberg.`}
      />
      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <div className="border-border rounded border p-4">
          <h3 className="text-muted-foreground text-xs tracking-[0.2em] uppercase">
            Superan BH ({significant.length} de {rows.length})
          </h3>
          <ul className="mt-3 space-y-3 text-sm">
            {significant.map((row) => (
              <li key={row.hipotesis_id}>
                <p className="text-foreground font-medium">{hypothesisLabel(row)}</p>
                <p className="text-muted-foreground mt-0.5 text-xs tabular-nums">
                  Δ {fmtDelta(row.delta * 100)} pp · q = {fmtP(row.q)} ·{" "}
                  {fmtQuota(row.valor_antes)} → {fmtQuota(row.valor_despues)}
                </p>
              </li>
            ))}
          </ul>
        </div>
        <div className="text-muted-foreground space-y-3 text-xs leading-relaxed">
          <p>
            <span className="text-foreground font-medium">Lectura.</span> La COVID dispara sanidad
            y ERTE; la guerra dispara el tópico de Ucrania. La formación del Gobierno de Rajoy
            coincide con una caída de la confrontación, no con una subida: el fin del bloqueo
            descomprime el cajón de sastre. Las elecciones de 2015 y 2019-04 no muestran un efecto
            consistente; el episodio de 2016 se testea como formación de Gobierno y el de 2019-11
            se agrupa con la XIV legislatura y la COVID.
          </p>
          <p>
            <span className="text-foreground font-medium">El tono.</span> Las dos hipótesis de
            tono no superan el placebo local de seis meses. Su evidencia robusta es otra: el
            contraste de segmentos completos (share negativo +7,5 pp, IC 95 % [6,3; 8,6]) y la
            descomposición de actores del acto 4. No se fuerza el relato: el event study no
            confirma el tono; la serie completa y la composición sí.
          </p>
          <p>
            <span className="text-foreground font-medium">El nulo anterior.</span> El contraste
            exploratorio de la v1 (472 pares, ventana ±3 meses) no superaba BH. Este event study
            local es el primario; la diferencia es de diseño —unidad episodio, ventana pre/post y
            familia pre-especificada—, no de datos.
          </p>
        </div>
      </div>
    </section>
  );
}
