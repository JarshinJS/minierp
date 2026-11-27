import { existsSync } from "node:fs";
import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests: a real browser against a real Django + Next.js pair.
 *
 * `npm run e2e` starts both servers itself:
 *   - Django on :8100 with config.settings.e2e: a throwaway SQLite database that is
 *     reset and re-seeded (`seed_demo --reset`) on every run;
 *   - a production build of Next.js on :3100 that proxies /api/* and the
 *     not-yet-migrated Django pages to :8100, exactly as in production.
 */
const FRONTEND = "http://localhost:3100";
const BACKEND = "http://127.0.0.1:8100";
const isCI = !!process.env.CI;

const backendDir = path.resolve(__dirname, "../backend");
const venvPython = path.resolve(__dirname, "../.venv/bin/python");
const python = process.env.E2E_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  // Tests share one seeded database. They create their own uniquely named records,
  // but one worker keeps runs fully deterministic.
  workers: 1,
  fullyParallel: false,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: isCI
    ? [["github"], ["list"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: FRONTEND,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /global\.setup\.ts/ },
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
      testIgnore: [/docs-screenshots\.spec\.ts/],
      grepInvert: /@mobile/,
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 7"] },
      dependencies: ["setup"],
      grep: /@mobile/,
    },
    {
      // Regenerates docs/images/*.png for the README: `npm run e2e:screenshots`.
      name: "docs",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
      dependencies: ["setup"],
      testMatch: /docs-screenshots\.spec\.ts/,
    },
  ],
  webServer: [
    {
      command: `${python} manage.py migrate --noinput -v0 && ${python} manage.py seed_demo --reset && ${python} manage.py runserver 127.0.0.1:8100 --noreload`,
      cwd: backendDir,
      env: { DJANGO_SETTINGS_MODULE: "config.settings.e2e", PYTHONUNBUFFERED: "1" },
      url: `${BACKEND}/healthz/`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npm run build && npm run start -- -p 3100",
      env: { BACKEND_URL: BACKEND },
      url: `${FRONTEND}/login/`,
      reuseExistingServer: false,
      timeout: 240_000,
    },
  ],
});
