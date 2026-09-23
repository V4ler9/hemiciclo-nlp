import { ApiErrorNotice, type ApiFailure } from "@/components/api-error";
import { ConfusionPicker } from "@/components/confusion-matrix";
import { Kpi } from "@/components/kpi";
import { QualityCharts } from "@/components/quality-charts";
import {
  ApiError,
  type ChangeSensitivityRow,
  type ChangeStats,
  type ConfusionMatrix,
  type EmbeddingRow,
  type IcRow,
  type Meta,
  type SentimentPayload,
  type SeriesPoint,
  type Topic,
  type TopicSelectionRow,
  getChangesSensitivity,
  getChangesStats,
  getConfusion,
  getMeta,
  getSentiment,
  getSeries,
  getSensitivity,
  getTopics,
  getTopicsSelection,
  isDynamicUsage,
} from "@/lib/api";
import { MESES_REGULARES_MIN, INTERVENCIONES_MES_MIN } from "@/lib/constants";
import { fmtDecimal, fmtInt, fmtMonth, fmtP, fmtQuota, fmtR } from "@/lib/format";

interface MetricsBundle {
  meta: Meta;
  selection: TopicSelectionRow[];
  embeddings: EmbeddingRow[];
  sentiment: SentimentPayload;
  matrices: Record<string, ConfusionMatrix>;
  sensitivity: ChangeSensitivityRow[];
  stats: ChangeStats[];
  topics: Topic[];
  volume: SeriesPoint[];
  outliers: SeriesPoint[];
}

async function loadMetrics(): Promise<MetricsBundle> {
  const [
    meta,
    selection,
    embeddings,
    sentiment,
    confusion3,
    confusion6,
    sensitivity,
    stats,
    topics,
    volume,
    outliers,
  ] = await Promise.all([
    getMeta(),
    getTopicsSelection(),
    getSensitivity(),
    getSentiment(),
    getConfusion("senti_3"),
    getConfusion("senti_6"),
    getChangesSensitivity(),
    getChangesStats(),
    getTopics(),
    getSeries("volume"),
    getSeries("outliers"),
  ]);
  return {
    meta,
    selection,
    embeddings,
    sentiment,
    matrices: { senti_3: confusion3, senti_6: confusion6 },
    sensitivity,
    stats,
    topics,
    volume,
    outliers,
  };
}

function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return Number.NaN;
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position);
  const fraction = position - lower;
  const from = sorted[lower] ?? 0;
  const to = sorted[lower + 1] ?? from;
  return from + fraction * (to - from);
}

interface SensitivitySummary {
  factor: number;
  totalCambios: number;
  mediaSerie: number;
  seriesConCambios: number;
}

function summarizeSensitivity(rows: ChangeSensitivityRow[]): SensitivitySummary[] {
  const byFactor = new Map<number, ChangeSensitivityRow[]>();
  for (const row of rows) {
    const bucket = byFactor.get(row.factor);
    if (bucket) {
      bucket.push(row);
    } else {
      byFactor.set(row.factor, [row]);
    }
  }
  return [...byFactor.entries()]
    .map(([factor, factorRows]) => {
      const total = factorRows.reduce((sum, row) => sum + row.n_cambios, 0);
      return {
        factor,
        totalCambios: total,
        mediaSerie: total / factorRows.length,
        seriesConCambios: factorRows.filter((row) => row.n_cambios > 0).length,
      };
    })
    .sort((a, b) => a.factor - b.factor);
}

function Section({
  id,
  title,
  lead,
  children,
}: {
  id: string;
  title: string;
  lead?: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="border-border mt-10 border-t pt-8">
      <h2 id={id} className="text-muted-foreground text-xs font-medium tracking-[0.25em] uppercase">
        {title}
      </h2>
      {lead && <p className="text-muted-foreground mt-2 max-w-3xl text-sm">{lead}</p>}
      <div className="mt-5 space-y-6">{children}</div>
    </section>
  );
}

