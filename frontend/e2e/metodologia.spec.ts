import { expect, test } from "@playwright/test";

test("metodología: las siete secciones y el resultado nulo están presentes", async ({ page }) => {
  await page.goto("/metodologia");
  await expect(page.getByRole("heading", { level: 1, name: "Metodología" })).toBeVisible();
  for (const name of [
    "Alcance de este panel",
    "Corpus y limpieza",
    "Modelado de tópicos",
    "Medición y validación del tono",
    "Series mensuales y cambios de régimen",
    "Trazabilidad y regeneración",
  ]) {
    await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
  }
  await expect(page.getByRole("heading", { level: 2, name: /resultado nulo/ })).toBeVisible();
  await expect(page.getByText("Resultado: nulo.")).toBeVisible();
  await expect(page.getByText(/45 de 136/)).toBeVisible();
  await expect(page.getByText(/0,254/)).toBeVisible();
});

test("metodología: tabla de8 eventos y heatmap del análisis exploratorio", async ({ page }) => {
  await page.goto("/metodologia");
  await expect(page.locator("table tbody tr")).toHaveCount(8);
  const figure = page.locator("figure", { hasText: "fig_eventos_correlaciones" });
  await expect(figure.locator('[role="img"] canvas').first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("fig_eventos_correlaciones")).toBeVisible();
});

test("metodología: el informe HTML de validación se sirve", async ({ page }) => {
  await page.goto("/metodologia");
  const link = page.locator('a[href="/informes/validacion_sentimiento_revision.html"]');
  await expect(link).toBeVisible();
  const response = await page.request.get("/informes/validacion_sentimiento_revision.html");
  expect(response.status()).toBe(200);
  expect((await response.text()).length).toBeGreaterThan(10_000);
});
