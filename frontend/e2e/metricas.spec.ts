import { expect, test } from "@playwright/test";

test("métricas: las cuatro secciones están presentes", async ({ page }) => {
  await page.goto("/metricas");
  await expect(page.getByRole("heading", { level: 1, name: "Métricas" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Modelo de tópicos" })).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 2, name: /Validación de sentimiento/ })
  ).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Detección de cambios" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Calidad de datos" })).toBeVisible();
});

test("métricas: la rejilla de36 combinaciones tiene scroll con cabecera fija", async ({ page }) => {
  await page.goto("/metricas");
  const grid = page.locator("div.max-h-80").first();
  await expect(grid.locator("tbody tr")).toHaveCount(36);
  const scrollable = await grid.evaluate((el) => el.scrollHeight > el.clientHeight);
  expect(scrollable).toBe(true);
  const position = await grid.locator("thead").evaluate((el) => getComputedStyle(el).position);
  expect(position).toBe("sticky");
});

test("métricas: la tabla de contrastes tiene136 filas con nombres asignados", async ({ page }) => {
  await page.goto("/metricas");
  const table = page.locator("div.max-h-96");
  await expect(table.locator("tbody tr")).toHaveCount(136);
  const firstCell = table.locator("tbody tr").first().locator("td").first();
  await expect(firstCell).not.toHaveText(/^tópico \d+$/u);
});

test("métricas: el selector de confusión alterna entre3 y6 clases", async ({ page }) => {
  await page.goto("/metricas");
  const matrix = page.locator("table", { has: page.locator("caption") });
  await expect(matrix.locator("thead th")).toHaveCount(4);
  await page.getByRole("radio", { name: /6 clases/ }).check();
  await expect(matrix.locator("thead th")).toHaveCount(7);
});
