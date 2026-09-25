import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const ROUTES = ["/", "/metricas", "/evidencias", "/metodologia"];

for (const route of ROUTES) {
  test(`accesibilidad WCAG2A/AA sin violaciones: ${route}`, async ({ page }) => {
    await page.goto(route);
    await page.waitForLoadState("load");
    // Deja hidratar los gráficos de ECharts antes de auditar el DOM.
    await page.waitForTimeout(2000);

    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();

    expect(
      results.violations.map((violation) => ({
        id: violation.id,
        impact: violation.impact,
        nodes: violation.nodes.length,
        help: violation.help,
      }))
    ).toEqual([]);
  });
}

test("accesibilidad WCAG2A/AA con el diálogo de ampliación abierto", async ({ page }) => {
  await page.goto("/");
  await page.locator('[aria-label^="Ampliar gráfico de"]').first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.waitForTimeout(800);

  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();

  expect(
    results.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.length,
      help: violation.help,
    }))
  ).toEqual([]);
});
