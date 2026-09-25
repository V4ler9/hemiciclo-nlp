"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef } from "react";
import { Chart } from "@/components/charts/chart";
import type { TopicCard } from "@/lib/changes";
import { buildTopicDetailOption } from "@/lib/chart-options";
import {
  fmtDecimal,
  fmtDelta,
  fmtInt,
  fmtMonth,
  fmtP,
  fmtQuota,
  fmtR,
  intervalLine,
} from "@/lib/format";

const HEAD = ["fecha", "Δ", "media antes → después", "r", "p", "n", "intervalo"];
const CELL = "py-1.5 pr-4 text-foreground";

/**
 * Diálogo nativo `<dialog>` con el gráfico ampliado de un tópico y la tabla
 * que respalda sus cambios (fecha, Δ, medias, `r`, `p`, `n` e intervalo; sin
 * `q`, que vive en Métricas — Q1c). Se cierra con `ESC`, el botón o el fondo.
 */
export function TopicDialog({ card, onClose }: { card: TopicCard | null; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const option = useMemo(() => (card ? buildTopicDetailOption(card) : null), [card]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (card && !dialog.open) dialog.showModal();
    if (!card && dialog.open) dialog.close();
  }, [card]);

  const heading = card ? (card.label ?? `Tópico ${card.topic}`) : "";
  const ariaLabel = card
    ? `Cuota mensual ampliada de ${heading} con ${card.changes.length} cambios detectados.`
    : "";

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialogRef.current) onClose();
      }}
      aria-labelledby="topic-dialog-title"
      className="border-border bg-background text-foreground fixed inset-0 m-auto max-h-[calc(100dvh-3rem)] w-[92vw] max-w-4xl overflow-auto rounded-lg border p-0 shadow-xl [&::backdrop]:bg-black/50"
    >
      {card && option && (
        <div className="p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2
              id="topic-dialog-title"
              className="text-foreground font-serif text-2xl font-semibold tracking-tight"
            >
              {heading}
            </h2>
            <p className="text-muted-foreground text-xs tabular-nums">
              tópico {card.topic} · {fmtInt(card.size)} intervenciones · {fmtQuota(card.size / 400)}
            </p>
          </div>

          <Chart option={option} className="mt-4 h-80 w-full" ariaLabel={ariaLabel} />

          {card.changes.length > 0 ? (
            <div
              role="region"
              aria-label={`Cambios que respaldan el tópico ${heading}`}
              tabIndex={0}
              className="border-border focus-visible:outline-foreground mt-5 max-h-64 overflow-auto rounded border focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              <table className="w-full text-sm tabular-nums">
                <thead className="bg-background sticky top-0">
                  <tr className="border-border text-muted-foreground border-b text-left text-xs tracking-wider uppercase">
                    {HEAD.map((column) => (
                      <th key={column} scope="col" className="py-2 pr-4 font-medium">
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {card.changes.map((change) => (
                    <tr key={change.fecha} className="border-border/60 border-b">
                      <td className={CELL}>{fmtMonth(change.fecha)}</td>
                      <td className={`${CELL} font-medium`}>{fmtDelta(change.delta)}</td>
                      <td className={CELL}>
                        {fmtDecimal(change.mediaAntes)} → {fmtDecimal(change.mediaDespues)}
                      </td>
                      <td className={CELL}>{fmtR(change.r)}</td>
                      <td className={CELL}>{fmtP(change.p)}</td>
                      <td className={CELL}>{change.n}</td>
                      <td className={`${CELL} text-muted-foreground text-xs whitespace-nowrap`}>
                        {intervalLine(change)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted-foreground mt-5 text-sm">
              Este tópico no tiene cambios de régimen detectados.
            </p>
          )}

          <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
            <Link
              href={`/evidencias?topico=${card.topic}`}
              onClick={onClose}
              className="border-border text-foreground hover:bg-muted focus-visible:outline-foreground rounded border px-3 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              Ver evidencias de este tópico →
            </Link>
            <button
              type="button"
              onClick={onClose}
              autoFocus
              className="border-border text-foreground hover:bg-muted focus-visible:outline-foreground rounded border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              Cerrar
            </button>
          </div>
        </div>
      )}
    </dialog>
  );
}
