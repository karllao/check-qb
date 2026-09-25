import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";

const python =
  process.env.CHECK_QB_TEST_PYTHON ||
  resolve(
    "..",
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 40000,
  use: { baseURL: "http://127.0.0.1:8877", trace: "retain-on-failure" },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1050 },
      },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: `"${python}" -m tests.ui_server`,
    cwd: "..",
    env: { PYTHONPATH: ".", PYTHONIOENCODING: "utf-8" },
    url: "http://127.0.0.1:8877/healthz",
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
