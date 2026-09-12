import { expect, test } from "@playwright/test";

test("demo: website phishing audit with RDAP evidence", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByRole("button", { name: "Demo", exact: true }).click();
  const websiteTarget = page.getByRole("button", { name: "Sitio web", exact: false });
  await websiteTarget.click();
  await expect(websiteTarget).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Analizar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Ofertas del Gobierno - Tienda Demo" })).toBeVisible();
  await expect(page.getByText(/Riesgo de phishing: alto/i)).toBeVisible();
  await expect(page.getByText("23 días", { exact: true })).toBeVisible();
  await expect(page.getByText("Registrador Demo", { exact: true })).toBeVisible();
  await expect(page.getByText("Evaluación del agente", { exact: true })).toBeVisible();
  await page.locator("details.evidence > summary").click();
  await expect(page.getByText("Posible suplantación gubernamental", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Compara tus opciones" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: /Mapa y recorrido/ })).toHaveCount(0);
  expect(errors).toEqual([]);
});
