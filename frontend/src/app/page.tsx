import Link from "next/link";
import { ActorComposition } from "@/components/actor-composition";
import { ApiErrorNotice, type ApiFailure } from "@/components/api-error";
import { ChangeExplorer } from "@/components/change-explorer";
import { EpisodeTimeline } from "@/components/episode-timeline";
import { EventAlignment } from "@/components/event-alignment";
import { HomeTone } from "@/components/home-tone";
import { Kpi } from "@/components/kpi";
import { ApiError, type HomePayload, getHome, isDynamicUsage } from "@/lib/api";
import { fmtMonth } from "@/lib/format";

const integer = new Intl.NumberFormat("es-ES");

function HomeHeader({ home }: { home: HomePayload }) {
  return (
    <header className="border-border border-b pb-8">
      <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">
        ParlaMint-ES · {integer.format(home.kpis.intervenciones)} intervenciones ·{" "}
        {integer.format(home.kpis.topicos)} tópicos
      </p>
      <h1 className="text-foreground mt-4 max-w-4xl font-serif text-5xl font-semibold tracking-tight sm:text-6xl">
        {home.tesis.titular}
      </h1>
      <p className="text-foreground mt-4 max-w-3xl font-serif text-xl leading-8">
        {home.tesis.subtitulo}
      </p>
      <p className="text-muted-foreground mt-4 max-w-3xl text-sm leading-6">
        Una lectura de las intervenciones del Pleno entre 2015 y 2023. La agenda no se mueve en
        línea recta: cambia a saltos, y los saltos grandes tienen fecha, tópico y actores. El tono
        no cae porque todos hablen peor; cae porque cambia quién habla.
      </p>
      <nav aria-label="Actos de la home" className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm">
        {[
          ["#tono", "El tono"],
          ["#episodios", "Los episodios"],
          ["#actores", "Quién habla"],
          ["#eventos", "Los eventos"],
          ["#mapa", "El mapa"],
          ["#limites", "Límites"],
        ].map(([href, label]) => (
          <a
            key={href}
            href={href}
            className="text-muted-foreground hover:text-foreground focus-visible:outline-foreground rounded-sm underline decoration-dotted underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2"
          >
            {label}
          </a>
        ))}
      </nav>
    </header>
  );
}

function HomeKpis({ home }: { home: HomePayload }) {
  return (
    <dl className="mt-8 grid grid-cols-2 gap-8 lg:grid-cols-5">
      <Kpi label="Intervenciones" value={integer.format(home.kpis.intervenciones)} />
      <Kpi label="Tópicos" value={integer.format(home.kpis.topicos)} />
      <Kpi label="Cambios significativos" value={integer.format(home.kpis.cambios_significativos)} />
      <Kpi label="Fechas de cambio" value={integer.format(home.kpis.fechas)} />
      <Kpi
        label="Cambio de tono"
        value={home.kpis.cambio_tono ? fmtMonth(home.kpis.cambio_tono) : "—"}
      />
    </dl>
  );
}

function Caveats({ home }: { home: HomePayload }) {
  return (
    <section aria-labelledby="limites-heading" className="border-border mt-14 border-t pt-8">
      <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">Cierre · Límites</p>
      <h2
        id="limites-heading"
        className="text-foreground mt-2 font-serif text-3xl font-semibold tracking-tight"
      >
        Lo que esta historia no dice
      </h2>
      <div className="mt-4 grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <ul className="text-foreground max-w-3xl space-y-3 text-sm leading-6">
          {home.caveats.map((caveat) => (
            <li key={caveat} className="border-border border-l-2 pl-4">
              {caveat}
            </li>
          ))}
          <li className="border-border border-l-2 pl-4">
            Los episodios agrupan eventos que se solapan. «Asociación» no significa «causa»: la
            comparación es descriptiva y el event study mide alineación temporal, no mecanismos.
          </li>
        </ul>
        <div className="text-muted-foreground space-y-3 text-sm leading-6">
          <p>
            La metodología completa —corpus, BERTopic, validación del tono, PELT, event study y
            descomposición de actores— está en{" "}
            <Link href="/metodologia" className="text-foreground font-medium underline decoration-dotted underline-offset-4">
              Metodología
            </Link>
            . Las series completas y los estadísticos, en{" "}
            <Link href="/metricas" className="text-foreground font-medium underline decoration-dotted underline-offset-4">
              Métricas
            </Link>
            ; los textos representativos, en{" "}
            <Link href="/evidencias" className="text-foreground font-medium underline decoration-dotted underline-offset-4">
              Evidencias
            </Link>
            .
          </p>
          <p>
            Los datos son ParlaMint-ES 5.0 y ParlaCAP 1.0 (CC BY 4.0). El código es MIT y los
            artefactos se regeneran con `npm run pipeline` o los módulos de `src/analysis/`.
          </p>
        </div>
      </div>
    </section>
  );
}

export default async function HomePage() {
  let home: HomePayload | null = null;
  let failure: ApiFailure | null = null;
  try {
    home = await getHome();
  } catch (cause) {
    if (isDynamicUsage(cause)) throw cause;
    console.error("[home] no se pudo cargar el bundle editorial:", cause);
    failure = {
      status: cause instanceof ApiError ? cause.status : null,
      detail: cause instanceof Error ? cause.message : "Error inesperado",
    };
  }

  if (!home) {
    return (
      <div>
        <header className="border-border border-b pb-6">
          <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">
            ParlaMint-ES · Congreso de los Diputados (2015-2023)
          </p>
          <h1 className="text-foreground mt-3 max-w-3xl font-serif text-4xl font-semibold tracking-tight sm:text-5xl">
            El Congreso cambia a saltos
          </h1>
        </header>
        <div className="mt-8">
          <ApiErrorNotice failure={failure ?? { status: null, detail: "Error inesperado" }} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <HomeHeader home={home} />
      <HomeKpis home={home} />
      <div id="tono">
        <HomeTone
          points={home.tono}
          episode={
            home.episodios.find((episode) => episode.episodio_id === "EP04_2020_06") ?? null
          }
        />
      </div>
      <div id="episodios">
        <EpisodeTimeline episodes={home.episodios} />
      </div>
      <div id="actores">
        <ActorComposition points={home.actores} actorChanges={home.actores_cambio} />
      </div>
      <div id="eventos">
        <EventAlignment rows={home.eventos} />
      </div>
      <div id="mapa">
        <ChangeExplorer changes={home.cambios} actorChanges={home.actores_cambio} />
      </div>
      <div id="limites">
        <Caveats home={home} />
      </div>
    </div>
  );
}
