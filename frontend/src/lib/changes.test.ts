import { describe, expect, it } from "vitest";
import type { Change, ChangeStats, SeriesPoint, Topic } from "@/lib/api";
import { buildTopicCards, buildTopicHeatmap, buildToneView, toTimeline } from "@/lib/changes";
import { HEATMAP_TOPICS, MESES_REGULARES_MIN } from "@/lib/constants";

function topic(id: number, label: string | null, size = 100): Topic {
  return {
    topic: id,
    size,
    share: size / 400,
    top_terms: "economía; empleo",
    label,
    description: null,
    reviewed_by: null,
  };
}

function point(month: string, seriesId: string, value: number | null, n = 10): SeriesPoint {
  return {
    month,
    series_type: "topic",
    series_id: seriesId,
    value,
    n_interventions: n,
    has_session: value !== null,
  };
}

function months(count: number, prefix = "2020"): string[] {
  return Array.from(
    { length: count },
    (_, index) => `${prefix}-${String(index + 1).padStart(2, "0")}-01T00:00:00.000Z`
  );
}

describe("umbrales documentados", () => {
  it("fija los criterios de potencia y heatmap", () => {
    expect(MESES_REGULARES_MIN).toBe(10);
    expect(HEATMAP_TOPICS).toBe(20);
  });
});

describe("toTimeline", () => {
  it("filtra meses sin sesión, normaliza a AAAA-MM-DD y ordena", () => {
    const rows = [
      point("2020-03-01T00:00:00.000", "0", 0.3),
      point("2020-01-01T00:00:00.000", "0", 0.1),
      point("2020-02-01T00:00:00.000", "0", null),
    ];
    expect(toTimeline(rows)).toEqual([
      { month: "2020-01-01", value: 0.1 },
      { month: "2020-03-01", value: 0.3 },
    ]);
  });
});

describe("buildToneView", () => {
  const serie = [
    point("2015-10-01T00:00:00.000", "tone", 2.0),
    point("2015-11-01T00:00:00.000", "tone", 2.5),
  ];
  const change: Change = {
    serie: "tone",
    serie_id: "tone",
    fecha: "2015-11-01",
    indice: 1,
    media_antes: 2.0,
    media_despues: 2.5,
    delta: 0.5,
    pen_seleccionada: 1.0,
    n_cambios: 1,
    n_puntos: 2,
    tamano_serie: 40,
  };

  it("une el cambio con sus estadísticos", () => {
    const stats: ChangeStats[] = [
      {
        serie: "tone",
        serie_id: "tone",
        fecha: "2015-11-01",
        r: -0.4,
        p: 0.02,
        q: 0.05,
        n_antes: 1,
        n_despues: 1,
        n: 2,
        significativo_bh: 1,
      },
    ];
    const view = buildToneView(serie, [change], stats);
    expect(view.points).toHaveLength(2);
    expect(view.changes[0]?.r).toBe(-0.4);
    expect(view.changes[0]?.n).toBe(2);
  });

  it("marca NaN cuando faltan los estadísticos", () => {
    const view = buildToneView(serie, [change], []);
    expect(Number.isNaN(view.changes[0]?.r ?? Number.NaN)).toBe(true);
    expect(view.changes[0]?.n).toBe(0);
  });
});

