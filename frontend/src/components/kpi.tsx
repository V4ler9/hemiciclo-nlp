/** Indicador numérico con etiqueta en versalitas y valor en serif. */
export function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground text-xs tracking-widest uppercase">{label}</dt>
      <dd className="text-foreground mt-1 font-serif text-3xl font-semibold tabular-nums">
        {value}
      </dd>
    </div>
  );
}
