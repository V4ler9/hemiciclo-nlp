"use client";

import { useMemo, useState } from "react";
import { Chart } from "@/components/charts/chart";
import { ChangeChip } from "@/components/change-chip";
import type { TopicCard } from "@/lib/changes";
import { buildSparklineOption } from "@/lib/chart-options";
import { MESES_REGULARES_MIN } from "@/lib/constants";
import { fmtInt, fmtMonth } from "@/lib/format";

function TopicCardView({ card }: { card: TopicCard }) {
  const option = useMemo(() => buildSparklineOption(card), [card]);
  const label = card.label ?? `Tópico ${card.topic}`;
  const changesText = card.changes.length
    ? ` con ${card.changes.length} cambios: ${card.changes.map((change) => fmtMonth(change.fecha)).join(", ")}`
    : " sin cambios detectados";
  const ariaLabel = `Cuota mensual del tópico ${label}${changesText}.`;

  return (
    <li className="border-border flex flex-col rounded border p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-foreground truncate font-medium" title={label}>
          {label}
        </h3>
        <span className="text-muted-foreground shrink-0 text-xs tabular-nums">
          {fmtInt(card.size)} interv.
        </span>
      </div>
      {card.lowPower && (
        <span
          className="mt-1 w-fit rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[0.7rem] text-amber-900"
          title={`Menos de ${MESES_REGULARES_MIN} meses con 5 o más intervenciones (${card.mesesRegulares} meses): la cuota mensual es ruidosa`}
        >
          Baja potencia · {card.mesesRegulares} m
        </span>
      )}
      <Chart option={option} className="mt-3 h-24 w-full" ariaLabel={ariaLabel} />
      {card.changes.length > 0 ? (
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
          {card.changes.map((change) => (
            <li key={change.fecha}>
              <ChangeChip change={change} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground mt-3 text-xs">Sin cambios detectados</p>
      )}
    </li>
  );
}

/**
 * Rejilla de tópicos ordenada por magnitud del mayor cambio, con filtro de
 * series de baja potencia y estadísticos de cada cambio en tooltip.
 */
export function TopicGrid({ cards }: { cards: TopicCard[] }) {
  const [hideLowPower, setHideLowPower] = useState(false);
  const lowPowerCount = cards.filter((card) => card.lowPower).length;
  const visible = hideLowPower ? cards.filter((card) => !card.lowPower) : cards;
  const totalChanges = cards.reduce((total, card) => total + card.changes.length, 0);
  const seriesWithChanges = cards.filter((card) => card.changes.length > 0).length;

  return (
    <section aria-labelledby="topicos-heading" className="border-border mt-12 border-t pt-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2
            id="topicos-heading"
            className="text-muted-foreground text-xs font-medium tracking-[0.25em] uppercase"
          >
            Cambios por tópico
          </h2>
          <p className="text-muted-foreground mt-2 max-w-3xl text-sm">
            {totalChanges} cambios en la cuota de prevalencia de {seriesWithChanges} de los{" "}
            {cards.length} tópicos (PELT sobre la serie mensual de cada uno). Estos cambios son de{" "}
            <span className="text-foreground font-medium">prevalencia, no de tono</span>: el tono
            global está arriba. Ordenados por la magnitud del mayor cambio.
          </p>
        </div>
        <label className="text-muted-foreground flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={hideLowPower}
            onChange={(event) => setHideLowPower(event.target.checked)}
            className="accent-foreground size-4"
          />
          Ocultar baja potencia ({lowPowerCount})
        </label>
      </div>
      {visible.length > 0 ? (
        <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {visible.map((card) => (
            <TopicCardView key={card.topic} card={card} />
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground mt-6 text-sm">
          No queda ninguna serie visible con el filtro actual.
        </p>
      )}
    </section>
  );
}
