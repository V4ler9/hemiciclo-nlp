import { ApiErrorNotice, type ApiFailure } from "@/components/api-error";
import { Kpi } from "@/components/kpi";
import { ToneHero } from "@/components/tone-hero";
import { TopicGrid } from "@/components/topic-grid";
import {
  ApiError,
  type Meta,
  getChanges,
  getChangesStats,
  getMeta,
  getSeries,
  getTopics,
  isDynamicUsage,
} from "@/lib/api";
import { buildTopicCards, buildToneView, type ToneView, type TopicCard } from "@/lib/changes";

const integer = new Intl.NumberFormat("es-ES");
const percent = new Intl.NumberFormat("es-ES", { style: "percent", maximumFractionDigits: 1 });
const decimal = new Intl.NumberFormat("es-ES", {
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});

interface Dashboard {
  meta: Meta;
  tone: ToneView;
  cards: TopicCard[];
  kicker: string;
}

async function loadDashboard(): Promise<Dashboard> {
  const [meta, toneSeries, toneChanges, topicSeries, topicChanges, allStats, topics] =
    await Promise.all([
      getMeta(),
      getSeries("tone"),
      getChanges("tone"),
      getSeries("topic"),
      getChanges("topic"),
      getChangesStats(),
      getTopics(),
    ]);
  return {
    meta,
    tone: buildToneView(toneSeries, toneChanges, allStats),
    cards: buildTopicCards(topics, topicSeries, topicChanges, allStats),
    kicker: `ParlaMint-ES · ${integer.format(meta.intervenciones)} intervenciones · ${integer.format(meta.topicos)} tópicos`,
  };
}

function PageHeader({ kicker }: { kicker: string }) {
  return (
    <header className="border-border border-b pb-6">
      <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">{kicker}</p>
      <h1 className="text-foreground mt-3 max-w-3xl font-serif text-4xl font-semibold tracking-tight sm:text-5xl">
        El tono del debate: tópicos y cambios de régimen en el Congreso (2015-2023)
      </h1>
    </header>
  );
}

function CorpusKpis({ meta }: { meta: Meta }) {
  return (
    <dl className="mt-6 grid grid-cols-2 gap-8 lg:grid-cols-5">
      <Kpi label="Intervenciones" value={integer.format(meta.intervenciones)} />
      <Kpi label="Tópicos" value={integer.format(meta.topicos)} />
      <Kpi label="Tasa de outliers" value={percent.format(meta.tasa_outliers)} />
      <Kpi label="Coherencia c_v" value={decimal.format(meta.coherencia_cv)} />
      <Kpi label="Diversidad" value={decimal.format(meta.diversidad)} />
    </dl>
  );
}

export default async function Home() {
  let dashboard: Dashboard | null = null;
  let failure: ApiFailure | null = null;
  try {
    dashboard = await loadDashboard();
  } catch (cause) {
    if (isDynamicUsage(cause)) throw cause;
    console.error("[portada] no se pudo cargar el dashboard:", cause);
    failure = {
      status: cause instanceof ApiError ? cause.status : null,
      detail: cause instanceof Error ? cause.message : "Error inesperado",
    };
  }

  if (!dashboard) {
    return (
      <div>
        <PageHeader kicker="ParlaMint-ES · Congreso de los Diputados (2015-2023)" />
        <div className="mt-8">
          <ApiErrorNotice failure={failure ?? { status: null, detail: "Error inesperado" }} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader kicker={dashboard.kicker} />
      <CorpusKpis meta={dashboard.meta} />
      <ToneHero view={dashboard.tone} />
      <TopicGrid cards={dashboard.cards} />
    </div>
  );
}
