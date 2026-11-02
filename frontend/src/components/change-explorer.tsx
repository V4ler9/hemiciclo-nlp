"use client";

import { useMemo, useState } from "react";
import { Chart } from "@/components/charts/chart";
import type { ActorChangeRow, HomeChange } from "@/lib/api";
import { buildChangeTimelineOption } from "@/lib/chart-options";
import { fmtDecimal, fmtDelta, fmtMonth, fmtP } from "@/lib/format";
import {
  CHANGE_TYPE_COLORS,
  CHANGE_TYPE_LABELS,
  type ChangePeriod,
  type ChangeType,
  availableActors,
  changeType,
  filterChanges,
  indexActorChanges,
  topActorForChange,
} from "@/lib/home";

const PERIODS: { value: ChangePeriod; label: string }[] = [
  { value: "todos", label: "Todo el periodo" },
  { value: "2015-2017", label: "2015-2017" },
  { value: "2018-2020", label: "2018-2020" },
  { value: "2021-2023", label: "2021-2023" },
];

/**
 * Cierre interactivo: timeline filtrable de los 45 cambios significativos.
 * El tamaño codifica el impacto (|Δ| × intervenciones/mes); el color, el tipo
 * de episodio. La tabla inferior es el respaldo accesible del canvas y muestra
 * también el cambio de tono, que no se pinta en el scatter.
 */
