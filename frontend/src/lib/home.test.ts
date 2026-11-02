import { describe, expect, it } from "vitest";
import type { ActorChangeRow, HomeChange } from "@/lib/api";
import {
  availableActors,
  changeType,
  filterChanges,
  hypothesisLabelById,
  indexActorChanges,
  topActorForChange,
} from "@/lib/home";

function change(overrides: Partial<HomeChange> = {}): HomeChange {
  return {
    serie: "topic",
    serie_id: "1",
    fecha: "2020-03-01",
    delta: 0.1,
    media_antes: 0.1,
    media_despues: 0.2,
    tamano_serie: 100,
    n_puntos: 82,
    q: 0.01,
    p: 0.01,
    r: 0.5,
    n: 82,
    significativo_bh: 1,
    label: "Energía",
    impacto: 1.2,
    ...overrides,
  };
}

function actor(overrides: Partial<ActorChangeRow> = {}): ActorChangeRow {
  return {
    serie: "topic",
    serie_id: "1",
    fecha: "2020-03-01",
    metrica: "cuota_topico",
    nivel: "partido",
    partido: "Vox",
    estatus: "Todos",
    n_antes: 10,
    n_despues: 20,
    peso_antes: 0.1,
    peso_despues: 0.2,
    valor_antes: 0.1,
    valor_despues: 0.2,
    delta_total_serie: 0.1,
    contribucion_dentro: 0.02,
    contribucion_composicion: 0.08,
    residual: 0,
    significativo_bh: 1,
    tamano_serie: 100,
    ...overrides,
  };
}

describe("home helpers", () => {
  it("clasifica los cambios por tipo editorial", () => {
    expect(changeType({ serie: "tone", fecha: "2020-06-01" })).toBe("shock");
    expect(changeType({ serie: "topic", fecha: "2016-11-01" })).toBe("legislatura");
    expect(changeType({ serie: "topic", fecha: "2019-04-01" })).toBe("eleccion");
    expect(changeType({ serie: "topic", fecha: "2017-10-01" })).toBe("territorial");
    expect(changeType({ serie: "topic", fecha: "2015-07-01" })).toBe("contexto");
  });

  it("indexa actores de nivel partido y descarta residuales", () => {
    const rows = [
      actor(),
      actor({ partido: "__residual__", contribucion_dentro: 0.04 }),
      actor({ nivel: "partido_estatus", partido: "PP" }),
    ];
    const index = indexActorChanges(rows);
    const match = index.get("topic|1|2020-03-01") ?? [];
    expect(match).toHaveLength(1);
    expect(match[0]?.partido).toBe("Vox");
  });

  it("elige al actor con mayor contribución absoluta", () => {
    const index = indexActorChanges([
      actor(),
      actor({ partido: "PP", contribucion_dentro: 0.12, contribucion_composicion: 0.01 }),
    ]);
    expect(topActorForChange(change(), index)?.partido).toBe("PP");
    expect(availableActors(index)).toEqual(["PP"]);
  });

  it("filtra por tipo, actor y periodo", () => {
    const index = indexActorChanges([
      actor(),
      actor({ serie_id: "2", fecha: "2017-01-01", partido: "PP" }),
    ]);
    const changes = [
      change(),
      change({ serie_id: "2", fecha: "2017-01-01", label: "Corrupción", impacto: 0.5 }),
    ];
    expect(
      filterChanges(changes, index, { type: "shock", actor: "todos", period: "todos" })
    ).toHaveLength(1);
    expect(
      filterChanges(changes, index, { type: "todos", actor: "PP", period: "todos" })
    ).toHaveLength(1);
    expect(
      filterChanges(changes, index, { type: "todos", actor: "todos", period: "2018-2020" })
    ).toHaveLength(1);
  });

  it("traduce las hipótesis del event study", () => {
    expect(hypothesisLabelById("H07")).toContain("COVID");
    expect(hypothesisLabelById("H99")).toBe("H99");
  });
});
