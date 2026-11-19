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

// El profe elige un run histórico (no recomendado), revisa su identidad, lo carga y corre una evaluación.
test('modelo histórico ejecutable: ficha, cargar, diagnóstico, recarga y enlace directo', async ({ page }) => {
  test.setTimeout(240000);
  const errors = [];page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page.locator('#scene-loading')).toBeHidden({ timeout: 60000 });
  await page.locator('#open-models').click();
  await page.locator('#models-search').fill('m1-c3-seed1');
  await page.locator('.model-card', { hasText: 'm1-c3-seed1' }).first().click();
  await expect(page.locator('#model-detail h3')).toHaveText('m1-c3-seed1');
  await expect(page.locator('#model-detail')).toContainText('candidato');
  await page.getByRole('button', { name: /Diagnóstico rápido/ }).click();
  await expect(page.locator('.model-eval-out .mode-badge')).toHaveText('DIAGNÓSTICO · NO CERTIFICADO', { timeout: 90000 });
  await page.getByRole('button', { name: 'Cargar en la bodega' }).click();
  await expect(page.locator('#mode-badge')).toContainText('m1-c3-seed1', { timeout: 60000 });
  await expect(page.locator('#policy')).toHaveValue('model:m1-c3-seed1');
  await page.locator('#step').click();
  await expect(page.locator('#steps')).toHaveText('1');
  // La URL ya es el enlace directo (?modelo=…&semilla=…): al recargar, el modelo sigue cargado y la misión
  // se vuelve a crear desde el enlace (mismo comportamiento que con los modelos recomendados).
  await expect(page).toHaveURL(/modelo=m1-c3-seed1/);
  await page.reload();
  await expect(page.locator('#scene-loading')).toBeHidden({ timeout: 60000 });
  await expect(page.locator('#policy')).toHaveValue('model:m1-c3-seed1');
  await expect(page.locator('#mode-badge')).toContainText('m1-c3-seed1');
  // Enlace directo con otra semilla (en la misma página: la otra ventana ya la cubre la prueba anterior y aquí solo
  // cargaba la CPU con una segunda escena WebGL por software).
  await page.goto('/?modelo=m1-c3-seed1&semilla=10001');
  await expect(page.locator('#scene-loading')).toBeHidden({ timeout: 60000 });
  await expect(page.locator('#mode-badge')).toContainText('m1-c3-seed1', { timeout: 60000 });
  await expect(page.locator('#order-seed')).toHaveValue('10001');
  expect(errors).toEqual([]);
});

// Evaluación oficial desde la web (contrato 6): reconstruye la evaluación registrada del modelo de producción.
test('evaluación oficial: progreso, resultado por episodio y coincide con la registrada; cola llena', async ({ page }) => {
  test.setTimeout(300000);
  const errors = [];page.on('pageerror', e => errors.push(e.message));
  await page.goto('/?catalogo=m1b-i1-seed1-best');
  await expect(page.locator('#model-detail h3')).toHaveText('m1b-i1-seed1-best', { timeout: 60000 });
  await expect(page.locator('#official-suite')).toHaveValue('suite-m1b-v1');
  await expect(page.locator('#official-policy')).toHaveValue('ppo');
  await page.locator('#official-run').click();
  await expect(page.locator('#official-run')).toBeDisabled();
  await expect(page.locator('.official-progress')).toBeVisible({ timeout: 60000 });
  await page.screenshot({ path: `${process.env.SHOT_DIR || 'test-results/capturas'}/evaluacion-oficial-progreso.png` });
  await expect(page.locator('#official-out .official-match')).toContainText('la evaluación se reproduce igual', { timeout: 240000 });
  await expect(page.locator('#official-out')).toContainText('Éxito 100%');
  await expect(page.locator('#official-out tbody tr')).toHaveCount(50);
  await expect(page.locator('#official-run')).toBeEnabled();
  await page.screenshot({ path: `${process.env.SHOT_DIR || 'test-results/capturas'}/evaluacion-oficial-resultado.png` });
  // Al volver a la ficha, el resultado sigue ahí.
  await page.locator('#models-search').fill('m1-c3-seed0');
  await page.locator('.model-card', { hasText: 'm1-c3-seed0' }).first().click();
  await page.locator('#models-search').fill('m1b-i1-seed1-best');
  await page.locator('.model-card', { hasText: 'm1b-i1-seed1-best' }).first().click();
  await expect(page.locator('#official-out')).toContainText('Éxito 100%');
  // 429 cola_llena (simulado): mensaje claro y el botón vuelve a quedar disponible.
  await page.route('**/evaluaciones', route => route.request().method() === 'POST'
    ? route.fulfill({ status: 429, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify({ error: { codigo: 'cola_llena', mensaje: 'Ya hay 3 evaluaciones esperando', detalle: {} } }) })
    : route.continue());
  await page.locator('#official-policy').selectOption('heuristic');
  await page.locator('#official-run').click();
  await expect(page.locator('#official-out .model-error')).toContainText('La cola de evaluaciones está llena');
  await expect(page.locator('#official-run')).toBeEnabled();
  expect(errors).toEqual([]);
});
