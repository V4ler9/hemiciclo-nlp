import { ApiErrorNotice, type ApiFailure } from "@/components/api-error";
import { TopicEvidence } from "@/components/topic-evidence";
import { TopicHeatmap } from "@/components/topic-heatmap";
import { ApiError, type Topic, getSeries, getTopics, isDynamicUsage } from "@/lib/api";
import { buildTopicHeatmap, type HeatmapData } from "@/lib/changes";

interface EvidenceBundle {
  topics: Topic[];
  heatmap: HeatmapData;
}

async function loadEvidence(): Promise<EvidenceBundle> {
  const [topics, series] = await Promise.all([getTopics(), getSeries("topic")]);
  return { topics, heatmap: buildTopicHeatmap(series, topics) };
}

export default async function EvidenciasPage({ searchParams }: PageProps<"/evidencias">) {
  const params = await searchParams;
  const parsedTopic = Number(params.topico);
  const requestedTopic = Number.isInteger(parsedTopic) ? parsedTopic : undefined;

  let bundle: EvidenceBundle | null = null;
  let failure: ApiFailure | null = null;
  try {
    bundle = await loadEvidence();
  } catch (cause) {
    if (isDynamicUsage(cause)) throw cause;
    console.error("[evidencias] no se pudieron cargar las evidencias:", cause);
    failure = {
      status: cause instanceof ApiError ? cause.status : null,
      detail: cause instanceof Error ? cause.message : "Error inesperado",
    };
  }
  const initialTopic =
    bundle && requestedTopic !== undefined
      ? bundle.topics.find((topic) => topic.topic === requestedTopic)?.topic
      : undefined;

  return (
    <div>
      <header className="border-border border-b pb-6">
        <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">
          Prueba material de cada tópico
        </p>
        <h1 className="text-foreground mt-3 font-serif text-4xl font-semibold tracking-tight">
          Evidencias por tópico
        </h1>
      </header>
      {bundle ? (
        <div>
          <section aria-labelledby="explorador-heading">
            <h2
              id="explorador-heading"
              className="text-muted-foreground mt-8 text-xs font-medium tracking-[0.25em] uppercase"
            >
              Explorador de tópicos
            </h2>
            <TopicEvidence topics={bundle.topics} initialTopic={initialTopic} />
          </section>
          <section aria-labelledby="heatmap-heading" className="border-border mt-12 border-t pt-8">
            <h2
              id="heatmap-heading"
              className="text-muted-foreground text-xs font-medium tracking-[0.25em] uppercase"
            >
              Panorama: cuota por tópico y mes
            </h2>
            <TopicHeatmap data={bundle.heatmap} />
          </section>
        </div>
      ) : (
        <div className="mt-8">
          <ApiErrorNotice failure={failure ?? { status: null, detail: "Error inesperado" }} />
        </div>
      )}
    </div>
  );
}
