import { ApiErrorNotice, type ApiFailure } from "@/components/api-error";
import { EventsHeatmap } from "@/components/events-heatmap";
import {
  ApiError,
  type EventRow,
  getEventRelations,
  getEvents,
  getTopics,
  isDynamicUsage,
} from "@/lib/api";
import { buildEventsView, type EventsView } from "@/lib/events";
import { fmtMonth } from "@/lib/format";

interface MethodBundle {
  events: EventRow[];
  view: EventsView;
}

async function loadMethod(): Promise<MethodBundle> {
  const [events, relations, topics] = await Promise.all([
    getEvents(),
    getEventRelations(),
    getTopics(),
  ]);
  return { events, view: buildEventsView(relations, events, topics) };
}

function DocSection({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="border-border mt-10 border-t pt-8">
      <h2 id={id} className="text-foreground font-serif text-2xl font-semibold tracking-tight">
        {title}
      </h2>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-foreground max-w-3xl text-[0.95rem] leading-7">{children}</p>;
}

function Note({ children }: { children: React.ReactNode }) {
  return <p className="text-muted-foreground max-w-3xl text-sm">{children}</p>;
}

function EventsTable({ events }: { events: EventRow[] }) {
  const head = ["evento", "fecha", "tipo", "fuente"];
  const cell = "py-1.5 pr-4 text-foreground";
  return (
    <div
      role="region"
      aria-label="Tabla de eventos del repositorio"
      tabIndex={0}
      className="focus-visible:outline-foreground overflow-x-auto focus-visible:outline-2 focus-visible:outline-offset-2"
    >
      <table className="w-full max-w-3xl text-sm">
        <thead>
          <tr className="border-border text-muted-foreground border-b text-left text-xs tracking-wider uppercase">
            {head.map((column) => (
              <th key={column} scope="col" className="py-2 pr-4 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={`${event.evento}-${event.fecha}`} className="border-border/60 border-b">
              <td className={cell}>{event.evento}</td>
              <td className={cell}>{fmtMonth(event.fecha)}</td>
              <td className={cell}>{event.tipo}</td>
              <td className={cell}>{event.fuente}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function MetodologiaPage() {
  let bundle: MethodBundle | null = null;
  let failure: ApiFailure | null = null;
  try {
    bundle = await loadMethod();
  } catch (cause) {
    if (isDynamicUsage(cause)) throw cause;
    console.error("[metodologia] no se pudo cargar el material metodológico:", cause);
    failure = {
      status: cause instanceof ApiError ? cause.status : null,
      detail: cause instanceof Error ? cause.message : "Error inesperado",
    };
  }

  return (
    <div>
      <header className="border-border border-b pb-6">
        <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">
          Cómo se obtienen los resultados
        </p>
        <h1 className="text-foreground mt-3 font-serif text-4xl font-semibold tracking-tight">
          Metodología
        </h1>
      </header>

      <DocSection id="alcance-heading" title="Alcance de este panel">
        <P>
          Este panel presenta la evolución temática y tonal del Pleno del Congreso de los Diputados
          entre enero de 2015 y febrero de 2023. Cada cifra que se muestra procede de artefactos
          precalculados que se versionan en <code className="font-mono">reports/tables/</code> y
          cada decisión metodológica está registrada con su identificador (D-xx) en{" "}
          <code className="font-mono">docs/DECISIONS.md</code>. La interfaz no ejecuta ningún
          modelo: solo lee y presenta.
        </P>
      </DocSection>

      <DocSection id="corpus-heading" title="Corpus y limpieza">
        <P>
          El corpus son las intervenciones del Pleno exportadas en ParlaMint-ES:{" "}
          <strong>30.027 intervenciones</strong> sobre una rejilla mensual de 98 meses, de los
          cuales <strong>82 tienen sesión</strong>. La limpieza retira frases procedimentales, notas
          y ruido, y la segmentación conserva una fila por intervención con su orador, grupo y
          fecha.
        </P>
        <Note>
          Los meses sin actividad se mantienen en la rejilla con{" "}
          <code className="font-mono">has_session</code> a falso y quedan fuera de todas las
          agregaciones y del modelado (D-28).
        </Note>
      </DocSection>

      <DocSection id="topicos-heading" title="Modelado de tópicos">
        <P>
          Los tópicos se obtienen con BERTopic sobre embeddings multilingües
          (multilingual-e5-large). La rejilla de <strong>36 combinaciones</strong> se evalúa con la
          regla de D-32: se descartan las combinaciones con más de 40 % de outliers o fuera del
          rango de 20 a 60 tópicos, se maximiza la coherencia <em>c_v</em> y los empates se
          resuelven por diversidad. La selección final —min_topic_size = 100, n_neighbors = 30,
          min_samples = 10— produce <strong>58 tópicos</strong>, una tasa de outliers del{" "}
          <strong>32,0 %</strong>, <em>c_v</em> = 0,7546 y diversidad = 0,9414.
        </P>
        <P>
          El anexo de sensibilidad (D-39) contrasta e5-large frente a bge-m3 sobre 15.233
          intervenciones comparables: ARI = 0,711 y NMI = 0,875, es decir, la estructura temática es
          robusta al cambio de embeddings.
        </P>
        <Note>
          Las etiquetas de los tópicos están generadas con asistencia de LLM (D-25); la pestaña
          Evidencias muestra para cada una si ha sido revisada por una persona. La rejilla completa
          y el anexo de embeddings están en Métricas.
        </Note>
      </DocSection>

      <DocSection id="sentimiento-heading" title="Medición y validación del tono">
        <P>
          El tono se mide con la escala <code className="font-mono">senti_n</code> (0–6) de
          ParlaSent, corregida y contrastada con un LLM sobre una muestra revisada por personas
          (D-36 y D-37). Frente a la referencia humana, la métrica reponderada alcanza{" "}
          <strong>0,675 en tres bandas</strong> y <strong>0,374 en el nivel de seis clases</strong>,
          con κ cuadrática de 0,656 y 0,701 respectivamente.
        </P>
        <P>
          <strong>Limitación relevante:</strong> el nivel de seis clases es poco fiable y su error
          se propaga a las series de tono (D-37). Por eso el tono global de la portada se interpreta
          como una señal agregada y no como una clasificación exacta de cada intervención. Los
          intervalos bootstrap, el acuerdo a tres bandas y las matrices de confusión están en
          Métricas; el informe completo de validación se puede abrir tal cual se generó{" "}
          <a
            href="/informes/validacion_sentimiento_revision.html"
            target="_blank"
            rel="noreferrer"
            className="text-foreground focus-visible:outline-foreground font-medium underline decoration-dotted underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            aquí (HTML)
          </a>
          .
        </P>
        <Note>
          Ese HTML es una copia sincronizada automáticamente desde{" "}
          <code className="font-mono">reports/validacion_sentimiento_revision.html</code> en cada
          arranque y build (<code className="font-mono">npm run sync:informes</code>).
        </Note>
      </DocSection>

      <DocSection id="cambios-heading" title="Series mensuales y cambios de régimen">
        <P>
          Cada intervención se agrega a mes según su tópico y su{" "}
          <code className="font-mono">senti_n</code> (D-08, D-28), y de ahí salen las series de
          cuota por tópico, el tono global y la tasa de outliers. Los cambios de régimen se detectan
          con PELT (coste l2, min_size = 6), eligiendo la penalización por un criterio tipo BIC
          sobre la rejilla logarítmica de 10⁻⁶ a 10³ y verificando la robustez con factores de 0,25×
          a 4×.
        </P>
        <P>
          El resultado son <strong>136 cambios en 53 series</strong>: 133 en la cuota de prevalencia
          de los tópicos y 3 en el tono global. Cada cambio se contrasta con una Mann-Whitney
          bilateral de los meses anteriores y posteriores (tamaño de efecto rango-biserial) y la
          familia completa de contrastes se corrige con Benjamini-Hochberg:{" "}
          <strong>45 de 136 superan q &lt; 0,05</strong>. La portada muestra los cambios con sus
          estadísticos; las tablas completas, la sensibilidad de la penalización y el criterio de
          potencia (10 meses con 5 o más intervenciones del tópico) están en Métricas.
        </P>
      </DocSection>

      {bundle ? (
        <DocSection id="eventos-heading" title="Análisis exploratorio de eventos (resultado nulo)">
          <P>
            Sobre las {bundle.events.length} series de eventos del repositorio se contrastó cada
            serie mensual con una ventana de ±3 meses usando correlación de Spearman y corrección de
            Benjamini-Hochberg sobre una familia única de 472 contrastes (D-09).
          </P>
          <P>
            <strong>Resultado: nulo.</strong> Ninguna asociación supera q &lt; 0,05 (el mínimo
            alcanzado es 0,254). Con 82 meses de serie la potencia es limitada, y las correlaciones
            que pasan el filtro crudo de p &lt; 0,05 son compatibles con el azar. Se documenta aquí
            porque forma parte del registro honesto del proyecto: <strong>no hay evidencia</strong>{" "}
            de que los eventos enumerados se asocien a los cambios de las series a este nivel de
            análisis.
          </P>
          <EventsTable events={bundle.events} />
          <EventsHeatmap view={bundle.view} />
        </DocSection>
      ) : (
        <div className="mt-8">
          <ApiErrorNotice failure={failure ?? { status: null, detail: "Error inesperado" }} />
        </div>
      )}

      <DocSection id="trazabilidad-heading" title="Trazabilidad y regeneración">
        <P>
          Los artefactos se regeneran con los módulos CLI de{" "}
          <code className="font-mono">src/analysis/</code> y{" "}
          <code className="font-mono">src/nlp/</code>: por ejemplo,{" "}
          <code className="font-mono">uv run python -m src.analysis.regime_change</code> reconstruye
          los cambios, su sensibilidad, los contrastes Mann-Whitney con BH y las relaciones con
          eventos. El contrato de ficheros del proyecto vive en{" "}
          <code className="font-mono">structure.md</code> y el registro de decisiones en{" "}
          <code className="font-mono">docs/DECISIONS.md</code>.
        </P>
        <Note>
          Este panel es solo lectura: no modifica artefactos ni etiquetas. La revisión de las
          etiquetas de tópicos (D-25) se hace fuera de la interfaz.
        </Note>
      </DocSection>
    </div>
  );
}
