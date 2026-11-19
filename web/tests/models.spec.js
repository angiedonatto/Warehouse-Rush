import { test, expect } from '@playwright/test';
const shots = process.env.SHOT_DIR || 'test-results/capturas';
// Catálogo de modelos (R4): ficha, evaluación, comparación, carga, enlace directo y móvil.
test('catálogo de modelos: ficha, evaluar, cargar, comparar, enlace directo', async ({ page }) => {
  test.setTimeout(300000);
  const errors = [];page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page.locator('#scene-loading')).toBeHidden({ timeout: 60000 });
  await page.locator('#open-models').click();
  await expect(page.locator('.models-dialog')).toBeVisible();
  await page.locator('#models-state').selectOption('recomendado');
  await page.locator('.model-card', { hasText: 'm1b-i1-seed1-best' }).click();
  await expect(page.locator('#model-detail h3')).toHaveText('m1b-i1-seed1-best');
  await page.screenshot({ path: `${shots}/1-ficha.png` });
  await page.locator('#models-blocked').check();
  await page.getByRole('button', { name: /Diagnóstico rápido · 10 episodios \(no certificado\)/ }).click();
  await expect(page.locator('.model-eval-out .model-kpis')).toBeVisible({ timeout: 90000 });
  await expect(page.locator('.model-eval-out .mode-badge')).toHaveText('DIAGNÓSTICO · NO CERTIFICADO');
  await page.screenshot({ path: `${shots}/2-evaluacion.png` });
  // comparar dos modelos
  await page.locator('#models-state').selectOption('');
  for (const id of ['m1-c3-seed0', 'm1-c3-seed1']) await page.locator('.model-card', { hasText: new RegExp(`^.*${id}$|${id}`) }).first().locator('input[type=checkbox]').check();
  await page.locator('#models-compare').click();
  await expect(page.locator('#model-detail h3')).toHaveText('Comparación de candidatos');
  await page.screenshot({ path: `${shots}/3-comparar.png` });
  // cargar en la bodega
  await page.locator('#models-state').selectOption('recomendado');
  await page.locator('.model-card', { hasText: 'm1b-i1-seed1-best' }).click();
  await page.locator('#models-blocked').check();
  await page.getByRole('button', { name: 'Cargar en la bodega' }).click();
  await expect(page.locator('#mode-badge')).toContainText('m1b-i1-seed1-best', { timeout: 30000 });
  await page.locator('#speed').selectOption('4');await page.locator('#play').click();
  await expect(page.locator('#mission-banner')).toBeVisible({ timeout: 200000 });
  await page.screenshot({ path: `${shots}/4-episodio.png` });
  // enlace directo en otra pestaña (sin cookie compartida no importa: la URL manda)
  const url = page.url();
  const other = await page.context().browser().newPage();
  await other.goto(url);
  await expect(other.locator('#mode-badge')).toContainText('m1b-i1-seed1-best', { timeout: 60000 });
  await other.goto(url.replace(/\?.*/, '?catalogo=m1-c3-seed0'));
  await expect(other.locator('#model-detail h3')).toHaveText('m1-c3-seed0', { timeout: 60000 });
  await other.setViewportSize({ width: 390, height: 844 });
  expect(await other.evaluate(() => { const d = document.querySelector('.models-dialog'); return d.scrollWidth - d.clientWidth; })).toBe(0);
  await other.screenshot({ path: `${shots}/modelos-movil.png` });
  expect(errors).toEqual([]);
});
