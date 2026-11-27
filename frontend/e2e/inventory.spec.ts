import { expect, test } from "@playwright/test";
import { createProduct } from "./support/api";
import { authFile, uid } from "./support/users";

test.use({ storageState: authFile("inventory") });

const row = (page: import("@playwright/test").Page, sku: string) => page.getByRole("row").filter({ hasText: sku });

test.describe("Inventory", () => {
  test("the out-of-stock tile filters the stock list", async ({ page }) => {
    await page.goto("/inventory/");
    await page.getByRole("button", { name: /Out of stock/ }).click();
    await expect(page).toHaveURL(/stock=out_of_stock/);
    await expect(row(page, "FG-BED")).toBeVisible();
    await expect(row(page, "HW-HNGE")).toBeVisible();
    await expect(row(page, "RM-TEAK")).toHaveCount(0);
  });

  test("a stock receipt updates on-hand and is written to the ledger", async ({ page }) => {
    const product = await createProduct("inventory", { sku: `E2E-${uid()}`, name: "Cedar Shelf Board" });
    const reference = `GRN-${uid()}`;
    await page.goto(`/inventory/?search=${product.sku}`);
    await expect(row(page, product.sku).getByRole("cell").nth(3)).toHaveText("0");

    await row(page, product.sku).getByRole("button", { name: "Adjust" }).click();
    const dialog = page.getByRole("dialog", { name: "Adjust stock" });
    await dialog.getByLabel("Quantity").fill("25");
    await dialog.getByLabel("Reference").fill(reference);
    await dialog.getByRole("button", { name: "Record receipt" }).click();
    await expect(dialog).toBeHidden();
    await expect(row(page, product.sku).getByRole("cell").nth(3)).toHaveText("25");

    await page.getByRole("tab", { name: "Movement ledger" }).click();
    await page.getByRole("searchbox", { name: "Reference…" }).fill(reference);
    const entry = row(page, reference);
    await expect(entry).toContainText("Receipt");
    await expect(entry).toContainText("+25");
  });

  test("issuing more than is on hand is refused with the server's reason", async ({ page }) => {
    const product = await createProduct("inventory", { sku: `E2E-${uid()}`, name: "Maple Veneer" });
    await page.goto(`/inventory/?search=${product.sku}`);
    await row(page, product.sku).getByRole("button", { name: "Adjust" }).click();
    const dialog = page.getByRole("dialog", { name: "Adjust stock" });
    await dialog.getByText("Issue (stock out)").click();
    await dialog.getByLabel("Quantity").fill("5");
    await dialog.getByRole("button", { name: "Record issue" }).click();
    await expect(dialog.getByRole("alert")).toContainText(`only 0.00 on hand for ${product.name}`);
    await page.keyboard.press("Escape");
    await expect(row(page, product.sku).getByRole("cell").nth(3)).toHaveText("0");
  });
});
