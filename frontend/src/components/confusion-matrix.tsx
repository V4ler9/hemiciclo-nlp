"use client";

import { useMemo, useState } from "react";
import { type ConfusionMatrix } from "@/lib/api";

const LEVELS = [
  { id: "senti_3", label: "3 bandas (Negativa · Neutral · Positiva)" },
  { id: "senti_6", label: "6 clases (taxonomía completa)" },
] as const;

function MatrixTable({ matrix }: { matrix: ConfusionMatrix }) {
  const max = Math.max(...matrix.values.flat(), 1);
  return (
    <div
      role="region"
      aria-label="Matriz de confusión"
      tabIndex={0}
      className="focus-visible:outline-foreground overflow-x-auto focus-visible:outline-2 focus-visible:outline-offset-2"
    >
      <table className="w-full text-sm tabular-nums">
        <caption className="text-muted-foreground pb-3 text-left text-xs">
          Filas: clase real · columnas: etiqueta asignada por el modelo. Intensidad proporcional al
          recuento.
        </caption>
        <thead>
          <tr className="border-border text-muted-foreground border-b text-left text-xs tracking-wider uppercase">
            <th scope="col" className="py-2 pr-4 font-medium">
              Real \ asignada
            </th>
            {matrix.columns.map((column) => (
              <th key={column} scope="col" className="py-2 pr-4 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.index.map((rowLabel, rowIndex) => (
            <tr key={rowLabel} className="border-border/60 border-b">
              <th scope="row" className="text-foreground py-1.5 pr-4 text-left font-medium">
                {rowLabel}
              </th>
              {matrix.values[rowIndex]?.map((value, columnIndex) => (
                <td
                  key={`${rowLabel}-${String(matrix.columns[columnIndex])}`}
                  className="text-foreground py-1.5 pr-4"
                  style={{
                    backgroundColor: `rgb(24 24 27 / ${(0.06 + (0.29 * value) / max).toFixed(3)})`,
                  }}
                >
                  {value}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Matriz de conmutable entre niveles con selector accesible de radio. */
export function ConfusionPicker({ matrices }: { matrices: Record<string, ConfusionMatrix> }) {
  const [level, setLevel] = useState<(typeof LEVELS)[number]["id"]>("senti_3");
  const matrix = matrices[level];
  const options = useMemo(
    () => LEVELS.map((entry) => ({ ...entry, matrix: matrices[entry.id] })),
    [matrices]
  );

  if (!matrix) {
    return <p className="text-muted-foreground text-sm">Matrices no disponibles.</p>;
  }

  return (
    <div>
      <fieldset className="flex flex-wrap gap-x-6 gap-y-2">
        <legend className="sr-only">Nivel de la matriz de confusión</legend>
        {options.map(
          (option) =>
            option.matrix && (
              <label
                key={option.id}
                className="text-muted-foreground flex cursor-pointer items-center gap-2 text-sm"
              >
                <input
                  type="radio"
                  name="confusion-level"
                  value={option.id}
                  checked={level === option.id}
                  onChange={() => setLevel(option.id)}
                  className="accent-foreground size-4"
                />
                {option.label}
              </label>
            )
        )}
      </fieldset>
      <div className="mt-4">
        <MatrixTable matrix={matrix} />
      </div>
    </div>
  );
}