export function ChangeExplorer({
  changes,
  actorChanges,
}: {
  changes: HomeChange[];
  actorChanges: ActorChangeRow[];
}) {
  const [type, setType] = useState<ChangeType | "todos">("todos");
  const [actor, setActor] = useState<string>("todos");
  const [period, setPeriod] = useState<ChangePeriod>("todos");
  const index = useMemo(() => indexActorChanges(actorChanges), [actorChanges]);
  const actors = useMemo(() => availableActors(index), [index]);
  const filtered = useMemo(
    () => filterChanges(changes, index, { type, actor, period }),
    [changes, index, type, actor, period]
  );
  const option = useMemo(() => buildChangeTimelineOption(filtered, index), [filtered, index]);
  const topics = filtered.filter((change) => change.serie === "topic" && change.impacto !== null);

  return (
    <section aria-labelledby="explorador-heading" className="border-border mt-14 border-t pt-8">
      <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">Cierre · El mapa</p>
      <h2
        id="explorador-heading"
        className="text-foreground mt-2 font-serif text-3xl font-semibold tracking-tight"
      >
        Los 45 cambios significativos, uno a uno
      </h2>
      <p className="text-foreground mt-3 max-w-3xl text-[0.95rem] leading-7">
        Cada punto es un cambio de cuota que supera Benjamini-Hochberg. El tamaño codifica el
        impacto absoluto (|Δ| × intervenciones/mes) para no sobrevalorar tópicos pequeños; el
        color, el tipo de episodio. Filtra por tipo, actor principal o periodo. El cambio de tono
        de 2020-06 vive en el acto 2 y se incluye en la tabla.
      </p>

      <div className="mt-5 flex flex-wrap items-end gap-4">
        <label
          htmlFor="explorer-type"
          className="text-muted-foreground flex flex-col gap-1 text-xs"
        >
          Tipo
          <select
            id="explorer-type"
            value={type}
            onChange={(event) => setType(event.target.value as ChangeType | "todos")}
            className="border-border bg-background text-foreground focus-visible:outline-foreground rounded border px-2 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            <option value="todos">Todos</option>
            {(Object.keys(CHANGE_TYPE_LABELS) as ChangeType[]).map((key) => (
              <option key={key} value={key}>
                {CHANGE_TYPE_LABELS[key]}
              </option>
            ))}
          </select>
        </label>
        <label
          htmlFor="explorer-actor"
          className="text-muted-foreground flex flex-col gap-1 text-xs"
        >
          Actor principal
          <select
            id="explorer-actor"
            value={actor}
            onChange={(event) => setActor(event.target.value)}
            className="border-border bg-background text-foreground focus-visible:outline-foreground rounded border px-2 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            <option value="todos">Todos</option>
            {actors.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label
          htmlFor="explorer-period"
          className="text-muted-foreground flex flex-col gap-1 text-xs"
        >
          Periodo
          <select
            id="explorer-period"
            value={period}
            onChange={(event) => setPeriod(event.target.value as ChangePeriod)}
            className="border-border bg-background text-foreground focus-visible:outline-foreground rounded border px-2 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            {PERIODS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <p className="text-muted-foreground text-sm tabular-nums" aria-live="polite">
          {filtered.length} de {changes.length} cambios
        </p>
      </div>

      <ul className="text-muted-foreground mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {(Object.keys(CHANGE_TYPE_LABELS) as ChangeType[]).map((key) => (
          <li key={key} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="size-2 rounded-full"
              style={{ backgroundColor: CHANGE_TYPE_COLORS[key] }}
            />
            {CHANGE_TYPE_LABELS[key]}
          </li>
        ))}
      </ul>

      {topics.length > 0 ? (
        <Chart
          option={option}
          className="mt-4 h-80 w-full"
          ariaLabel={`Timeline de ${topics.length} cambios de tópico; el tamaño codifica el impacto y el color el tipo de episodio.`}
        />
      ) : (
        <p className="text-muted-foreground mt-4 text-sm">
          No hay cambios de tópico con estos filtros. La tabla de abajo incluye el tono y los
          cambios descartados por el filtro.
        </p>
      )}

      <div
        role="region"
        aria-label="Tabla de los cambios significativos filtrados"
        tabIndex={0}
        className="border-border focus-visible:outline-foreground mt-6 max-h-96 overflow-auto rounded border focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        <table className="w-full text-sm tabular-nums">
          <caption className="text-muted-foreground px-4 pt-4 pb-2 text-left text-xs">
            Cambios significativos tras BH. Δ en pp de cuota de tópico (el tono, en `senti_n`);
            impacto = |Δ| × intervenciones/mes; «—» en el tono.
          </caption>
          <thead className="bg-background sticky top-0">
            <tr className="border-border text-muted-foreground border-b text-left text-xs tracking-wider uppercase">
              <th scope="col" className="px-4 py-2 font-medium">Fecha</th>
              <th scope="col" className="px-4 py-2 font-medium">Serie</th>
              <th scope="col" className="px-4 py-2 font-medium">Δ</th>
              <th scope="col" className="px-4 py-2 font-medium">q</th>
              <th scope="col" className="px-4 py-2 font-medium">Impacto</th>
              <th scope="col" className="px-4 py-2 font-medium">Actor principal</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((change) => {
              const top = topActorForChange(change, index);
              return (
                <tr
                  key={`${change.serie}-${change.serie_id}-${change.fecha}`}
                  className="border-border/60 border-b"
                >
                  <td className="text-foreground px-4 py-2 whitespace-nowrap">
                    {fmtMonth(change.fecha)}
                  </td>
                  <td className="text-foreground px-4 py-2">
                    <span className="flex items-center gap-2">
                      <span
                        aria-hidden="true"
                        className="size-2 shrink-0 rounded-full"
                        style={{ backgroundColor: CHANGE_TYPE_COLORS[changeType(change)] }}
                      />
                      {change.serie === "tone" ? "Tono global" : change.label}
                    </span>
                  </td>
                  <td className="text-foreground px-4 py-2 font-medium">
                    {change.serie === "tone"
                      ? fmtDelta(change.delta)
                      : `${fmtDelta(change.delta * 100)} pp`}
                  </td>
                  <td className="text-muted-foreground px-4 py-2">{fmtP(change.q)}</td>
                  <td className="text-muted-foreground px-4 py-2">
                    {change.impacto === null ? "—" : fmtDecimal(change.impacto, 2)}
                  </td>
                  <td className="text-muted-foreground px-4 py-2">{top?.partido ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
