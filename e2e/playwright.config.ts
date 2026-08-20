import { defineConfig } from "@playwright/test";

// 共用 runner：spec 住 ../specs/<repo>-<需求slug>/，BASE_URL 由呼叫端顯式傳入（絕不寫死，防指到正式線）。
export default defineConfig({
  testDir: "./specs",
  timeout: 30_000,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL,
    trace: "on",
    screenshot: "only-on-failure",
    headless: true,
  },
});
