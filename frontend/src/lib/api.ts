import type { paths } from "./api-types.gen";

/**
 * URL base de la API.
 *
 * En el servidor se prefiera `HEMICICLO_API_URL_SERVER` (runtime; en Docker apunta
 * a `http://api:8000`, inalcanzable desde el navegador). En cliente solo existe
 * `NEXT_PUBLIC_HEMICICLO_API_URL`, inyectada en build.
 */
function resolveApiUrl(): string {
  if (typeof window === "undefined") {
    const serverUrl = process.env["HEMICICLO_API_URL_SERVER"];
    if (serverUrl) return serverUrl;
  }
  return process.env["NEXT_PUBLIC_HEMICICLO_API_URL"] ?? "http://localhost:8000";
}

const API_URL = resolveApiUrl();
const REQUEST_TIMEOUT_MS = 15_000;

/** Error de la capa de datos: fallo de red (``status: 0``) o respuesta no exitosa. */
export class ApiError extends Error {
  readonly status: number;
  readonly path: string;

  constructor(path: string, status: number, message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "ApiError";
    this.status = status;
    this.path = path;
  }
}

type GetPath = {
  [P in keyof paths]: paths[P] extends { get: unknown } ? P : never;
}[keyof paths];

type ResponseOf<TPath extends GetPath> = paths[TPath]["get"] extends {
  responses: { 200: { content: { "application/json": infer TBody } } };
}
  ? TBody
  : never;

type QueryOf<TPath extends GetPath> = paths[TPath]["get"] extends {
  parameters: { query?: infer TQuery };
}
  ? TQuery
  : never;

/**
 * GET tipado contra el esquema OpenAPI de FastAPI.
 *
 * Lanza {@link ApiError} ante fallos de red, 404 y 503 (artefacto ausente), de
 * modo que las páginas deciden qué mostrar sin repetir manejo de errores.
 */
/**
 * El `fetch` de Next lanza este sentinel durante la generación estática para
 * marcar la ruta como dinámica; no debe confundirse con un fallo de la API.
 */
export function isDynamicUsage(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "digest" in error &&
    (error as { digest?: unknown }).digest === "DYNAMIC_SERVER_USAGE"
  );
}

export async function apiGet<TPath extends GetPath>(
  path: TPath,
  query?: QueryOf<TPath>,
  pathParams?: Record<string, string>
): Promise<ResponseOf<TPath>> {
  let resolved: string = path;
  if (pathParams) {
    for (const [key, value] of Object.entries(pathParams)) {
      resolved = resolved.replace(`{${key}}`, encodeURIComponent(value));
    }
  }
  const url = new URL(resolved, API_URL);
  const params = (query ?? {}) as Record<string, unknown>;
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      url.searchParams.set(key, String(value));
    }
  }

  let response: Response;
  try {
    response = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (cause) {
    if (isDynamicUsage(cause)) throw cause;
    throw new ApiError(resolved, 0, `No se pudo conectar con la API en ${API_URL}`, { cause });
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof payload?.detail === "string" ? payload.detail : response.statusText;
    throw new ApiError(resolved, response.status, detail);
  }
  return (await response.json()) as ResponseOf<TPath>;
}

/** Resumen del corpus y del modelo de tópicos (columnas de ``GET /meta``). */
export interface Meta {
  intervenciones: number;
  topicos: number;
  tasa_outliers: number;
  rejilla_seleccionada: Record<string, number>;
  coherencia_cv: number;
  diversidad: number;
}

/** Fila de ``GET /series``: punto mensual de una serie (nulo sin sesión). */
export interface SeriesPoint {
  month: string;
  series_type: string;
  series_id: string;
  value: number | null;
  n_interventions: number;
  has_session: boolean;
}

/** Fila de ``GET /changes``: punto de cambio detectado por PELT. */
export interface Change {
  serie: string;
  serie_id: string;
  fecha: string;
  indice: number;
  media_antes: number;
  media_despues: number;
  delta: number;
  pen_seleccionada: number;
  n_cambios: number;
  n_puntos: number;
  tamano_serie: number;
}

/** Fila de ``GET /changes/stats``: Mann-Whitney antes/después con BH. */
export interface ChangeStats {
  serie: string;
  serie_id: string;
  fecha: string;
  r: number;
  p: number;
  q: number;
  n_antes: number;
  n_despues: number;
  n: number;
  significativo_bh: number;
}

/** Fila de ``GET /topics``: tópico con etiqueta y tamaño. */
export interface Topic {
  topic: number;
  size: number;
  share: number;
  top_terms: string;
  label: string | null;
  description: string | null;
  reviewed_by: string | null;
}

