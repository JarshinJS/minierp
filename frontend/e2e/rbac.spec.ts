import { expect, test } from "@playwright/test";
import { apiAs, write } from "./support/api";
import { authFile, type Role } from "./support/users";

/**
 * Role-based access, checked twice: what the UI offers, and what the server
 * actually allows. Hiding a button is a convenience; the 403 is the control.
 */
const SIDEBAR: Record<string, { visible: string[]; hidden: string[] }> = {
  admin: { visible: ["Dashboard", "Products", "Inventory", "Sales", "Reports", "Users & Roles"], hidden: [] },
  sales: { visible: ["Dashboard", "Products", "Sales", "Delivery"], hidden: ["Inventory", "Purchase", "Reports", "Users & Roles"] },
  accountant: { visible: ["Dashboard", "Reports"], hidden: ["Products", "Inventory", "Sales", "Users & Roles"] },
  trade: { visible: ["Dashboard", "Foreign Trade", "Blockchain"], hidden: ["Products", "Inventory", "Reports"] },
};

for (const [role, nav] of Object.entries(SIDEBAR)) {
  test.describe(`sidebar for ${role}`, () => {
    test.use({ storageState: authFile(role as Role) });
    test("shows exactly the modules the role may open", async ({ page }) => {
      await page.goto("/dashboard/");
      const sidebar = page.getByRole("navigation");
      for (const label of nav.visible) await expect(sidebar.getByRole("link", { name: label, exact: true })).toBeVisible();
      for (const label of nav.hidden) await expect(sidebar.getByRole("link", { name: label, exact: true })).toHaveCount(0);
    });
  });
}

test.describe("read-only catalogue for sales users", () => {
  test.use({ storageState: authFile("sales") });

  test("the UI offers no catalogue changes", async ({ page }) => {
    await page.goto("/products/list/");
    await expect(page.getByRole("heading", { name: "Products" })).toBeVisible();
    await expect(page.getByRole("row").nth(1)).toBeVisible();
    await expect(page.getByRole("link", { name: "New product" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /^Edit / })).toHaveCount(0);
  });

  test("and the API refuses them even when called directly", async () => {
    const api = await apiAs("sales");
    const res = await write(api, "post", "/api/products/", { name: "Sneaky", sku: "SNEAKY-1", category: "x", cost_price: "1", selling_price: "1" });
    expect(res.status()).toBe(403);
    await api.dispose();
  });
});

test.describe("modules outside the role", () => {
  test.use({ storageState: authFile("accountant") });

  test("opening one by URL shows a permission error, not data", async ({ page }) => {
    await page.goto("/inventory/");
    await expect(page.getByRole("alert").filter({ hasText: /permission/i }).first()).toBeVisible();
    await expect(page.getByRole("cell", { name: "FG-DTBL" })).toHaveCount(0);
  });

  test("the API answers 403", async () => {
    const api = await apiAs("accountant");
    expect((await api.get("/api/inventory/stock/")).status()).toBe(403);
    expect((await api.get("/api/users/")).status()).toBe(403);
    await api.dispose();
  });
});
