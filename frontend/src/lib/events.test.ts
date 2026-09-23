import { describe, expect, it } from "vitest";
import type { EventRelation, EventRow, Topic } from "@/lib/api";
import { ASSOCIATION_TOPICS } from "@/lib/constants";
import { buildEventsView } from "@/lib/events";

const EVENTS: EventRow[] = [
  { evento: "Zeta", fecha: "2020-06-01", tipo: "crisis", fuente: "test", notas: "" },
  { evento: "Alfa", fecha: "2018-03-01", tipo: "electoral", fuente: "test", notas: "" },
  { evento: "Medio", fecha: "2019-09-01", tipo: "social", fuente: "test", notas: "" },
];

function relation(serieId: string, evento: string, rho: number, q = 0.5): EventRelation {
  return {
    evento,
    serie: "topic",
    serie_id: serieId,
    rho,
    p: 0.2,
    q,
    n: 82,
    media_en_ventana: 0.1,
    media_fuera: 0.05,
  };
}

describe("buildEventsView", () => {
  const topics: Topic[] = Array.from({ length: ASSOCIATION_TOPICS + 2 }, (_, id) => ({
    topic: id,
    size: 100,
    share: 0.1,
    top_terms: "a; b",
    label: `Tópico ${id}`,
    description: null,
    reviewed_by: null,
  }));

  function fixture(): EventRelation[] {
    const rows: EventRelation[] = [];
    for (let id = 0; id < ASSOCIATION_TOPICS + 2; id += 1) {
      for (const event of EVENTS) {
        if (id === 5 && event.evento === "Medio") continue;
        rows.push(
          relation(String(id), event.evento, id === 0 && event.evento === "Alfa" ? 0.9 : 0.1)
        );
      }
    }
    rows.push({ ...relation("tone", "Alfa", 0.7), serie: "tone" });
    return rows;
  }

  it("ordena los eventos cronológicamente y descarta el tono", () => {
    const view = buildEventsView(fixture(), EVENTS, topics);
    expect(view.columns).toEqual(["Alfa", "Medio", "Zeta"]);
    expect(view.labels.every((label) => label !== "tono")).toBe(true);
  });

  it("recorta a los top tópicos por |rho| y respeta el orden", () => {
    const view = buildEventsView(fixture(), EVENTS, topics);
    expect(view.labels).toHaveLength(ASSOCIATION_TOPICS);
    expect(view.labels[0]).toBe("Tópico 0");
  });

  it("rellena rho, q y n con huecos donde falta el contraste", () => {
    const view = buildEventsView(fixture(), EVENTS, topics);
    const alfa = view.columns.indexOf("Alfa");
    const medio = view.columns.indexOf("Medio");
    expect(view.rho[0]?.[alfa]).toBe(0.9);
    expect(view.q[0]?.[alfa]).toBe(0.5);
    expect(view.n[0]?.[alfa]).toBe(82);
    expect(view.rho[5]?.[medio]).toBeNull();
  });

  it("fija un rango de color simétrico de al menos 0,6", () => {
    const small = buildEventsView(fixture(), EVENTS, topics);
    expect(small.maxAbs).toBeCloseTo(0.9);
    const tiny = buildEventsView(
      EVENTS.flatMap((event) => [relation("0", event.evento, 0.05)]),
      EVENTS,
      topics
    );
    expect(tiny.maxAbs).toBeCloseTo(0.6);
  });
});
