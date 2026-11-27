import { expect, test } from "@playwright/test";
import { DEMO_PASSWORD, USERS } from "./support/users";

async function signIn(page: import("@playwright/test").Page, email: string, password = DEMO_PASSWORD) {
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test.describe("Signing in", () => {
  test("valid credentials land on the dashboard", async ({ page }) => {
    await page.goto("/login/");
    await signIn(page, USERS.admin.email);
    await expect(page).toHaveURL("/dashboard/");
    await expect(page.getByRole("heading", { name: `Welcome back, ${USERS.admin.name}` })).toBeVisible();
  });

  test("a wrong password is rejected without revealing which field was wrong", async ({ page }) => {
    await page.goto("/login/");
    await signIn(page, USERS.admin.email, "not-the-password");
    // (Next.js also renders an empty role=alert route announcer, hence the filter.)
    await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveText("Invalid email or password.");
    await expect(page).toHaveURL(/\/login\//);
  });

  test("a deep link survives the login detour", async ({ page }) => {
    await page.goto("/inventory/?tab=ledger");
    await expect(page).toHaveURL(/\/login\/\?next=/);
    await signIn(page, USERS.inventory.email);
    await expect(page).toHaveURL("/inventory/?tab=ledger");
    await expect(page.getByRole("tab", { name: "Movement ledger" })).toHaveAttribute("aria-selected", "true");
  });

  test("an off-site ?next= is ignored (no open redirect)", async ({ page }) => {
    // Browsers treat "\" like "/", so "/\evil.example" would otherwise leave the site.
    await page.goto("/login/?next=/%5Cevil.example/");
    await signIn(page, USERS.admin.email);
    await expect(page).toHaveURL("/dashboard/");
  });

  test("a pending account learns why it can't get in", async ({ page }) => {
    await page.goto("/login/");
    await signIn(page, USERS.pending.email);
    const notice = page.locator("[data-account-status=account_pending]");
    await expect(notice).toContainText("Waiting for approval");
    await expect(page).toHaveURL(/\/login\//);
  });
});

test.describe("Signing out", () => {
  // Signs in through the UI (not the shared saved session): logging out ends the
  // session server-side, which would sign out every other test using that state.
  test("ends the session for both the Next.js and the Django pages", async ({ page }) => {
    await page.goto("/login/");
    await signIn(page, USERS.sales.email);
    await expect(page).toHaveURL("/dashboard/");
    await page.getByRole("button", { name: new RegExp(USERS.sales.name) }).click();
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login\//);

    await page.goto("/products/list/");
    await expect(page).toHaveURL(/\/login\/\?next=/);
    // A Django-rendered page is protected by the same (now ended) session.
    await page.goto("/sales/list/");
    await expect(page).toHaveURL(/\/login\/\?next=%2Fsales%2Flist%2F|\/login\/\?next=\/sales\/list\//);
  });
});