/**
 * Consulta ``/meta``.
 *
 * FastAPI declara los endpoints como ``dict[str, Any]``, así que el OpenAPI no
 * puede inferir el cuerpo: la refinación ocurre aquí, una sola vez, alineada
 * con las columnas reales de los artefactos.
 */
export async function getMeta(): Promise<Meta> {
  return (await apiGet("/meta")) as unknown as Meta;
}

/** Serie mensual (``/series``); sin ``serie_id`` devuelve todas las de ese tipo. */
export async function getSeries(seriesType: string, serieId?: string): Promise<SeriesPoint[]> {
  const query: { series_type: string; series_id: string | null } = {
    series_type: seriesType,
    series_id: serieId ?? null,
  };
  return (await apiGet("/series", query)) as unknown as SeriesPoint[];
}

/** Puntos de cambio de una serie (``/changes``); todos si se omite ``serie``. */
export async function getChanges(serie: string, serieId?: string): Promise<Change[]> {
  return (await apiGet("/changes", {
    serie,
    serie_id: serieId ?? null,
  })) as unknown as Change[];
}

/** Estadísticos por cambio (``/changes/stats``); toda la familia si se omite ``serie``. */
export async function getChangesStats(serie?: string): Promise<ChangeStats[]> {
  return (await apiGet("/changes/stats", { serie: serie ?? null })) as unknown as ChangeStats[];
}

/** Tópicos con etiqueta y tamaño (``/topics``). */
export async function getTopics(): Promise<Topic[]> {
  return (await apiGet("/topics")) as unknown as Topic[];
}

/** Fila de la rejilla de selección de hiperparámetros (``/topics/selection``). */
export interface TopicSelectionRow {
  min_topic_size: number;
  n_neighbors: number;
  min_samples: number;
  n_topics: number;
  outlier_rate: number;
  coherence: number;
  diversity: number;
  selected: number;
}

/** Métricas de validación humana de sentimiento (``/sentiment``). */
export interface MetricRow {
  nivel: string;
  n: number;
  accuracy: number;
  balanced_accuracy: number;
  reweighted_accuracy: number;
  f1_macro: number;
  kappa_linear: number;
  kappa_quadratic: number;
}

/** Intervalo de confianza bootstrap (``/sentiment`` → ``revision_ic``). */
export interface IcRow {
  nivel: string;
  metrica: string;
  variante: string;
  estimador: number;
  ic_inf: number;
  ic_sup: number;
  n_boot: number;
  alpha: number;
}

/** Acuerdo a tres bandas entre anotadores (``/sentiment`` → ``acuerdo_3bandas``). */
export interface AcuerdoRow {
  par: string;
  nivel: string;
  n: number;
  acuerdo: number;
  kappa_linear: number;
  kappa_quadratic: number;
  fleiss_kappa: number | null;
}

/** Payload de ``GET /sentiment`` con sus cuatro tablas. */
export interface SentimentPayload {
  revision_metricas: MetricRow[];
  revision_ic: IcRow[];
  acuerdo_3bandas: AcuerdoRow[];
  concordancia_llm: MetricRow[];
}

/** Matriz de confusión de ``GET /sentiment/confusion/{level}``. */
export interface ConfusionMatrix {
  nivel: string;
  index: string[];
  columns: string[];
  values: number[][];
}

/** Anexo de sensibilidad de embeddings (``/sensitivity``, D-39). */
export interface EmbeddingRow {
  modelo: string;
  n_topicos: number;
  outlier_rate: number;
  coherencia_cv: number;
  diversidad: number;
  ari_vs_e5: number | null;
  nmi_vs_e5: number | null;
  n_comparables: number;
}

/** Fila de sensibilidad de la penalización de PELT (``/changes/sensitivity``). */
export interface ChangeSensitivityRow {
  serie: string;
  serie_id: string;
  factor: number;
  penalizacion: number;
  n_cambios: number;
}

/** Rejilla completa de selección de hiperparámetros (D-32). */
export async function getTopicsSelection(): Promise<TopicSelectionRow[]> {
  return (await apiGet("/topics/selection")) as unknown as TopicSelectionRow[];
}

/** Tablas de validación de sentimiento (D-36/D-37). */
export async function getSentiment(): Promise<SentimentPayload> {
  return (await apiGet("/sentiment")) as unknown as SentimentPayload;
}

/** Matriz de confusión por nivel (``senti_3`` o ``senti_6``). */
export async function getConfusion(level: "senti_3" | "senti_6"): Promise<ConfusionMatrix> {
  return (await apiGet("/sentiment/confusion/{level}", undefined, {
    level,
  })) as unknown as ConfusionMatrix;
}

/** Anexo de sensibilidad de embeddings (D-39). */
export async function getSensitivity(): Promise<EmbeddingRow[]> {
  return (await apiGet("/sensitivity")) as unknown as EmbeddingRow[];
}

