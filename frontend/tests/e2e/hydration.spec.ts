import { expect, test } from "@playwright/test";

test("hydrates deterministically before restoring the saved language", async ({ page }) => {
  const runtimeErrors: string[] = [];
  page.on("pageerror", (error) => runtimeErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") runtimeErrors.push(message.text());
  });
  await page.addInitScript(() => {
    localStorage.setItem("buenpaso_lang", "en");
    localStorage.setItem("lang", "en");
  });

  await page.goto("/#explorar");

  await expect(page.getByRole("link", { name: "Skip to results" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  expect(runtimeErrors.filter((message) => /hydration|server rendered text/i.test(message))).toEqual([]);
});
