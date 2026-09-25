import { LABEL_MAX_LENGTH } from "@/lib/constants";

const MONTH = new Intl.DateTimeFormat("es-ES", {
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

function parseIso(value: string): [number, number, number] {
  const [year = NaN, month = NaN, day = NaN] = value.slice(0, 10).split("-").map(Number);
  if (!Number.isFinite(year + month + day)) {
    throw new RangeError(`Fecha ISO no válida: ${value}`);
  }
  return [year, month, day];
}

function toDate(value: string | Date): Date {
  if (value instanceof Date) return value;
  const [year, month, day] = parseIso(value);
  return new Date(Date.UTC(year, month - 1, day));
}

/** «oct 2015» — etiqueta mensual estable para ejes, fichas y tooltips. */
export function fmtMonth(value: string | Date): string {
  return MONTH.format(toDate(value));
}

/** Desplaza una fecha ISO en meses (negativo = atrás). */
export function monthShift(value: string, months: number): Date {
  const [year, month] = parseIso(value);
  return new Date(Date.UTC(year, month - 1 + months, 1));
}

/** Delta con signo y tres decimales («+0,401» / «−0,306»). */
export function fmtDelta(value: number): string {
  const digits = Math.abs(value).toLocaleString("es-ES", {
    minimumFractionDigits: 3,
    maximumFractionDigits: 3,
  });
  return `${value >= 0 ? "+" : "−"}${digits}`;
}

/** Decimal en notación española (coma) con hasta tres decimales. */
export function fmtDecimal(value: number, digits = 3): string {
  if (!Number.isFinite(value)) return "n/d";
  return value.toLocaleString("es-ES", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** p-valor: tres decimales o notación exponencial para valores muy pequeños. */
export function fmtP(value: number): string {
  if (!Number.isFinite(value)) return "n/d";
  if (Math.abs(value) < 0.001) return value.toExponential(2).replace(".", ",");
  return fmtDecimal(value, 3);
}

/** Coeficiente r con signo y tres decimales («−0,623»). */
export function fmtR(value: number): string {
  if (!Number.isFinite(value)) return "n/d";
  return fmtDecimal(value, 3);
}

/** Entero con separador de miles español («30.027»). */
export function fmtInt(value: number): string {
  return value.toLocaleString("es-ES");
}

/** Cuota fraccionaria como porcentaje («3,2 %»). */
export function fmtQuota(value: number): string {
  if (!Number.isFinite(value)) return "n/d";
  return `${(value * 100).toLocaleString("es-ES", { maximumFractionDigits: 1 })} %`;
}

/**
 * Etiqueta de tópico truncada para ejes de gráficos (misma regla que
 * `charts.py::_short_label`: LABEL_MAX_LENGTH con «…»).
 */
export function fmtTopicLabel(label: string | null, topicId: number): string {
  const text = label ?? `tópico ${topicId}`;
  return text.length > LABEL_MAX_LENGTH ? `${text.slice(0, LABEL_MAX_LENGTH - 1)}…` : text;
}

import type { ResultChange } from "@/lib/changes";

/** Línea de estadísticos de un cambio: `r`, `p` y meses en juego (o aviso). */
export function statsLine(change: ResultChange): string {
  const available = Number.isFinite(change.r) && Number.isFinite(change.p) && change.n > 0;
  if (!available) return "Estadísticos no disponibles";
  return `r = ${fmtR(change.r)} · p = ${fmtP(change.p)} · n = ${change.n} meses`;
}

/** Intervalo temporal comparado por un cambio (ventanas antes y después). */
export function intervalLine(change: ResultChange): string {
  if (change.nAntes <= 0 || change.nDespues <= 0) return "";
  const antesInicio = fmtMonth(monthShift(change.fecha, -change.nAntes));
  const antesFin = fmtMonth(monthShift(change.fecha, -1));
  const despuesFin = fmtMonth(monthShift(change.fecha, change.nDespues - 1));
  return (
    `antes: ${antesInicio} – ${antesFin} (${change.nAntes} m) · ` +
    `después: ${fmtMonth(change.fecha)} – ${despuesFin} (${change.nDespues} m)`
  );
}
