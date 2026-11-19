import { test, expect } from '@playwright/test';
const shots = process.env.SHOT_DIR || 'test-results/capturas';
// Modelo servido (GET /version + X-Modelo-Servido) y monitoreo (GET /monitoreo) contra la API de VITE_API_BASE_URL.
test('modelo servido y monitoreo de la API', async ({ page }) => {
  const errors = [];page.on('pageerror', e => errors.push(e.message));
  const version = page.waitForResponse(r => new URL(r.url()).pathname === '/version');
  await page.goto('/');
  const v = await (await version).json();
  const served = page.locator('#served-model');
  await expect(served).toContainText(`MODELO SERVIDO · ${v.run_id} · sha256 ${v.model_sha256.slice(0, 12)} · ${v.environment_version}`);

  await page.locator('#open-monitor').click();
  const dialog = page.locator('.monitor-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('.model-kpis')).toContainText(`Servido: ${v.run_id}`);
  for (const title of ['Éxito y causas de fin por escenario', 'Latencia de decisión por paso', 'Peticiones y errores por ruta']) await expect(dialog.getByRole('heading', { name: title })).toBeVisible();
  await expect(dialog.locator('td', { hasText: 'GET /version' })).toBeVisible();
  await page.screenshot({ path: `${shots}/monitoreo.png` });
  await dialog.getByRole('button', { name: 'Actualizar' }).click();
  await expect(dialog.locator('td', { hasText: 'GET /monitoreo' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Cerrar monitoreo' }).click();
  await expect(dialog).toBeHidden();

  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  await page.locator('#open-monitor').click();
  expect(await dialog.evaluate(d => d.scrollWidth - d.clientWidth)).toBe(0);
  await page.screenshot({ path: `${shots}/monitoreo-movil.png` });
  expect(errors).toEqual([]);
});
