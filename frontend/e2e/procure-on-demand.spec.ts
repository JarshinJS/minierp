import { expect, test, type Page } from "@playwright/test";
import { apiAs, createProduct, write } from "./support/api";
import { authFile, uid } from "./support/users";

/**
 * Regression: the product form's "Procure on demand" checkbox decides whether a
 * stock shortage raises a procurement request. (It used to be ignored: every
 * shortage raised one.)
 */
test.use({ storageState: authFile("inventory") });

/** A confirmed sales order for more than is in stock (as the sales user, via the API). */
async function orderMoreThanInStock(productId: string, quantity: string) {
  const sales = await apiAs("sales");
  const created = await write(sales, "post", "/api/sales-orders/", {
    customer_name: `Shortage ${uid()}`,
    lines: [{ product: productId, quantity, unit_price: "100.00" }],
  });
  expect(created.status(), await created.text()).toBe(201);
  const order = await created.json();
  const confirmed = await write(sales, "post", `/api/sales-orders/${order.id}/confirm/`);
  expect(confirmed.status()).toBe(200);
  await sales.dispose();
  return order.order_number as string;
}

async function setProcureOnDemand(page: Page, productId: string, on: boolean) {
  await page.goto(`/products/${productId}/edit/`);
  const box = page.getByRole("checkbox", { name: /Procure on demand/ });
  await box.setChecked(on);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page).toHaveURL(`/products/${productId}/`);
  const row = page.locator("div").filter({ has: page.getByText("Procure on demand", { exact: true }) }).last();
  await expect(row.getByText(on ? "Enabled" : "Disabled")).toBeVisible();
}

test("ticked: a shortage raises a procurement request; unticked: it doesn't", async ({ page }) => {
  const tag = uid();
  const auto = await createProduct("inventory", { sku: `POD-ON-${tag}`, name: `Auto-procured Chair ${tag}` });
  const manual = await createProduct("inventory", { sku: `POD-OFF-${tag}`, name: `Manual Chair ${tag}` });

  await test.step("tick the checkbox on one product only", async () => {
    await setProcureOnDemand(page, auto.id, true);
    await setProcureOnDemand(page, manual.id, false);
  });

  const autoRef = await orderMoreThanInStock(auto.id, "4");
  const manualRef = await orderMoreThanInStock(manual.id, "4");

  await test.step("the API records a request only for the ticked product", async () => {
    const purchase = await apiAs("purchase");
    const triggers = (await (await purchase.get("/api/procurement/triggers/?limit=100")).json()).results as
      { reference: string; product_sku: string; quantity_needed: string }[];
    await purchase.dispose();
    expect(triggers.find((t) => t.reference === autoRef)).toMatchObject({ product_sku: auto.sku, quantity_needed: "4.00" });
    expect(triggers.find((t) => t.reference === manualRef)).toBeUndefined();
  });

  await test.step("the procurement page (still a Django page) shows the same", async () => {
    await page.goto("/procurement/trigger-dashboard/");
    await expect(page.getByRole("row").filter({ hasText: autoRef })).toContainText(auto.name);
    await expect(page.getByRole("row").filter({ hasText: manualRef })).toHaveCount(0);
  });

  await test.step("either way the shortage is still visible in inventory", async () => {
    await page.goto(`/inventory/?search=${tag}&stock=out_of_stock`);
    await expect(page.getByRole("row").filter({ hasText: auto.sku })).toBeVisible();
    await expect(page.getByRole("row").filter({ hasText: manual.sku })).toBeVisible();
  });
});
