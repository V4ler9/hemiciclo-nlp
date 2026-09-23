import { useId } from "react";
import type { ResultChange } from "@/lib/changes";
import { fmtDelta, fmtMonth, fmtP, fmtR, monthShift } from "@/lib/format";

/**
 * Resultado de un cambio (fecha + delta) con sus estadísticos `r`, `p` y `n`
 * en un tooltip que aparece al pasar el ratón o al enfocar con el teclado
 * (también se activa con toque en móvil). Los valores quedan en el árbol de
 * accesibilidad mediante `aria-describedby`.
 */
export function ChangeChip({
  change,
  showDate = true,
}: {
  change: ResultChange;
  showDate?: boolean;
}) {
  const id = useId();
  const hasStats = Number.isFinite(change.r) && Number.isFinite(change.p) && change.n > 0;

  const statsLine = hasStats
    ? `r = ${fmtR(change.r)} · p = ${fmtP(change.p)} · n = ${change.n} meses`
    : "Estadísticos no disponibles";
  const rangeLine = hasStats
    ? `antes: ${fmtMonth(monthShift(change.fecha, -change.nAntes))} – ${fmtMonth(change.fecha)} (${change.nAntes} m) · ` +
      `después: ${fmtMonth(change.fecha)} – ${fmtMonth(monthShift(change.fecha, change.nDespues - 1))} (${change.nDespues} m)`
    : "";

  return (
    <span className="group/tip relative inline-flex items-baseline gap-2">
      {showDate && <span className="text-muted-foreground text-sm">{fmtMonth(change.fecha)}</span>}
      <span
        tabIndex={0}
        aria-describedby={id}
        className={
          "text-foreground cursor-help rounded-sm font-medium tabular-nums underline " +
          "decoration-dotted underline-offset-4 focus-visible:outline-2 " +
          "focus-visible:outline-foreground focus-visible:outline-offset-2"
        }
      >
        {fmtDelta(change.delta)}
      </span>
      <span
        id={id}
        role="tooltip"
        className={
          "pointer-events-none absolute bottom-full left-0 z-20 w-max max-w-xs rounded-md " +
          "border-border bg-popover text-popover-foreground border px-3 py-2 text-xs leading-relaxed " +
          "opacity-0 shadow-md transition-opacity group-focus-within/tip:opacity-100 group-hover/tip:opacity-100"
        }
      >
        <span className="block font-medium">{statsLine}</span>
        {rangeLine && <span className="text-muted-foreground mt-1 block">{rangeLine}</span>}
      </span>
    </span>
  );
}
