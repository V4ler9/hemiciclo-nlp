"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Episode, EpisodeActor, EpisodeEvent, EpisodeTopic } from "@/lib/api";
import { fmtDelta, fmtInt, fmtMonth, fmtP } from "@/lib/format";
import { hypothesisLabelById } from "@/lib/home";

function sortedTopics(episode: Episode): EpisodeTopic[] {
  return [...episode.topicos].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));
}

function topActors(actors: EpisodeActor[], limit = 3): EpisodeActor[] {
  return [...actors]
    .sort((a, b) => Math.abs(b.contribucion ?? 0) - Math.abs(a.contribucion ?? 0))
    .slice(0, limit);
}

function EventList({ events }: { events: EpisodeEvent[] }) {
  const hypotheses = events.filter((event) => event.hipotesis_id);
  if (hypotheses.length === 0) return null;
  return (
    <div className="mt-6">
      <h3 className="text-muted-foreground text-xs tracking-[0.2em] uppercase">
        Contraste con el episodio
      </h3>
      <ul className="mt-2 space-y-2 text-sm">
        {hypotheses.map((event) => (
          <li key={event.hipotesis_id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-foreground font-medium">
              {hypothesisLabelById(event.hipotesis_id ?? "")}
            </span>
            <span className="text-muted-foreground tabular-nums">
              Δ {fmtDelta(event.delta ?? 0)} · q = {fmtP(event.q ?? Number.NaN)}
            </span>
            <span
              className={
                event.significativo_bh === 1
                  ? "text-xs font-medium text-rose-800"
                  : "text-muted-foreground text-xs"
              }
            >
              {event.significativo_bh === 1 ? "Supera BH" : "No supera BH"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EpisodeDialog({ episode, onClose }: { episode: Episode | null; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const topics = useMemo(() => (episode ? sortedTopics(episode) : []), [episode]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (episode && !dialog.open) dialog.showModal();
    if (!episode && dialog.open) dialog.close();
  }, [episode]);

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialogRef.current) onClose();
      }}
      aria-labelledby="episode-dialog-title"
      className="border-border bg-background text-foreground fixed inset-0 m-auto max-h-[calc(100dvh-3rem)] w-[92vw] max-w-3xl overflow-auto rounded-lg border p-0 shadow-xl [&::backdrop]:bg-black/50"
    >
      {episode && (
        <div className="p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h2
              id="episode-dialog-title"
              className="text-foreground font-serif text-2xl font-semibold tracking-tight"
            >
              {episode.titulo}
            </h2>
            <p className="text-muted-foreground text-xs tabular-nums">
              {fmtMonth(episode.fecha)} · {episode.reviewed_by ? `revisado por ${episode.reviewed_by}` : "borrador sin revisión humana"}
            </p>
          </div>
          <p className="text-foreground mt-3 text-sm leading-7">{episode.resumen}</p>

          <div className="mt-6">
            <h3 className="text-muted-foreground text-xs tracking-[0.2em] uppercase">
              Tópicos que cambian
            </h3>
            <ul className="mt-3 space-y-4">
              {topics.map((topic) => (
                <li key={`${topic.topic}-${topic.fecha_cambio}`} className="border-border rounded border p-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                    <p className="text-foreground font-medium">{topic.label}</p>
                    <p className="text-muted-foreground text-xs tabular-nums">
                      {fmtMonth(topic.fecha_cambio)} · Δ {fmtDelta(topic.delta * 100)} pp · q ={" "}
                      {topic.q === null ? "n/d" : fmtP(topic.q)}
                    </p>
                  </div>
                  {topic.meses_distancia > 0 && (
                    <p className="text-muted-foreground mt-1 text-xs">
                      Cambio más cercano, a {fmtInt(topic.meses_distancia)} meses del episodio.
                    </p>
                  )}
                  <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                    {topActors(topic.actores).map((actor) => (
                      <li key={`${topic.topic}-${actor.partido}`} className="text-muted-foreground">
                        <span className="text-foreground font-medium">{actor.partido}</span>{" "}
                        <span className="tabular-nums">
                          {fmtDelta((actor.contribucion ?? 0) * 100)} pp
                        </span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </div>

          {episode.tono && (
            <div className="border-border mt-6 rounded border p-4">
              <h3 className="text-muted-foreground text-xs tracking-[0.2em] uppercase">
                El tono del episodio
              </h3>
              <p className="text-foreground mt-2 text-sm">
                Share negativo: <span className="font-medium tabular-nums">{fmtDelta((episode.tono.delta_share_negativo ?? 0) * 100)} pp</span>
                {" · "}senti_n: <span className="font-medium tabular-nums">{fmtDelta(episode.tono.delta_senti_n ?? 0)}</span>
                {" · "}q = {episode.tono.q === null ? "n/d" : fmtP(episode.tono.q)}
              </p>
              <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                {topActors(episode.tono.actores, 5).map((actor) => (
                  <li key={actor.partido} className="text-muted-foreground">
                    <span className="text-foreground font-medium">{actor.partido}</span>{" "}
                    <span className="tabular-nums">
                      {fmtDelta((actor.contribucion ?? 0) * 100)} pp
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <EventList events={episode.eventos} />

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-3">
              <Link
                href="/episodios"
                onClick={onClose}
                className="border-border text-foreground hover:bg-muted focus-visible:outline-foreground rounded border px-3 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2"
              >
                Ver todos los cambios →
              </Link>
              {topics[0] && (
                <Link
                  href={`/evidencias?topico=${topics[0].topic}`}
                  onClick={onClose}
                  className="border-border text-foreground hover:bg-muted focus-visible:outline-foreground rounded border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2"
                >
                  Evidencias del tópico principal →
                </Link>
              )}
            </div>
            <button
              type="button"
              onClick={onClose}
              autoFocus
              className="border-border text-foreground hover:bg-muted focus-visible:outline-foreground rounded border px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2"
            >
              Cerrar
            </button>
          </div>
          <p className="text-muted-foreground mt-4 text-xs">Fuente: {episode.fuente}</p>
        </div>
      )}
    </dialog>
  );
}

/**
 * Acto 3: línea de tiempo editorial de los cinco episodios del MVP. Cada
 * tarjeta abre una ficha con los tópicos, los actores y el contraste con el
 * event study; las tarjetas son botones accesibles y el diálogo nativo
 * conserva ESC, foco y fondo.
 */
export function EpisodeTimeline({ episodes }: { episodes: Episode[] }) {
  const [active, setActive] = useState<Episode | null>(null);
  const ordered = useMemo(
    () => [...episodes].sort((a, b) => a.fecha.localeCompare(b.fecha)),
    [episodes]
  );

  return (
    <section aria-labelledby="episodios-home-heading" className="border-border mt-14 border-t pt-8">
      <p className="text-muted-foreground text-xs tracking-[0.25em] uppercase">Acto 3 · Los episodios</p>
      <h2
        id="episodios-home-heading"
        className="text-foreground mt-2 font-serif text-3xl font-semibold tracking-tight"
      >
        Cinco momentos en los que la agenda salta
      </h2>
      <p className="text-foreground mt-3 max-w-3xl text-[0.95rem] leading-7">
        No son los 30 cambios: son los episodios donde el cambio es grande, está fechado y tiene
        una historia política detrás. Cada ficha separa lo que cambió, quién lo movió y qué
        confirma —o no— el contraste con el episodio.
      </p>
      <ol className="border-border mt-8 space-y-4 border-l pl-6">
        {ordered.map((episode) => {
          const topics = sortedTopics(episode).slice(0, 2);
          return (
            <li key={episode.episodio_id} className="relative">
              <span
                aria-hidden="true"
                className="bg-foreground absolute top-6 -left-[1.72rem] size-2.5 rounded-full"
              />
              <button
                type="button"
                onClick={() => setActive(episode)}
                className="border-border hover:bg-muted/40 focus-visible:outline-foreground w-full rounded border p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <p className="text-muted-foreground text-[0.7rem] tracking-[0.2em] uppercase">
                    {fmtMonth(episode.fecha)}
                  </p>
                  <span className="text-muted-foreground text-xs">Abrir ficha →</span>
                </div>
                <h3 className="text-foreground mt-1 font-serif text-2xl font-semibold tracking-tight">
                  {episode.titulo}
                </h3>
                <p className="text-muted-foreground mt-2 text-sm leading-6">{episode.resumen}</p>
                <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                  {topics.map((topic) => (
                    <li key={topic.topic} className="text-muted-foreground">
                      <span className="text-foreground font-medium">{topic.label}</span>{" "}
                      <span className="tabular-nums">{fmtDelta(topic.delta * 100)} pp</span>
                    </li>
                  ))}
                  {episode.tono && (
                    <li className="text-rose-800">
                      Tono: {fmtDelta((episode.tono.delta_share_negativo ?? 0) * 100)} pp de share
                      negativo
                    </li>
                  )}
                </ul>
              </button>
            </li>
          );
        })}
      </ol>
      <EpisodeDialog episode={active} onClose={() => setActive(null)} />
    </section>
  );
}
