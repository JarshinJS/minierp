import { mkdirSync } from "node:fs";
import { expect, request, test as setup } from "@playwright/test";
import { authFile, DEMO_PASSWORD, ROLES, USERS } from "./support/users";

/**
 * Sign every seeded role in once through the real login API and save the session
 * cookies, so specs start authenticated (`test.use({ storageState: authFile(role) })`).
 * The login UI itself is covered by auth.spec.ts.
 */
setup("Django pages' CSS is built", async ({ request: http }) => {
  const css = await http.get("/static/css/dist/styles.css");
  expect(css.status(), "Django's Tailwind CSS is missing: run `npm ci && npm run build:css` in backend/").toBe(200);
});

setup("sign in every demo role", async () => {
  mkdirSync("e2e/.auth", { recursive: true });
  for (const role of ROLES) {
    const ctx = await request.newContext({ baseURL: "http://localhost:3100" });
    const csrf = await (await ctx.get("/api/auth/csrf/")).json();
    const res = await ctx.post("/api/auth/login/", {
      data: { email: USERS[role].email, password: DEMO_PASSWORD },
      headers: { "X-CSRFToken": csrf.csrfToken },
    });
    expect(res.status(), `login as ${role}`).toBe(200);
    await ctx.storageState({ path: authFile(role) });
    await ctx.dispose();
  }
});
