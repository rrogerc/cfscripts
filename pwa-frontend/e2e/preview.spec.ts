import { test, expect } from '@playwright/test';

test('the live preview resizes the same app and keeps interactions working', async ({ page }, testInfo) => {
  await page.goto('/dev/iphone.html');
  await expect(page.getByText(/Sample data ·/)).toBeVisible();
  const app = page.frameLocator('#app');
  await app.getByRole('button', { name: 'Pick a problem' }).click();
  await expect(app.locator('.problem-statement .header .title')).toHaveText('A Walk Through the Array');
  await page.getByLabel('Orientation').selectOption('landscape');
  await expect(page.locator('#app')).toHaveCSS('width', '874px');
  await expect(app.locator('html')).toHaveCSS('--safe-area-left', '62px');
  await expect(app.locator('.problem-statement .header .title')).toHaveText('A Walk Through the Array');
  await page.getByLabel('Layout').selectOption('browser');
  await expect(page.locator('#app')).toHaveCSS('width', '756px');
  await expect(app.locator('html')).toHaveCSS('--safe-area-left', '0px');
  await page.getByLabel('Layout').selectOption('pwa');
  await page.getByLabel('Orientation').selectOption('portrait');
  await page.getByRole('button', { name: 'Reload app' }).click();
  await expect(app.getByRole('button', { name: 'Pick a problem' })).toBeVisible();
  await expect(app.locator('html')).toHaveCSS('--safe-area-bottom', '34px');
  await testInfo.attach('phone-preview', { body: await page.screenshot(), contentType: 'image/png' });
});