function Subsection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-foreground font-serif text-lg font-semibold">{title}</h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Table({
  head,
  children,
  label,
  tall = false,
}: {
  head: string[];
  children: React.ReactNode;
  label: string;
  tall?: boolean;
}) {
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      className={
        "focus-visible:outline-foreground overflow-auto focus-visible:outline-2 focus-visible:outline-offset-2 " +
        (tall ? "border-border max-h-80 rounded border" : "")
      }
    >
      <table className="w-full text-sm tabular-nums">
        <thead className={tall ? "bg-background sticky top-0 z-10" : undefined}>
          <tr className="border-border text-muted-foreground border-b text-left text-xs tracking-wider uppercase">
            {head.map((column) => (
              <th key={column} scope="col" className="py-2 pr-4 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

const CELL = "py-1.5 pr-4 text-foreground";

function formatOptional(value: number | null, digits = 3): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return fmtDecimal(value, digits);
}

function TopicModelBlock({
  meta,
  selection,
  embeddings,
}: {
  meta: Meta;
  selection: TopicSelectionRow[];
  embeddings: EmbeddingRow[];
}) {
  return (
    <Section
      id="modelo-heading"
      title="Modelo de tópicos"
      lead="Selección de la rejilla final (D-32): se descartan combinaciones con más de 40 % de outliers o fuera de [20, 60] tópicos; se maximiza c_v y se desempata por diversidad."
    >
      <dl className="grid grid-cols-2 gap-8 sm:grid-cols-4">
        <Kpi label="Tópicos finales" value={fmtInt(meta.topicos)} />
        <Kpi label="Coherencia c_v" value={fmtDecimal(meta.coherencia_cv, 4)} />
        <Kpi label="Diversidad" value={fmtDecimal(meta.diversidad, 4)} />
        <Kpi label="Tasa de outliers" value={fmtQuota(meta.tasa_outliers)} />
      </dl>
      <Subsection title={`Rejilla probada · ${selection.length} combinaciones`}>
        <Table
          tall
          label="Rejilla de selección de hiperparámetros"
          head={[
            "min_topic_size",
            "n_neighbors",
            "min_samples",
            "tópicos",
            "outliers",
            "c_v",
            "diversidad",
            "seleccionada",
          ]}
        >
          {selection.map((row) => (
            <tr
              key={`${String(row.min_topic_size)}-${String(row.n_neighbors)}-${String(row.min_samples)}`}
              className={row.selected === 1 ? "bg-muted font-medium" : undefined}
            >
              <td className={CELL}>{row.min_topic_size}</td>
              <td className={CELL}>{row.n_neighbors}</td>
              <td className={CELL}>{row.min_samples}</td>
              <td className={CELL}>{row.n_topics}</td>
              <td className={CELL}>{fmtQuota(row.outlier_rate)}</td>
              <td className={CELL}>{fmtDecimal(row.coherence, 4)}</td>
              <td className={CELL}>{fmtDecimal(row.diversity, 4)}</td>
              <td className={CELL}>{row.selected === 1 ? "sí" : ""}</td>
            </tr>
          ))}
        </Table>
      </Subsection>
      <Subsection title="Sensibilidad de los embeddings (D-39)">
        <Table
          label="Sensibilidad de los embeddings"
          head={["modelo", "tópicos", "outliers", "c_v", "diversidad", "ARI vs e5", "NMI vs e5"]}
        >
          {embeddings.map((row) => (
            <tr key={row.modelo} className="border-border/60 border-b">
              <td className={CELL}>{row.modelo}</td>
              <td className={CELL}>{row.n_topicos}</td>
              <td className={CELL}>{fmtQuota(row.outlier_rate)}</td>
              <td className={CELL}>{fmtDecimal(row.coherencia_cv, 4)}</td>
              <td className={CELL}>{fmtDecimal(row.diversidad, 4)}</td>
              <td className={CELL}>{formatOptional(row.ari_vs_e5)}</td>
              <td className={CELL}>{formatOptional(row.nmi_vs_e5)}</td>
            </tr>
          ))}
        </Table>
        <p className="text-muted-foreground mt-2 text-xs">
          {fmtInt(embeddings[0]?.n_comparables ?? 0)} intervenciones comparables entre modelos.
        </p>
      </Subsection>
    </Section>
  );
}

function SentimentBlock({
  sentiment,
  matrices,
}: {
  sentiment: SentimentPayload;
  matrices: Record<string, ConfusionMatrix>;
}) {
  const metricsHead = [
    "nivel",
    "n",
    "accuracy",
    "balanced",
    "reweighted",
    "F1 macro",
    "κ lineal",
    "κ cuadrático",
  ];
  return (
    <Section
      id="sentimiento-heading"
      title="Validación de sentimiento (D-36 y D-37)"
      lead="Comparación del modelo (ParlaSent + LLM) contra revisión humana, con intervalos bootstrap por BCa. La limitación del nivel 6 clases queda documentada en Metodología."
    >
      <Subsection title="Métricas principales">
        <Table label="Métricas principales de validación de sentimiento" head={metricsHead}>
          {sentiment.revision_metricas.map((row) => (
            <tr key={row.nivel} className="border-border/60 border-b">
              <td className={CELL}>{row.nivel}</td>
              <td className={CELL}>{fmtInt(row.n)}</td>
              <td className={CELL}>{fmtDecimal(row.accuracy)}</td>
              <td className={CELL}>{fmtDecimal(row.balanced_accuracy)}</td>
              <td className={CELL}>{fmtDecimal(row.reweighted_accuracy)}</td>
              <td className={CELL}>{fmtDecimal(row.f1_macro)}</td>
              <td className={CELL}>{fmtDecimal(row.kappa_linear)}</td>
              <td className={CELL}>{fmtDecimal(row.kappa_quadratic)}</td>
            </tr>
          ))}
        </Table>
      </Subsection>
      <Subsection title="Intervalos de confianza bootstrap">
        <Table
          tall
          label="Intervalos de confianza bootstrap"
          head={["nivel", "métrica", "variante", "estimador [IC]", "n_boot"]}
        >
          {sentiment.revision_ic.map((row: IcRow) => (
            <tr
              key={`${row.nivel}-${row.metrica}-${row.variante}`}
              className="border-border/60 border-b"
            >
              <td className={CELL}>{row.nivel}</td>
              <td className={CELL}>{row.metrica}</td>
              <td className={CELL}>{row.variante}</td>
              <td className={CELL}>
                {fmtDecimal(row.estimador)} [{fmtDecimal(row.ic_inf)}, {fmtDecimal(row.ic_sup)}]
              </td>
              <td className={CELL}>{fmtInt(row.n_boot)}</td>
            </tr>
          ))}
        </Table>
      </Subsection>
      <Subsection title="Acuerdo a tres bandas (ParlaSent · LLM · humano)">
        <Table
          label="Acuerdo a tres bandas"
          head={["par", "nivel", "n", "acuerdo", "κ lineal", "κ cuadrático", "Fleiss"]}
        >
          {sentiment.acuerdo_3bandas.map((row) => (
            <tr key={`${row.par}-${row.nivel}`} className="border-border/60 border-b">
              <td className={CELL}>{row.par}</td>
              <td className={CELL}>{row.nivel}</td>
              <td className={CELL}>{fmtInt(row.n)}</td>
              <td className={CELL}>{fmtDecimal(row.acuerdo)}</td>
              <td className={CELL}>{fmtDecimal(row.kappa_linear)}</td>
              <td className={CELL}>{fmtDecimal(row.kappa_quadratic)}</td>
              <td className={CELL}>{formatOptional(row.fleiss_kappa)}</td>
            </tr>
          ))}
        </Table>
      </Subsection>
      <Subsection title="Matriz de confusión">
        <ConfusionPicker matrices={matrices} />
      </Subsection>
    </Section>
  );
}

function ChangesBlock({
  sensitivity,
  stats,
  topics,
}: {
  sensitivity: ChangeSensitivityRow[];
  stats: ChangeStats[];
  topics: Topic[];
}) {
  const summary = summarizeSensitivity(sensitivity);
  const rawSignificant = stats.filter((row) => row.p < 0.05).length;
  const bhSignificant = stats.filter((row) => row.significativo_bh === 1).length;
  const sizes = topics.map((topic) => topic.size).sort((a, b) => a - b);
  const ordered = [...stats].sort((a, b) => a.q - b.q);
  const labelById = new Map(topics.map((topic) => [String(topic.topic), topic.label]));

  function serieLabel(row: ChangeStats): string {
    if (row.serie === "tone") return "tono";
    return labelById.get(row.serie_id) ?? `tópico ${row.serie_id}`;
  }

  return (
    <Section
      id="cambios-heading"
      title="Detección de cambios"
      lead="PELT (coste l2, min_size 6, rejilla de penalización logarítmica [1e-6, 1e3] elegida por criterio tipo BIC) sobre cada serie mensual, y corrección de Benjamini-Hochberg sobre la familia completa de contrastes Mann-Whitney."
    >
      <dl className="grid grid-cols-2 gap-8 sm:grid-cols-4">
        <Kpi label="Contrastes" value={fmtInt(stats.length)} />
        <Kpi label="p < 0,05 (crudos)" value={fmtInt(rawSignificant)} />
        <Kpi label="q < 0,05 (BH)" value={fmtInt(bhSignificant)} />
        <Kpi label="Tamaños (mediana)" value={fmtInt(Math.round(quantile(sizes, 0.5)))} />
      </dl>
      <Subsection title="Sensibilidad de la penalización (factores 0,25× – 4×)">
        <Table
          label="Sensibilidad de la penalización"
          head={["factor", "cambios totales", "media por serie", "series con ≥1 cambio"]}
        >
          {summary.map((row) => (
            <tr key={row.factor} className="border-border/60 border-b">
              <td className={CELL}>{fmtDecimal(row.factor, 2)}×</td>
              <td className={CELL}>{fmtInt(row.totalCambios)}</td>
              <td className={CELL}>{fmtDecimal(row.mediaSerie, 2)}</td>
              <td className={CELL}>{fmtInt(row.seriesConCambios)}</td>
            </tr>
          ))}
        </Table>
      </Subsection>
      <Subsection title="Criterios de potencia y tamaños">
        <p className="text-muted-foreground max-w-3xl text-sm">
          Una serie se marca como de{" "}
          <span className="text-foreground font-medium">baja potencia</span> cuando tiene menos de{" "}
          {MESES_REGULARES_MIN} meses con {INTERVENCIONES_MES_MIN} o más intervenciones del tópico:
          su cuota mensual es ruidosa. Tamaños de tópico (intervenciones): mín{" "}
          {fmtInt(sizes[0] ?? 0)} · p25 {fmtInt(Math.round(quantile(sizes, 0.25)))} · mediana{" "}
          {fmtInt(Math.round(quantile(sizes, 0.5)))} · p75{" "}
          {fmtInt(Math.round(quantile(sizes, 0.75)))} · máx {fmtInt(sizes[sizes.length - 1] ?? 0)}.
        </p>
      </Subsection>
      <Subsection title={`Tabla completa de contrastes · orden por q (${stats.length})`}>
        <div
          role="region"
          aria-label="Tabla completa de contrastes de cambios"
          tabIndex={0}
          className="border-border focus-visible:outline-foreground max-h-96 overflow-auto rounded border focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          <table className="w-full text-sm tabular-nums">
            <thead className="bg-background sticky top-0">
              <tr className="border-border text-muted-foreground border-b text-left text-xs tracking-wider uppercase">
                <th scope="col" className="py-2 pr-4 font-medium">
                  serie
                </th>
                <th scope="col" className="py-2 pr-4 font-medium">
                  fecha
                </th>
                <th scope="col" className="py-2 pr-4 font-medium">
                  r
                </th>
                <th scope="col" className="py-2 pr-4 font-medium">
                  p
                </th>
                <th scope="col" className="py-2 pr-4 font-medium">
                  q (BH)
                </th>
                <th scope="col" className="py-2 pr-4 font-medium">
                  n
                </th>
                <th scope="col" className="py-2 font-medium">
                  significativo
                </th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((row) => (
                <tr
                  key={`${row.serie}-${row.serie_id}-${row.fecha}`}
                  className="border-border/60 border-b"
                >
                  <td className={CELL}>{serieLabel(row)}</td>
                  <td className={CELL}>{fmtMonth(row.fecha)}</td>
                  <td className={CELL}>{fmtR(row.r)}</td>
                  <td className={CELL}>{fmtP(row.p)}</td>
                  <td className={CELL}>{fmtP(row.q)}</td>
                  <td className={CELL}>{row.n}</td>
                  <td className={CELL}>{row.significativo_bh === 1 ? "q < 0,05" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Subsection>
    </Section>
  );
}

function QualityBlock({
  meta,
  volume,
  outliers,
}: {
  meta: Meta;
  volume: SeriesPoint[];
  outliers: SeriesPoint[];
}) {
  const activeMonths = volume.filter((row) => row.has_session).length;
  return (
    <Section
      id="calidad-heading"
      title="Calidad de datos"
      lead="Escala del corpus y rendimiento de BERTopic a lo largo de toda la serie temporal."
    >
      <dl className="grid grid-cols-2 gap-8 sm:grid-cols-4">
        <Kpi label="Intervenciones" value={fmtInt(meta.intervenciones)} />
        <Kpi label="Meses con sesión" value={fmtInt(activeMonths)} />
        <Kpi label="Tasa de outliers" value={fmtQuota(meta.tasa_outliers)} />
        <Kpi label="Tópicos" value={fmtInt(meta.topicos)} />
      </dl>
      <QualityCharts volume={volume} outliers={outliers} />
    </Section>
  );
}

export default async function MetricasPage() {
  let bundle: MetricsBundle | null = null;
  let failure: ApiFailure | null = null;
  try {
    bundle = await loadMetrics();
  } catch (cause) {
    if (isDynamicUsage(cause)) throw cause;
    console.error("[métricas] no se pudieron cargar las métricas:", cause);
    failure = {
      status: cause instanceof ApiError ? cause.status : null,
      detail: cause instanceof Error ? cause.message : "Error inesperado",
    };
  }

  return (
    <div>
      <header className="border-border border-b pb-6">
        <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">
          Justificación de los resultados
        </p>
        <h1 className="text-foreground mt-3 font-serif text-4xl font-semibold tracking-tight">
          Métricas
        </h1>
      </header>
      {bundle ? (
        <div>
          <TopicModelBlock
            meta={bundle.meta}
            selection={bundle.selection}
            embeddings={bundle.embeddings}
          />
          <SentimentBlock sentiment={bundle.sentiment} matrices={bundle.matrices} />
          <ChangesBlock
            sensitivity={bundle.sensitivity}
            stats={bundle.stats}
            topics={bundle.topics}
          />
          <QualityBlock meta={bundle.meta} volume={bundle.volume} outliers={bundle.outliers} />
        </div>
      ) : (
        <div className="mt-8">
          <ApiErrorNotice failure={failure ?? { status: null, detail: "Error inesperado" }} />
        </div>
      )}
    </div>
  );
}
