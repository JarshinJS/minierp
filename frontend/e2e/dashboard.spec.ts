import { expect, test } from "@playwright/test";
import { authFile } from "./support/users";

test.describe("Dashboard for an owner", () => {
  test.use({ storageState: authFile("owner") });

  test("shows business KPIs, charts and live alerts", async ({ page }) => {
    await page.goto("/dashboard/");
    for (const widget of ["Products Catalog", "Inventory Levels", "Sales Activity", "Purchase Activity"]) {
      await expect(page.getByText(widget, { exact: true })).toBeVisible();
    }
    await expect(page.getByRole("heading", { name: "Sales order value" })).toBeVisible();
    // Seed data has out-of-stock items, so the low-stock card lists them.
    await expect(page.getByRole("cell", { name: "Queen Bed Frame" })).toBeVisible();
  });

  test("every chart can be read as a table", async ({ page }) => {
    await page.goto("/dashboard/");
    const card = page.locator(".card").filter({ has: page.getByRole("heading", { name: "Inventory movement" }) });
    await card.getByRole("button", { name: "Show table" }).click();
    await expect(card.getByRole("cell", { name: "Receipts" })).toBeVisible();
  });
});

test.describe("Dashboard for an accountant", () => {
  test.use({ storageState: authFile("accountant") });

  test("hides operational widgets the role can't act on", async ({ page }) => {
    await page.goto("/dashboard/");
    await expect(page.getByRole("heading", { name: /Welcome back/ })).toBeVisible();
    await expect(page.getByText("Sales Activity", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Low stock" })).toHaveCount(0);
  });
});
