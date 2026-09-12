import { defineConfig } from "@playwright/test";
const baseURL = process.env.E2E_BASE_URL || "http://localhost:3000";
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60000,
  workers: 1,
  use: { baseURL, channel: "chrome", trace: "off" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1536, height: 1024 } } },
    {
      name: "mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