describe("buildTopicCards", () => {
  function fixture(): {
    topics: Topic[];
    series: SeriesPoint[];
    changes: Change[];
    stats: ChangeStats[];
  } {
    const topics = [topic(0, "Economía"), topic(1, null), topic(2, "Sanidad")];
    const series: SeriesPoint[] = [];
    for (const month of months(12)) {
      series.push(point(month, "0", 0.1, 10));
      series.push(point(month, "1", 0.2, 1));
      series.push(point(month, "2", 0.3, 8));
    }
    const changes: Change[] = [
      {
        serie: "topic",
        serie_id: "1",
        fecha: "2020-05-01",
        indice: 4,
        media_antes: 0.1,
        media_despues: 0.3,
        delta: 0.9,
        pen_seleccionada: 1,
        n_cambios: 1,
        n_puntos: 12,
        tamano_serie: 12,
      },
      {
        serie: "topic",
        serie_id: "0",
        fecha: "2020-03-01",
        indice: 2,
        media_antes: 0.05,
        media_despues: 0.25,
        delta: 0.2,
        pen_seleccionada: 1,
        n_cambios: 1,
        n_puntos: 12,
        tamano_serie: 120,
      },
    ];
    const stats: ChangeStats[] = [
      {
        serie: "topic",
        serie_id: "0",
        fecha: "2020-03-01",
        r: 0.8,
        p: 0.001,
        q: 0.01,
        n_antes: 2,
        n_despues: 10,
        n: 12,
        significativo_bh: 1,
      },
    ];
    return { topics, series, changes, stats };
  }

  it("ordena por magnitud máxima de cambio descendente", () => {
    const { topics, series, changes, stats } = fixture();
    const cards = buildTopicCards(topics, series, changes, stats);
    expect(cards.map((card) => card.topic)).toEqual([1, 0, 2]);
    expect(cards[2]?.changes).toHaveLength(0);
    expect(cards[2]?.maxDelta).toBe(0);
  });

  it("marca de baja potencia bajo el umbral de meses regulares", () => {
    const { topics, series, changes, stats } = fixture();
    const cards = buildTopicCards(topics, series, changes, stats);
    expect(cards[0]?.lowPower).toBe(true);
    expect(cards[0]?.mesesRegulares).toBe(0);
    expect(cards[1]?.lowPower).toBe(false);
    expect(cards[1]?.mesesRegulares).toBe(12);
  });

  it("conserva la etiqueta nula y une los estadísticos del cambio", () => {
    const { topics, series, changes, stats } = fixture();
    const cards = buildTopicCards(topics, series, changes, stats);
    expect(cards[0]?.label).toBeNull();
    expect(cards[1]?.label).toBe("Economía");
    expect(cards[1]?.changes[0]?.r).toBe(0.8);
    expect(cards[1]?.points[0]?.month).toBe("2020-01-01");
  });
});

describe("buildTopicHeatmap", () => {
  it("recorta a los tópicos top, trunca etiquetas y deja huecos sin datos", () => {
    const topics = Array.from({ length: HEATMAP_TOPICS + 2 }, (_, id) =>
      topic(
        id,
        id === 0 ? "Etiqueta larguísima que supera con creces el límite permitido" : `T${id}`,
        300 - id
      )
    );
    const series: SeriesPoint[] = [];
    for (const current of topics) {
      const id = String(current.topic);
      for (const month of months(2, "2021")) {
        const missing = current.topic === HEATMAP_TOPICS - 1 && month.startsWith("2021-02");
        series.push(point(month, id, missing ? null : current.topic / 1000, 100 - current.topic));
      }
    }

    const view = buildTopicHeatmap(series, topics);
    expect(view.labels).toHaveLength(HEATMAP_TOPICS);
    expect(view.months).toEqual(["2021-01-01", "2021-02-01"]);
    expect(view.labels[0]?.startsWith("Etiqueta larguísima")).toBe(true);
    expect(view.labels[0]?.length).toBe(42);
    expect(view.values[0]?.[0]).toBeCloseTo(0);
    expect(view.counts[0]?.[0]).toBe(100);
    const holeRow = view.values[HEATMAP_TOPICS - 1];
    expect(holeRow?.[1]).toBeNull();
    expect(holeRow?.[0]).not.toBeNull();
    expect(view.counts[HEATMAP_TOPICS - 1]?.[1]).toBeNull();
    expect(view.counts[HEATMAP_TOPICS - 1]?.[0]).toBe(81);
    expect(view.max).toBeGreaterThan(0);
  });
});
