import { expect, test } from "@playwright/test";
import { authFile } from "./support/users";

test.use({ storageState: authFile("inventory") });

test("navigation works from the phone drawer @mobile", async ({ page }) => {
  await page.goto("/dashboard/");
  await page.getByRole("button", { name: "Open menu" }).click();
  await page.getByRole("link", { name: "Inventory", exact: true }).click();
  await expect(page).toHaveURL("/inventory/");
  await expect(page.getByRole("heading", { name: "Inventory" })).toBeVisible();
  // No horizontal page scroll at phone width (tables scroll inside their card).
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
