import { describe, expect, it } from "vitest";
import {
  fmtDelta,
  fmtInt,
  fmtMonth,
  fmtP,
  fmtQuota,
  fmtR,
  fmtTopicLabel,
  monthShift,
} from "@/lib/format";

describe("fmtMonth", () => {
  it("etiqueta meses en español con año", () => {
    expect(fmtMonth("2015-10-01")).toBe("oct 2015");
  });

  it("acepta Date y trunca marcas de tiempo ISO", () => {
    expect(fmtMonth("2016-09-01T00:00:00.000")).toBe("sept 2016");
    expect(fmtMonth(new Date(Date.UTC(2020, 0, 1)))).toBe("ene 2020");
  });

  it("rechaza fechas no válidas", () => {
    expect(() => fmtMonth("no-es-fecha")).toThrow(RangeError);
  });
});

describe("monthShift", () => {
  it("desplaza hacia atrás y hacia delante cruzando años", () => {
    expect(monthShift("2016-09-01", -15).toISOString()).toBe("2015-06-01T00:00:00.000Z");
    expect(monthShift("2016-09-01", 67).toISOString()).toBe("2022-04-01T00:00:00.000Z");
    expect(monthShift("2016-09-01", -1).toISOString()).toBe("2016-08-01T00:00:00.000Z");
  });
});

describe("formateadores numéricos", () => {
  it("fmtDelta usa signo tipográfico y coma decimal", () => {
    expect(fmtDelta(0.401)).toBe("+0,401");
    expect(fmtDelta(-0.306)).toBe("−0,306");
  });

  it("fmtDecimal devuelve n/d en no finitos", () => {
    expect(fmtDecimalSafe(0.7546, 4)).toBe("0,7546");
    expect(fmtDecimalSafe(Number.NaN)).toBe("n/d");
  });

  it("fmtP usa notación exponencial bajo 0,001", () => {
    expect(fmtP(0.00000296)).toBe("2,96e-6");
    expect(fmtP(0.5)).toBe("0,500");
    expect(fmtP(Number.NaN)).toBe("n/d");
  });

  it("fmtR firma con tres decimales", () => {
    expect(fmtR(-0.623077)).toBe("-0,623");
    expect(fmtR(Number.NaN)).toBe("n/d");
  });

  it("fmtInt usa el punto español como separador de miles", () => {
    expect(fmtInt(30027)).toBe("30.027");
  });

  it("fmtQuota muestra porcentaje con espacio", () => {
    expect(fmtQuota(0.32)).toMatch(/^32\s?%$/u);
    expect(fmtQuota(Number.NaN)).toBe("n/d");
  });
});

describe("fmtTopicLabel", () => {
  it("usa el id cuando no hay etiqueta", () => {
    expect(fmtTopicLabel(null, 7)).toBe("tópico 7");
  });

  it("trunca a42 caracteres con puntos suspensivos", () => {
    const long = "Etiqueta larguísima que supera con creces el límite permitido";
    const result = fmtTopicLabel(long, 0);
    expect(result.length).toBe(42);
    expect(result.endsWith("…")).toBe(true);
  });
});

function fmtDecimalSafe(value: number, digits?: number): string {
  if (!Number.isFinite(value)) return "n/d";
  return value.toLocaleString("es-ES", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}
