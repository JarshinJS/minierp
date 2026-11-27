import { expect, test } from "@playwright/test";
import { apiAs, write } from "./support/api";
import { latestOtp } from "./support/mail";
import { DEMO_PASSWORD, uid } from "./support/users";

test("request an account → verify the e-mailed code → admin approves → first sign-in", async ({ page }) => {
  const email = `new.hire.${uid().toLowerCase()}@example.com`;

  await test.step("request an account", async () => {
    await page.goto("/signup/");
    await page.getByLabel("Full name").fill("Nina Newhire");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel(/^Password/).fill(DEMO_PASSWORD);
    await page.getByLabel("Confirm password").fill(DEMO_PASSWORD);
    await page.getByRole("button", { name: "Continue" }).click();
    await expect(page).toHaveURL(/\/signup\/verify\//);
    await expect(page.getByText(email)).toBeVisible();
  });

  await test.step("a wrong code is refused", async () => {
    const code = await latestOtp(email);
    const wrong = code === "000000" ? "111111" : "000000";
    await page.getByLabel("Verification code").fill(wrong);
    await page.getByRole("button", { name: "Verify and create account" }).click();
    await expect(page.getByText("Invalid OTP. Please try again.")).toBeVisible();
  });

  await test.step("the right code creates a pending account", async () => {
    await page.getByLabel("Verification code").fill(await latestOtp(email));
    await page.getByRole("button", { name: "Verify and create account" }).click();
    await expect(page).toHaveURL(/\/login\/\?registered=1/);
    await expect(page.getByText("An administrator must approve your account")).toBeVisible();
  });

  await test.step("it can't be used until approved", async () => {
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(DEMO_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.locator("[data-account-status=account_pending]")).toBeVisible();
  });

  await test.step("an admin approves it as a sales user", async () => {
    const admin = await apiAs("admin");
    const found = await (await admin.get(`/api/users/?search=${encodeURIComponent(email)}`)).json();
    expect(found.results[0].account_status).toBe("PENDING");
    const res = await write(admin, "post", `/api/users/${found.results[0].id}/approve/`, { role: "SALES_USER" });
    expect(res.status()).toBe(200);
    await admin.dispose();
  });

  await test.step("now sign-in works and only sales modules are offered", async () => {
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL("/dashboard/");
    const nav = page.getByRole("navigation");
    await expect(nav.getByRole("link", { name: "Sales" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Inventory" })).toHaveCount(0);
  });
});
