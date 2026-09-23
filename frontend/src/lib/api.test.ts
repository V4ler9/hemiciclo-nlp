import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiGet, isDynamicUsage } from "@/lib/api";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("apiGet", () => {
  it("resuelve y construye la URL con parámetros de ruta y query", async () => {
    const confusionFetch = vi.fn((_input: unknown, _init?: RequestInit) =>
      Promise.resolve(jsonResponse({ nivel: "senti_3" }))
    );
    vi.stubGlobal("fetch", confusionFetch);
    const data = await apiGet("/sentiment/confusion/{level}", undefined, { level: "senti_3" });
    expect(data).toEqual({ nivel: "senti_3" });
    expect(String(confusionFetch.mock.calls[0]?.[0])).toContain("/sentiment/confusion/senti_3");

    const seriesFetch = vi.fn((_input: unknown, _init?: RequestInit) =>
      Promise.resolve(jsonResponse([]))
    );
    vi.stubGlobal("fetch", seriesFetch);
    await apiGet("/series", { series_type: "topic", series_id: null });
    const url = String(seriesFetch.mock.calls[0]?.[0]);
    expect(url).toContain("series_type=topic");
    expect(url).not.toContain("series_id");
  });

  it("convierte fallos de red en ApiError con status 0", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("fetch failed")))
    );
    const error = await apiGet("/meta").catch((cause: unknown) => cause);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0 });
    expect((error as Error).message).toContain("No se pudo conectar");
  });

  it("traduce el 503 del servidor al detalle del artefacto", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({ detail: "Artefacto no disponible: cambios_regimen.csv" }, 503)
        )
      )
    );
    await expect(apiGet("/changes", { serie: "tone" })).rejects.toMatchObject({
      status: 503,
      message: "Artefacto no disponible: cambios_regimen.csv",
    });
  });

  it("re-lanza el sentinel de rutas dinámicas de Next sin envolverlo", async () => {
    const dynamic = Object.assign(new Error("Dynamic server usage"), {
      digest: "DYNAMIC_SERVER_USAGE",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(dynamic))
    );
    await expect(apiGet("/meta")).rejects.toBe(dynamic);
  });
});

describe("isDynamicUsage", () => {
  it("reconoce solo el digest de Next", () => {
    expect(isDynamicUsage({ digest: "DYNAMIC_SERVER_USAGE" })).toBe(true);
    expect(isDynamicUsage({ digest: "OTRO" })).toBe(false);
    expect(isDynamicUsage(new Error("x"))).toBe(false);
    expect(isDynamicUsage(null)).toBe(false);
  });
});