/** Sensibilidad de la penalización de PELT por serie. */
export async function getChangesSensitivity(): Promise<ChangeSensitivityRow[]> {
  return (await apiGet("/changes/sensitivity")) as unknown as ChangeSensitivityRow[];
}

/** Detalle de tópico con textos representativos (``/topics/{topic_id}``). */
export interface TopicDetail {
  topic: number;
  size: number;
  share: number;
  top_terms: string;
  representative_utterance_ids: string[];
  representative_texts: string[];
  label: string | null;
  description: string | null;
  reviewed_by: string | null;
}

/** Detalle de un tópico concreto (términos y documentos representativos). */
export async function getTopicDetail(topicId: number): Promise<TopicDetail> {
  return (await apiGet("/topics/{topic_id}", undefined, {
    topic_id: String(topicId),
  })) as unknown as TopicDetail;
}

/** Fila de la tabla de eventos (``/events``, espejo D-13). */
export interface EventRow {
  evento: string;
  fecha: string;
  tipo: string;
  fuente: string;
  notas: string;
}

/** Asociación exploratoria evento↔serie (``/events/relations``, D-09). */
export interface EventRelation {
  evento: string;
  serie: string;
  serie_id: string;
  rho: number | null;
  p: number | null;
  q: number | null;
  n: number;
  media_en_ventana: number | null;
  media_fuera: number | null;
}

/** Tabla de eventos versionada (``/events``). */
export async function getEvents(): Promise<EventRow[]> {
  return (await apiGet("/events")) as unknown as EventRow[];
}

/** Asociaciones exploratorias evento↔serie (``/events/relations``). */
export async function getEventRelations(): Promise<EventRelation[]> {
  return (await apiGet("/events/relations")) as unknown as EventRelation[];
}

/** KPI de la home editorial (``/home``). */
export interface HomeKpis {
  intervenciones: number;
  topicos: number;
  cambios_significativos: number;
  fechas: number;
  cambio_tono: string | null;
}

/** Cambio significativo con etiqueta e impacto para el timeline. */
export interface HomeChange {
  serie: string;
  serie_id: string;
  fecha: string;
  delta: number;
  media_antes: number;
  media_despues: number;
  tamano_serie: number;
  n_puntos: number;
  q: number;
  p: number;
  r: number;
  n: number;
  significativo_bh: number;
  label: string;
  impacto: number | null;
}

/** Punto mensual del tono real y del contrafactual por composición. */
export interface ToneCounterfactualPoint {
  month: string;
  n: number;
  neg_share_real: number;
  neg_share_ajustado: number;
  senti_n_real: number;
  senti_n_ajustado: number;
  brecha_neg: number;
  brecha_senti: number;
  base_start: string;
  base_end: string;
}

/** Contribución de un partido a un cambio de tópico o de tono. */
export interface EpisodeActor {
  partido: string;
  contribucion: number | null;
  contribucion_dentro?: number | null;
  contribucion_composicion?: number | null;
  n_antes: number | null;
  n_despues: number | null;
}

/** Tópico dentro de un episodio editorial. */
export interface EpisodeTopic {
  topic: number;
  label: string;
  fecha_cambio: string;
  meses_distancia: number;
  delta: number;
  q: number | null;
  n: number | null;
  tamano_serie: number | null;
  significativo_bh: number;
  direccion: "up" | "down";
  actores: EpisodeActor[];
}

/** Cambio de tono dentro de un episodio editorial. */
export interface EpisodeTone {
  fecha_cambio: string;
  delta_serie: number | null;
  delta_share_negativo: number | null;
  delta_senti_n: number | null;
  q: number | null;
  significativo_bh: number;
  intervalos: {
    metrica: string;
    delta: number | null;
    ic_inf: number | null;
    ic_sup: number | null;
    n_boot: number | null;
  }[];
  actores: EpisodeActor[];
}

/** Evento o hipótesis dentro de un episodio editorial. */
export interface EpisodeEvent {
  hipotesis_id?: string;
  serie?: string;
  serie_id?: string;
  metrica?: string;
  delta?: number | null;
  q?: number | null;
  significativo_bh?: number;
  direccion_esperada?: string;
  episodio_evento_id?: string;
  titulo?: string;
  fecha_ancla?: string;
  eventos?: string;
  resumen?: string;
}

/** Ficha editorial de un episodio. */
export interface Episode {
  episodio_id: string;
  titulo: string;
  fecha: string;
  resumen: string;
  fuente: string;
  reviewed_by: string;
  topicos: EpisodeTopic[];
  tono: EpisodeTone | null;
  eventos: EpisodeEvent[];
}

