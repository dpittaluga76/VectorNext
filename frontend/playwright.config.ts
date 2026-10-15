import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:4173', screenshot: 'only-on-failure' },
  webServer: process.env.VECTORNEXT_PLANNING_URL
    ? undefined
    : {
        command: 'npx vite preview --host 0.0.0.0',
        port: 4173,
        reuseExistingServer: false,
      },
})
