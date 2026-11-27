import { expect, test } from "@playwright/test";
import { authFile } from "./support/users";

/**
 * The migration architecture: Next.js serves rebuilt pages and proxies everything
 * else to Django on the same origin, so one session works across both.
 */
test.use({ storageState: authFile("sales") });

test("a not-yet-migrated Django page is served through Next.js with the same session", async ({ page }) => {
  const djangoCss = page.waitForResponse((r) => r.url().includes("/static/css/dist/styles.css"));
  await page.goto("/sales/list/");
  await expect(page).toHaveURL("/sales/list/");
  await expect(page).toHaveTitle(/Sales orders/);
  await expect(page.getByText("Lotus Interiors")).toBeVisible();
  expect((await djangoCss).status()).toBe(200);
});

test("moving between the two apps keeps you signed in", async ({ page }) => {
  await page.goto("/products/list/");
  await expect(page.getByRole("heading", { name: "Products" })).toBeVisible();

  await page.getByRole("navigation").getByRole("link", { name: "Sales", exact: true }).click();
  await expect(page).toHaveURL("/sales/list/");
  await expect(page.getByText("Lotus Interiors")).toBeVisible();

  // Django's own sidebar links back into the Next.js app.
  await page.goto("/sales/list/");
  await page.getByRole("link", { name: "Products", exact: true }).first().click();
  await expect(page).toHaveURL("/products/list/");
  await expect(page.getByRole("heading", { name: "Products" })).toBeVisible();
});
