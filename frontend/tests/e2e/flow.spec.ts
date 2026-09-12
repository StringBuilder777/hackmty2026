import { test, expect } from "@playwright/test";
test("demo: analysis, offers, list, street route, branch, failures, offline restoration", async ({
  page,
  context,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page).toHaveTitle(/BuenPaso/);
  await expect(
    page.getByRole("heading", { name: "Compra con más contexto." }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Mapa y recorrido de pickup en Monterrey" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Demo", exact: true }).click();
  await page.getByRole("button", { name: "Analizar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Compara tus opciones" }),
  ).toBeVisible();
  await expect(page.getByText(/bandera.*verde/i)).toBeVisible();
  await page
    .getByRole("button", { name: "Agregar Demo Centro", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Mapa y recorrido de pickup en Monterrey" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Agregar Demo San Pedro", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Agregar Demo Online", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Mi lista (3)" }),
  ).toBeVisible();
  await expect(page.locator(".stop-icon")).toHaveCount(2);
  await expect(page.locator(".total")).toContainText("$22,446.00 MXN");
  await expect(page.locator(".total")).toContainText("2 costo(s)");
  await expect(page.locator(".route-panel")).toContainText("Ruta recomendada", {
    timeout: 25000,
  });
  await expect(page.locator(".leaflet-overlay-pane path")).toHaveCount(1);
  await page
    .getByLabel("Sucursal de Demo Centro")
    .selectOption("demo-obispado");
  await expect(page.locator(".route-panel")).toContainText("Ruta recomendada", {
    timeout: 25000,
  });
  await page.getByLabel("Modo de transporte").selectOption("walking");
  await expect(page.locator(".route-panel")).toContainText("ORS_API_KEY", {
    timeout: 25000,
  });
  await expect(page.locator(".stop-icon")).toHaveCount(2);
  await expect(page.locator(".leaflet-overlay-pane path")).toHaveCount(0);
  await page.getByLabel("Modo de transporte").selectOption("driving");
  await expect(page.locator(".route-panel")).toContainText("Ruta recomendada", {
    timeout: 25000,
  });
  // A source card focuses the matching marker; responsive layout never overflows.
  await page
    .getByRole("button", { name: "Ver en mapa", exact: true })
    .first()
    .click();
  await expect(page.locator(".stop-icon.selected")).toHaveCount(1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: `/private/tmp/buenpaso-${testInfo.project.name}.png`,
    fullPage: true,
  });
  await expect
    .poll(() =>
      page.evaluate(() => Boolean(navigator.serviceWorker.controller)),
    )
    .toBe(true);
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          JSON.parse(localStorage.getItem("buenpaso-v1-demo") || "{}").items
            ?.length,
      ),
    )
    .toBe(3);
  await context.setOffline(true);
  await expect(
    page.getByRole("button", { name: "Analizar", exact: true }),
  ).toBeDisabled();
  await expect(page.locator(".route-panel")).toContainText("Sin conexión");
  await expect(page.locator(".leaflet-tile")).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: "Demo", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Mi lista (3)" }),
  ).toBeVisible();
  await expect(page.locator(".saved-note")).toBeVisible();
  const cached = await page.evaluate(async () => {
    const keys = await caches.keys();
    return (
      await Promise.all(
        keys.map(async (key) =>
          (await (await caches.open(key)).keys()).map((r) => r.url),
        ),
      )
    ).flat();
  });
  expect(
    cached.some(
      (url) =>
        url.includes("tile.openstreetmap") ||
        url.includes("/analyses") ||
        url.includes(":8000"),
    ),
  ).toBe(false);
  await page
    .getByRole("button", { name: "Quitar Demo Centro", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Quitar Demo San Pedro", exact: true })
    .click();
  await expect(page.locator(".stop-icon")).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Mi lista (1)" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
