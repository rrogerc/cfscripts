import { defineConfig, devices } from '@playwright/test';
import { iphonePresets, type IphonePreset } from './dev/iphone-presets';

const iphone = (preset: IphonePreset) => ({
  name: `iphone-${preset}`,
  testMatch: '**/app.spec.ts',
  metadata: { insets: iphonePresets[preset].insets },
  use: {
    ...devices['iPhone 17 Pro'],
    viewport: { width: iphonePresets[preset].width, height: iphonePresets[preset].height },
    screen: preset.endsWith('landscape') ? { width: 874, height: 402 } : { width: 402, height: 874 },
  },
});

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 4,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4175',
    colorScheme: 'dark',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop-chromium', testMatch: '**/app.spec.ts', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } },
    { name: 'desktop-webkit', testMatch: '**/app.spec.ts', use: { ...devices['Desktop Safari'], viewport: { width: 1440, height: 1000 } } },
    iphone('browser-portrait'),
    iphone('browser-landscape'),
    iphone('pwa-portrait'),
    iphone('pwa-landscape'),
    { name: 'pwa-chromium', testMatch: '**/pwa.spec.ts', use: { ...devices['Desktop Chrome'], serviceWorkers: 'allow' } },
    { name: 'preview', testMatch: '**/preview.spec.ts', use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:5175' } },
  ],
  webServer: [
    {
      command: 'npm run build && npm run preview -- --mode demo --host 127.0.0.1 --port 4175 --strictPort',
      url: 'http://127.0.0.1:4175',
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --mode demo --host 127.0.0.1 --port 5175 --strictPort',
      url: 'http://127.0.0.1:5175/dev/iphone.html',
      reuseExistingServer: false,
    },
  ],
});
