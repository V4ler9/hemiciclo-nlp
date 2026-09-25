"use client";

import { useEffect, useMemo, useState } from "react";
import { ApiErrorNotice, type ApiFailure } from "@/components/api-error";
import { ApiError, type Topic, type TopicDetail, getTopicDetail } from "@/lib/api";
import { fmtInt, fmtQuota } from "@/lib/format";

interface LoadedState {
  id: number;
  detail?: TopicDetail;
  failure?: ApiFailure;
}

function byLabel(a: Topic, b: Topic): number {
  const left = (a.label ?? `tópico ${a.topic}`).toLocaleLowerCase("es");
  const right = (b.label ?? `tópico ${b.topic}`).toLocaleLowerCase("es");
  return left.localeCompare(right, "es");
}

function toFailure(cause: unknown): ApiFailure {
  return {
    status: cause instanceof ApiError ? cause.status : null,
    detail: cause instanceof Error ? cause.message : "Error inesperado",
  };
}

/**
 * Selector de tópico con panel de evidencias.
 *
 * La carga es perezosa y el estado se deriva del dato (`loaded.id` frente a
 * `selected`), de modo que el efecto solo dispara trabajo asíncrono y los
 * `setState` ocurren en callbacks de promesa (regla `set-state-in-effect`).
 */
/** Selector de tópico con panel de evidencias (carga perezosa vía API).
 *
 * `initialTopic` permite el deep-link `?topico=N` de la portada (Q2).
 */
export function TopicEvidence({
  topics,
  initialTopic,
}: {
  topics: Topic[];
  initialTopic?: number;
}) {
  const sorted = useMemo(() => [...topics].sort(byLabel), [topics]);
  const [selected, setSelected] = useState(() => {
    const base = [...topics].sort(byLabel);
    if (initialTopic !== undefined && base.some((topic) => topic.topic === initialTopic)) {
      return initialTopic;
    }
    return base[0]?.topic ?? null;
  });
  const [loaded, setLoaded] = useState<LoadedState | null>(null);

  useEffect(() => {
    if (selected === null) return undefined;
    let cancelled = false;
    getTopicDetail(selected)
      .then((detail) => {
        if (cancelled) return;
        setLoaded({ id: selected, detail });
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setLoaded({ id: selected, failure: toFailure(cause) });
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const current = loaded && selected !== null && loaded.id === selected ? loaded : null;
  const loading = selected !== null && (current === null || (!current.detail && !current.failure));
  const detail = current?.detail ?? null;
  const failure = current?.failure ?? null;

  const terms = useMemo(
    () => (detail ? detail.top_terms.split("; ").filter(Boolean) : []),
    [detail]
  );
  const texts = useMemo(
    () =>
      detail
        ? detail.representative_texts
            .map((text, index) => ({
              id: detail.representative_utterance_ids[index] ?? "",
              text,
            }))
            .filter((entry) => entry.text.trim().length > 0)
        : [],
    [detail]
  );

  return (
    <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
      <div>
        <label
          htmlFor="topic-select"
          className="text-muted-foreground text-xs tracking-widest uppercase"
        >
          Tópico ({sorted.length})
        </label>
        <select
          id="topic-select"
          value={selected ?? ""}
          onChange={(event) => setSelected(Number(event.target.value))}
          className="border-border bg-background text-foreground focus-visible:outline-foreground mt-2 w-full rounded border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2"
        >
          {sorted.map((topic) => (
            <option key={topic.topic} value={topic.topic}>
              {topic.label ?? `tópico ${topic.topic}`} · {fmtInt(topic.size)}
            </option>
          ))}
        </select>
        <p className="text-muted-foreground mt-3 text-xs">
          Orden alfabético por etiqueta asignada (D-25). Las etiquetas son asistidas por LLM y{" "}
          {sorted.every((topic) => !topic.reviewed_by)
            ? "aún no han sido revisadas por una persona."
            : "se muestran con su estado de revisión."}
        </p>
      </div>

      <div className="border-border rounded border p-5">
        {loading && (
          <p role="status" className="text-muted-foreground animate-pulse text-sm">
            Cargando evidencias del tópico…
          </p>
        )}
        {!loading && failure && <ApiErrorNotice failure={failure} />}
        {!loading && !failure && detail && (
          <div>
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h3 className="text-foreground font-serif text-2xl font-semibold">
                {detail.label ?? `Tópico ${detail.topic}`}
              </h3>
              <p className="text-muted-foreground text-xs tabular-nums">
                tópico {detail.topic} · {fmtInt(detail.size)} intervenciones (
                {fmtQuota(detail.share)} de las asignadas)
              </p>
            </div>
            {detail.description && (
              <p className="text-muted-foreground mt-2 max-w-3xl text-sm">{detail.description}</p>
            )}
            <p className="text-muted-foreground mt-1 text-xs">
              {detail.reviewed_by
                ? `Etiqueta revisada por ${detail.reviewed_by}.`
                : "Etiqueta aún sin revisión humana (D-25: revisión pendiente)."}
            </p>

            <h4 className="text-muted-foreground mt-5 text-xs tracking-widest uppercase">
              Términos c-TF-IDF
            </h4>
            <ul className="mt-2 flex flex-wrap gap-2">
              {terms.map((term) => (
                <li
                  key={term}
                  className="border-border text-foreground rounded-full border px-2.5 py-0.5 text-xs"
                >
                  {term}
                </li>
              ))}
            </ul>

            <h4 className="text-muted-foreground mt-5 text-xs tracking-widest uppercase">
              Textos representativos ({texts.length})
            </h4>
            {texts.length > 0 ? (
              <ul className="mt-2 space-y-2">
                {texts.map((entry, index) => (
                  <li key={entry.id || String(index)}>
                    <details className="group border-border rounded border px-3 py-2">
                      <summary className="text-foreground focus-visible:outline-foreground cursor-pointer text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2">
                        Intervención representativa {index + 1}
                        {entry.id && (
                          <span className="text-muted-foreground ml-2 font-mono text-xs">
                            {entry.id}
                          </span>
                        )}
                      </summary>
                      <p className="border-border text-muted-foreground mt-2 border-l-2 pl-3 text-sm">
                        {entry.text}
                      </p>
                    </details>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground mt-2 text-sm">
                Este tópico no tiene textos representativos registrados.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
