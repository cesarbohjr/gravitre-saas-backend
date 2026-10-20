import { defineConfig } from "@playwright/test"
import base from "./playwright.config"

export default defineConfig({
  ...base,
  testMatch: ["**/trial-expiry-billing-flow.spec.ts", "**/founder-billing-acceptance.spec.ts"],
  retries: 0,
  timeout: 180_000,
  use: { ...base.use, trace: "off", video: "off", screenshot: "only-on-failure" },
})
