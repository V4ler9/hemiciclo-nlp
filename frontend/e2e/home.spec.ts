import { expect, test } from "@playwright/test";

test("home: tesis, KPIs y cuatro gráficos", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "El Congreso cambia a saltos"
  );
  await expect(page.getByText("Cambios significativos", { exact: true })).toBeVisible();
  await expect(page.getByText("Fechas de cambio", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "El tono cae, pero no porque todos hablen peor" })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Cinco momentos en los que la agenda salta" })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "La Cámara cambia antes de que cambie el tono" })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Los shocks sí; el calendario electoral, poco" })
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Los 45 cambios significativos, uno a uno" })
  ).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(4, { timeout: 20_000 });
});

test("home: la ficha de episodio abre y se cierra con Escape", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Abrir ficha/ }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("heading", { level: 2 })).toContainText("Rajoy");
  await expect(dialog.getByText("Tópicos que cambian")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});

test("home: el explorador filtra por tipo y muestra la tabla de respaldo", async ({ page }) => {
  await page.goto("/");
  await page.locator("#explorer-type").selectOption("shock");
  await expect(page.getByText(/\d+ de 45 cambios/)).toBeVisible();
  const table = page.getByRole("region", {
    name: "Tabla de los cambios significativos filtrados",
  });
  await expect(table.locator("tbody tr").first()).toBeVisible();
  const count = await table.locator("tbody tr").count();
  expect(count).toBeGreaterThan(0);
  expect(count).toBeLessThan(45);
});
