import { expect, test } from "@playwright/test";
import { createProduct } from "./support/api";
import { authFile, uid } from "./support/users";

test.use({ storageState: authFile("inventory") });

test.describe("Product catalogue", () => {
  test("required fields are validated by the server and shown per field", async ({ page }) => {
    await page.goto("/products/create/");
    await page.getByRole("button", { name: "Create product" }).click();
    for (const field of ["Product name", "SKU", "Category", "Cost price", "Selling price"]) {
      await expect(page.locator(".has-error").filter({ has: page.getByText(field, { exact: false }) }).first()).toBeVisible();
    }
  });

  test("create a product, then refuse a duplicate SKU", async ({ page }) => {
    const sku = `E2E-${uid()}`;
    await page.goto("/products/create/");
    await page.getByLabel("Product name").fill("Walnut Bookshelf");
    await page.getByLabel("SKU").fill(sku);
    await page.getByLabel("Category").selectOption({ label: "Finished Goods" });
    await page.getByLabel("Cost price").fill("5200");
    await page.getByLabel("Selling price").fill("11900");
    await page.getByRole("button", { name: "Create product" }).click();

    await expect(page.getByRole("heading", { name: "Walnut Bookshelf" })).toBeVisible();
    await expect(page).toHaveURL(/\/products\/[0-9a-f-]{36}\/$/);
    await expect(page.getByText("₹11,900.00")).toBeVisible();

    await page.goto("/products/create/");
    await page.getByLabel("Product name").fill("Duplicate");
    await page.getByLabel("SKU").fill(sku);
    await page.getByLabel("Category").selectOption({ label: "Finished Goods" });
    await page.getByLabel("Cost price").fill("1");
    await page.getByLabel("Selling price").fill("1");
    await page.getByRole("button", { name: "Create product" }).click();
    await expect(page.getByText("product with this sku already exists.")).toBeVisible();
  });

  test("search and filters live in the URL, so they survive a reload", async ({ page }) => {
    await page.goto("/products/list/");
    await page.getByRole("searchbox", { name: "Search name or SKU…" }).fill("oak");
    await expect(page).toHaveURL(/search=oak/);
    await expect(page.getByRole("link", { name: "Oak Dining Chair", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Teak Dining Table", exact: true })).toHaveCount(0);

    await page.reload();
    await expect(page.getByRole("searchbox", { name: "Search name or SKU…" })).toHaveValue("oak");
    await expect(page.getByRole("link", { name: "Oak Dining Chair", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Clear filters" }).click();
    await expect(page).toHaveURL("/products/list/");
    await expect(page.getByRole("link", { name: "Teak Dining Table", exact: true })).toBeVisible();
  });

  test("edit a price", async ({ page }) => {
    const product = await createProduct("inventory", { sku: `E2E-${uid()}`, name: "Pine Side Table", price: "3000.00" });
    await page.goto(`/products/${product.id}/edit/`);
    await page.getByLabel("Selling price").fill("3450");
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page).toHaveURL(`/products/${product.id}/`);
    await expect(page.getByText("₹3,450.00")).toBeVisible();
  });

  test("deactivate after confirming in a dialog", async ({ page }) => {
    const product = await createProduct("inventory", { sku: `E2E-${uid()}`, name: "Retired Stool" });
    await page.goto(`/products/list/?search=${product.sku}`);
    await page.getByRole("button", { name: `Deactivate ${product.name}` }).click();

    const dialog = page.getByRole("dialog", { name: "Deactivate product" });
    await expect(dialog).toContainText(product.name);
    await dialog.getByRole("button", { name: "Deactivate" }).click();
    await expect(dialog).toBeHidden();

    const row = page.getByRole("row").filter({ hasText: product.sku });
    await expect(row.getByText("Inactive")).toBeVisible();
    await page.getByRole("combobox", { name: "Status" }).selectOption("inactive");
    await expect(page.getByRole("link", { name: product.name, exact: true })).toBeVisible();
  });
});
