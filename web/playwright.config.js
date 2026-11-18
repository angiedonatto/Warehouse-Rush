import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';

const macChrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
export default defineConfig({
  testDir: './tests',
  workers: 1,
  timeout: 90000,
  expect: { timeout: 15000 },
  reporter: 'list',
  use: {
    baseURL: process.env.WAREHOUSE_TEST_URL || 'http://127.0.0.1:8080',
    viewport: { width: 1440, height: 1040 },
    screenshot: 'only-on-failure',
    launchOptions: {
      ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : existsSync(macChrome) ? { executablePath: macChrome } : {}),
      args: ['--enable-webgl', '--enable-unsafe-swiftshader', '--use-angle=swiftshader'],
    },
  },
});
