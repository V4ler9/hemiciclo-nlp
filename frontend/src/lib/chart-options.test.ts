import { describe, expect, it } from "vitest";
import { buildToneOption, buildTopicDetailOption, heatmapLog } from "@/lib/chart-options";
import type { ResultChange, TimelinePoint, TopicCard } from "@/lib/changes";
import { HEATMAP_LOG_EPS } from "@/lib/constants";

const CAMBIO: ResultChange = {
  fecha: "2015-10-01",
  delta: 0.401,
  mediaAntes: 2.1,
  mediaDespues: 2.5,
  r: -0.623077,
  p: 0.00000296,
  n: 82,
  nAntes: 52,
  nDespues: 30,
};

const POINTS: TimelinePoint[] = [
  { month: "2015-10-01", value: 2.4 },
  { month: "2015-11-01", value: 2.6 },
];

type ToneShape = {
  tooltip?: { formatter?: unknown };
  series?: Array<{ markLine?: { triggerLineEvent?: boolean; silent?: boolean } }>;
};

function toneFormatter(): (params: unknown) => string {
  const option = buildToneOption(POINTS, [CAMBIO]) as unknown as ToneShape;
  const formatter = option.tooltip?.formatter;
  if (typeof formatter !== "function") {
    throw new Error("el tooltip del héroe debe ser una función");
  }
  return formatter as (params: unknown) => string;
}

describe("heatmapLog", () => {
  it("acota en el piso para no producir −∞", () => {
    expect(heatmapLog(0)).toBeCloseTo(Math.log10(HEATMAP_LOG_EPS));
    expect(heatmapLog(0.05)).toBeCloseTo(Math.log10(0.05));
  });

  it("es monótona creciente", () => {
    expect(heatmapLog(0.001)).toBeLessThan(heatmapLog(0.01));
    expect(heatmapLog(0.01)).toBeLessThan(heatmapLog(0.05));
  });
});

describe("buildToneOption (hover con estadísticos)", () => {
  it("despierta las líneas de cambio para recibir el puntero", () => {
    const option = buildToneOption(POINTS, [CAMBIO]) as unknown as ToneShape;
    expect(option.series?.[0]?.markLine?.triggerLineEvent).toBe(true);
    expect(option.series?.[0]?.markLine?.silent).toBe(false);
  });

  it("al tocar la línea añade la ficha completa del cambio", () => {
    const html = toneFormatter()([
      {
        componentType: "series",
        axisValue: "oct 2015",
        seriesName: "Tono medio mensual",
        value: 2.4,
      },
      { componentType: "markLine", name: "oct 2015" },
    ]);
    expect(html).toContain("oct 2015");
    expect(html).toContain("Δ +0,401");
    expect(html).toContain("2,100 → 2,500");
    expect(html).toContain("r = -0,623");
    expect(html).toContain("p = 2,96e-6");
    expect(html).toContain("n = 82 meses");
    expect(html).toContain("antes: jun 2011");
  });

  it("sin línea bajo el puntero muestra mes y valor", () => {
    const html = toneFormatter()([
      {
        componentType: "series",
        axisValue: "nov 2015",
        seriesName: "Tono medio mensual",
        value: 2.6,
      },
    ]);
    expect(html).toContain("nov 2015");
    expect(html).toContain("2,600");
    expect(html).not.toContain("Δ");
  });
});

describe("buildTopicDetailOption (diálogo de la portada)", () => {
  const card: TopicCard = {
    topic: 3,
    label: "Energía",
    size: 500,
    mesesRegulares: 40,
    lowPower: false,
    points: POINTS,
    changes: [CAMBIO],
    maxDelta: 0.401,
  };

  it("devuelve ejes visibles y las líneas de cambio etiquetadas", () => {
    const option = buildTopicDetailOption(card) as unknown as {
      yAxis?: { axisLabel?: unknown };
      series?: Array<{ markLine?: { label?: { formatter?: string }; data?: unknown[] } }>;
    };
    expect(option.yAxis?.axisLabel).toBeTruthy();
    expect(option.series?.[0]?.markLine?.label?.formatter).toBe("{b}");
    expect(option.series?.[0]?.markLine?.data).toHaveLength(1);
  });
});
