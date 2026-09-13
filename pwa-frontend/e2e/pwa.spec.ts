import { test, expect } from '@playwright/test';

test('the production PWA has valid install assets and reloads its shell offline', async ({ page, context, request }) => {
  const response = await request.get('/manifest.webmanifest');
  expect(response.ok()).toBe(true);
  const manifest = await response.json();
  expect(manifest).toMatchObject({ display: 'standalone', start_url: '/', scope: '/', id: '/' });
  for (const icon of manifest.icons) {
    const asset = await request.get(icon.src);
    expect(asset.ok()).toBe(true);
    expect(asset.headers()['content-type']).toContain('image/png');
    // Read the PNG IHDR instead of accepting an HTML fallback with a 200 status.
    const png = await asset.body();
    expect(`${png.readUInt32BE(16)}x${png.readUInt32BE(20)}`).toBe(icon.sizes);
  }
  const appleIcon = await request.get('/apple-touch-icon.png');
  expect((await appleIcon.body()).readUInt32BE(16)).toBe(180);
  await page.goto('/');
  await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute('href', '/apple-touch-icon.png');
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  await context.setOffline(true);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'CF Picker' })).toBeVisible();
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Settings' })).toBeVisible();
  // Offline navigation to an API must not return index.html from Workbox.
  const apiPage = await context.newPage();
  const apiNavigation = await apiPage.goto('/api/participations').catch(() => null);
  expect(apiNavigation?.ok() ?? false).toBe(false);
});
