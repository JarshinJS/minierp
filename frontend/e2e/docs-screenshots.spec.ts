import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { authFile } from "./support/users";

/**
 * Regenerates the README screenshots from seeded demo data:
 *   npm run e2e:screenshots
 * Not part of the normal suite (project "docs").
 */
const OUT = path.resolve(__dirname, "../../docs/images");
mkdirSync(OUT, { recursive: true });

async function hideDevIndicator(page: import("@playwright/test").Page) {
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
}

test("login", async ({ page }) => {
  await page.goto("/login/");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await hideDevIndicator(page);
  await page.screenshot({ path: `${OUT}/login.png` });
});

test.describe("signed in", () => {
  test.use({ storageState: authFile("owner") });

  for (const [file, url, heading] of [
    ["dashboard", "/dashboard/", /Welcome back/],
    ["products", "/products/list/", "Products"],
    ["inventory", "/inventory/", "Inventory"],
    ["inventory-ledger", "/inventory/?tab=ledger", "Inventory"],
  ] as const) {
    test(file, async ({ page }) => {
      await page.goto(url);
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
      await page.waitForLoadState("networkidle");
      await hideDevIndicator(page);
      if (file === "dashboard") {
        // Grow the viewport to the page height (instead of fullPage) so the fixed
        // sidebar spans the whole image.
        const height = await page.evaluate(() => document.documentElement.scrollHeight);
        await page.setViewportSize({ width: 1440, height });
      }
      await page.screenshot({ path: `${OUT}/${file}.png` });
    });
  }

  test("adjust-dialog", async ({ page }) => {
    await page.goto("/inventory/?search=RM-OAK");
    await page.getByRole("row").filter({ hasText: "RM-OAK" }).getByRole("button", { name: "Adjust" }).click();
    await page.getByRole("dialog").getByLabel("Quantity").fill("40");
    await hideDevIndicator(page);
    await page.screenshot({ path: `${OUT}/adjust-dialog.png` });
  });
});

test.describe("on a phone", () => {
  test.use({ storageState: authFile("owner"), viewport: { width: 390, height: 844 }, isMobile: true });

  test("mobile-dashboard", async ({ page }) => {
    await page.goto("/dashboard/");
    await expect(page.getByRole("heading", { name: /Welcome back/ })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await hideDevIndicator(page);
    await page.screenshot({ path: `${OUT}/mobile-dashboard.png` });
  });
});