/** Serie mensual de un partido (``/actors``). */
export interface ActorPoint {
  month: string;
  party_family: string;
  party_status: string;
  n: number;
  n_assigned: number;
  share_all: number | null;
  share_assigned: number | null;
  tone_mean: number | null;
  negative_share: number | null;
  outlier_rate: number | null;
  has_session: boolean;
}

/** Fila del event study (``/events/alignment``). */
export interface EventAlignmentRow {
  hipotesis_id: string;
  episodio_id: string;
  serie: string;
  serie_id: string;
  metrica: string;
  fecha_ancla: string;
  ventana_meses: number;
  n_antes: number;
  n_despues: number;
  valor_antes: number;
  valor_despues: number;
  delta: number;
  p: number;
  q: number;
  significativo_bh: number;
  direccion_esperada: string;
  subfamilia: string;
  justificacion: string;
}

/** Bundle completo de la home editorial. */
export interface HomePayload {
  tesis: { titular: string; subtitulo: string };
  kpis: HomeKpis;
  tono: ToneCounterfactualPoint[];
  episodios: Episode[];
  actores: ActorPoint[];
  actores_cambio: ActorChangeRow[];
  eventos: EventAlignmentRow[];
  cambios: HomeChange[];
  caveats: string[];
}

/** Bundle de la home (``/home``). */
export async function getHome(): Promise<HomePayload> {
  return (await apiGet("/home")) as unknown as HomePayload;
}

/** Episodios editoriales del MVP (``/episodes``). */
export async function getEpisodes(): Promise<Episode[]> {
  return (await apiGet("/episodes")) as unknown as Episode[];
}

/** Detalle de un episodio editorial (``/episodes/{episode_id}``). */
export async function getEpisode(episodeId: string): Promise<Episode> {
  return (await apiGet("/episodes/{episode_id}", undefined, {
    episode_id: episodeId,
  })) as unknown as Episode;
}

/** Series de actores (``/actors``), filtrables por partido y estatus. */
export async function getActors(
  partyFamily?: string,
  partyStatus?: string
): Promise<ActorPoint[]> {
  return (await apiGet("/actors", {
    party_family: partyFamily ?? null,
    party_status: partyStatus ?? null,
  })) as unknown as ActorPoint[];
}

/** Descomposición de actores por cambio (``/actors/changes``). */
export interface ActorChangeRow {
  serie: string;
  serie_id: string;
  fecha: string;
  metrica: string;
  nivel: string;
  partido: string;
  estatus: string;
  n_antes: number;
  n_despues: number;
  peso_antes: number | null;
  peso_despues: number | null;
  valor_antes: number | null;
  valor_despues: number | null;
  delta_total_serie: number;
  contribucion_dentro: number | null;
  contribucion_composicion: number | null;
  residual: number | null;
  significativo_bh: number;
  tamano_serie: number;
}

/** Descomposición intra-partido/composición (``/actors/changes``). */
export async function getActorChanges(params?: {
  serie?: string;
  serieId?: string;
  metrica?: string;
  nivel?: string;
  significativoBh?: number;
}): Promise<ActorChangeRow[]> {
  return (await apiGet("/actors/changes", {
    serie: params?.serie ?? null,
    serie_id: params?.serieId ?? null,
    metrica: params?.metrica ?? null,
    nivel: params?.nivel ?? null,
    significativo_bh: params?.significativoBh ?? null,
  })) as unknown as ActorChangeRow[];
}

/** Resultados del event study (``/events/alignment``). */
export async function getEventAlignment(params?: {
  subfamilia?: string;
  significativoBh?: number;
  maxQ?: number;
}): Promise<EventAlignmentRow[]> {
  return (await apiGet("/events/alignment", {
    subfamilia: params?.subfamilia ?? null,
    significativo_bh: params?.significativoBh ?? null,
    max_q: params?.maxQ ?? null,
  })) as unknown as EventAlignmentRow[];
}

/** Tono real y contrafactual (``/tone/counterfactual``). */
export async function getToneCounterfactual(): Promise<ToneCounterfactualPoint[]> {
  return (await apiGet("/tone/counterfactual")) as unknown as ToneCounterfactualPoint[];
}

/** IC bootstrap del cambio de tono (``/tone/ci``). */
export async function getToneCi(): Promise<
  { metrica: string; fecha: string; delta: number; ic_inf: number; ic_sup: number; n_boot: number; n_antes: number; n_despues: number }[]
> {
  return (await apiGet("/tone/ci")) as unknown as {
    metrica: string;
    fecha: string;
    delta: number;
    ic_inf: number;
    ic_sup: number;
    n_boot: number;
    n_antes: number;
    n_despues: number;
  }[];
}
