import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { authFile } from "./support/users";

/** WCAG 2.1 A/AA checks with axe-core; any serious or critical violation fails. */
async function expectAccessible(page: import("@playwright/test").Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude("nextjs-portal") // Next.js dev/build indicator, not part of the app
    .analyze();
  const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(blocking.map((v) => `${v.id}: ${v.help} (${v.nodes.length}×)`)).toEqual([]);
}

test("sign-in page", async ({ page }) => {
  await page.goto("/login/");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expectAccessible(page);
});

test.describe("signed-in pages", () => {
  test.use({ storageState: authFile("admin") });

  for (const [name, url, heading] of [
    ["dashboard", "/dashboard/", /Welcome back/],
    ["product list", "/products/list/", "Products"],
    ["product form", "/products/create/", "New product"],
    ["inventory", "/inventory/", "Inventory"],
  ] as const) {
    test(name, async ({ page }) => {
      await page.goto(url);
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
      await page.waitForLoadState("networkidle");
      await expectAccessible(page);
    });
  }
});
