import { expect, test } from "@playwright/test";

test("evidencias: el selector ofrece58 tópicos y carga su detalle", async ({ page }) => {
  await page.goto("/evidencias");
  const select = page.locator("#topic-select");
  await expect(select.locator("option")).toHaveCount(58);

  await select.selectOption({ index: 7 });
  const expected = ((await select.locator("option").nth(7).textContent()) ?? "").split(" · ")[0];
  const heading = page.getByRole("heading", { level: 3 });
  await expect(heading).toHaveText(expected as string, { timeout: 15_000 });
  await expect(page.getByText(/Términos c-TF-IDF/)).toBeVisible();
  await expect(page.getByText(/sin revisión humana|revisada por/)).toBeVisible();
});

test("evidencias: los textos representativos se expanden", async ({ page }) => {
  await page.goto("/evidencias");
  const firstSummary = page.locator("details summary").first();
  await expect(firstSummary).toBeVisible({ timeout: 15_000 });
  await firstSummary.click();
  await expect(page.locator("details p").first()).toBeVisible();
});

test("evidencias: el heatmap del panorama se renderiza", async ({ page }) => {
  await page.goto("/evidencias");
  const figure = page.locator("figure", { hasText: "fig_heatmap_topicos" });
  await expect(figure.locator('[role="img"] canvas').first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("fig_heatmap_topicos")).toBeVisible();
});
