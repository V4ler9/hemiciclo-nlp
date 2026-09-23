/** Datos planos de un fallo de API, aptos para componer JSX. */
export interface ApiFailure {
  status: number | null;
  detail: string;
}

/**
 * Aviso accesible para fallos de la API al cargar una página.
 *
 * Distingue tres casos: artefacto ausente en el servidor (503), API caída o
 * inaccesible (status 0) y cualquier otro error HTTP. Recibe un registro plano
 * en lugar de una instancia de `Error`: pasar errores con cadena `cause` como
 * props provoca un fallo de React Flight (`frame.join is not a function`).
 */
export function ApiErrorNotice({ failure }: { failure: ApiFailure }) {
  let title = "Error al consultar la API";
  let hint = "Vuelve a cargar la página; si persiste, revisa los logs del servidor.";
  if (failure.status === 503) {
    title = "Artefacto no disponible";
    hint = "Falta el artefacto en reports/tables: regenera el pipeline de análisis.";
  } else if (failure.status === 0 || failure.status === null) {
    title = "API no disponible";
    hint = "Arranca el proyecto con npm run dev:all y vuelve a cargar.";
  }

  return (
    <div
      role="status"
      className="max-w-2xl rounded border border-amber-400 bg-amber-50 px-4 py-3 text-sm"
    >
      <p className="font-medium text-amber-950">{title}</p>
      <p className="mt-1 text-amber-900">{failure.detail}</p>
      <p className="mt-2 text-amber-900">{hint}</p>
    </div>
  );
}
