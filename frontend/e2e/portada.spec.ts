import { expect, test } from "@playwright/test";

test("portada: héroe, tres fichas y rejilla con58 tarjetas", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("El tono del debate");
  await expect(
    page.getByRole("heading", { name: "Cambios de tono detectados", exact: true })
  ).toBeVisible();
  await expect(page.getByText("prevalencia, no de tono")).toBeVisible();
  await expect(page.getByText("Cambio de tono", { exact: true })).toHaveCount(3);

  // Hidratación: héroe (1) + sparklines de la rejilla (58)
  await expect(page.locator("canvas")).toHaveCount(59, { timeout: 20_000 });
  await expect(page.locator('[aria-label^="Cuota mensual del tópico"]')).toHaveCount(58);
});

test("portada: el filtro de baja potencia oculta exactamente12 tarjetas", async ({ page }) => {
  await page.goto("/");
  const charts = page.locator('[aria-label^="Cuota mensual del tópico"]');
  await expect(charts).toHaveCount(58, { timeout: 20_000 });
  await page.getByLabel(/Ocultar baja potencia/).check();
  await expect(charts).toHaveCount(46);
  await page.getByLabel(/Ocultar baja potencia/).uncheck();
  await expect(charts).toHaveCount(58);
});

test("portada: el delta muestra r, p, n e intervalo al pasar el ratón y al enfocar", async ({
  page,
}) => {
  await page.goto("/");
  const chip = page.locator('span[tabindex="0"]').first();
  await expect(chip).toBeVisible();
  const tooltipId = await chip.getAttribute("aria-describedby");
  expect(tooltipId).toBeTruthy();
  const tooltip = page.locator(`[id="${tooltipId as string}"]`);
  await expect(tooltip).toHaveCSS("opacity", "0");

  await chip.hover();
  await expect(tooltip).toHaveCSS("opacity", "1");
  await expect(tooltip).toContainText("r = ");
  await expect(tooltip).toContainText("p = ");
  await expect(tooltip).toContainText("n = ");
  await expect(tooltip).toContainText("antes:");

  const second = page.locator('span[tabindex="0"]').nth(1);
  await second.focus();
  const secondId = (await second.getAttribute("aria-describedby")) as string;
  await expect(page.locator(`[id="${secondId}"]`)).toHaveCSS("opacity", "1");
});

test("portada: el diálogo amplía el subgráfico con su tabla de respaldo (sin q)", async ({
  page,
}) => {
  await page.goto("/");
  const trigger = page.locator('[aria-label^="Ampliar gráfico de"]').first();
  await expect(trigger).toBeVisible();
  await trigger.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator("canvas").first()).toBeVisible({ timeout: 15_000 });
  for (const column of ["fecha", "Δ", "media antes → después", "r", "p", "n", "intervalo"]) {
    await expect(dialog.getByRole("columnheader", { name: column, exact: true })).toBeVisible();
  }
  await expect(dialog.getByRole("columnheader", { name: "q", exact: true })).toHaveCount(0);
  await expect(dialog.locator("table tbody tr").first()).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("portada: el diálogo enlaza con Evidencias vía ?topico=", async ({ page }) => {
  await page.goto("/");
  await page.locator('[aria-label^="Ampliar gráfico de"]').first().click();
  const link = page.getByRole("dialog").getByRole("link", { name: /Ver evidencias/ });
  await link.click();

  await expect(page).toHaveURL(/\/evidencias\?topico=\d+/);
  const topicId = new URL(page.url()).searchParams.get("topico");
  await expect(page.locator("#topic-select")).toHaveValue(topicId ?? "");
});
