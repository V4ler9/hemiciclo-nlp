/** Esqueleto de carga mostrado mientras una sección consulta la API. */
export default function Loading() {
  return (
    <div className="animate-pulse space-y-4" aria-busy="true">
      <span className="sr-only">Cargando sección…</span>
      <div className="bg-muted h-9 w-2/3 rounded" />
      <div className="bg-muted h-4 w-1/3 rounded" />
      <div className="bg-muted h-48 rounded" />
    </div>
  );
}
