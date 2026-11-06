import { test, expect } from '@playwright/test';

test.beforeEach(async ({ context }) => {
  const response = await context.request.post('/api/reset', { data: { orders: 2, blocked: true, policy: 'heuristic', seed: 10000 } });
  expect(response.ok()).toBeTruthy();
});

async function open(page) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.locator('#scene-loading')).toBeHidden({ timeout: 45000 });
  await expect(page.locator('#connection-label')).toHaveText('Simulador conectado');
  return errors;
}

test('real WebGL scene, six racks, same layout and no horizontal overflow', async ({ page }) => {
  const errors = await open(page);
  expect(await page.evaluate(() => window.warehouseViewer.scene.renderer.getContext().isContextLost())).toBe(false);
  expect(await page.evaluate(() => window.warehouseViewer.scene.layout.racks.length)).toBe(6);
  await expect(page.locator('#position')).toContainText('(2, 11)');
  await expect(page.locator('#deliveries')).toHaveText('0 / 2');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  await page.screenshot({ path: '../docs/resultados/viewer-v0.2.png', fullPage: true });
});

test('step, play, pause and reset change the real Python episode', async ({ page, request }) => {
  await open(page);
  await page.locator('#step').click();
  await expect(page.locator('#steps')).toHaveText('1');
  expect((await (await page.request.get('/api/state')).json()).state.tiempo).toBe(1);
  await page.locator('#play').click();
  await expect(page.locator('#play span')).toHaveText('Pausar');
  await expect.poll(async () => Number(await page.locator('#steps').textContent())).toBeGreaterThan(1);
  await page.locator('#play').click();
  await expect(page.locator('#play span')).toHaveText('Iniciar');
  await page.locator('#reset').click();
  await expect(page.locator('#steps')).toHaveText('0');
  await expect(page.locator('#position')).toContainText('(2, 11)');
});

test('all four cameras, route, sensors and block switch work', async ({ page, request }) => {
  await open(page);
  for (const camera of ['fpv', 'side', 'station', 'iso']) {
    await page.locator(`[data-camera="${camera}"]`).click();
    await expect(page.locator(`[data-camera="${camera}"]`)).toHaveAttribute('aria-pressed', 'true');
    expect(await page.evaluate(() => window.warehouseViewer.scene.view)).toBe(camera);
  }
  await page.locator('#toggle-sensors').click();
  expect(await page.evaluate(() => window.warehouseViewer.scene.showSensors)).toBe(true);
  await page.locator('#toggle-route').click();
  expect(await page.evaluate(() => window.warehouseViewer.scene.showRoute)).toBe(false);
  await page.locator('#blocked').uncheck();
  await expect.poll(async () => (await (await page.request.get('/api/state')).json()).state.pasillo_bloqueado).toBe(false);
});

test('manual actions and completed deliveries stay synchronized', async ({ page, request }) => {
  test.setTimeout(180000); // 91 transiciones HTTP reales y renderizado de ambas cargas.
  await open(page);
  await page.locator('#policy').selectOption('manual');
  await expect(page.locator('#manual-controls')).toBeVisible();
  await page.locator('[data-action="0"]').click();
  await expect(page.locator('#collisions')).toHaveText('1');
  await page.locator('#policy').selectOption('heuristic');
  await expect(page.locator('#manual-controls')).toBeHidden();
  let state;
  for (let i = 0; i < 110; i++) {
    const response = await page.request.post('/api/step', { data: {} });
    expect(response.ok()).toBeTruthy();state = await response.json();
    if (state.done) break;
  }
  expect(state.info.success).toBe(true);
  await page.reload();
  await expect(page.locator('#scene-loading')).toBeHidden({ timeout: 45000 });
  await expect(page.locator('#deliveries')).toHaveText('2 / 2');
  await expect(page.locator('#mission-banner')).toContainText('Misión completada');
  await expect(page.locator('#play')).toBeDisabled();
});

test('mobile layout remains usable without horizontal scrolling', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.locator('#play')).toBeVisible();
  await page.locator('#step').click();
  await expect(page.locator('#steps')).toHaveText('1');
  // El canvas WebGL usa el viewport: capturar el área visible real, no una
  // página completa con vistas que todavía no han entrado en pantalla.
  await page.screenshot({ path: '../docs/resultados/viewer-mobile-v0.2.png' });
});

test('PPO and random selections execute their actual Python policies', async ({ page, request }) => {
  const metadata = await (await request.get('/api/layout')).json();
  test.skip(!metadata.available_ppo['1'], 'Requiere el modelo PPO de un pedido entrenado localmente');
  await open(page);
  await page.locator('#orders').selectOption('1');
  await expect(page.locator('#policy option[value="ppo"]')).toBeEnabled();
  await page.locator('#policy').selectOption('ppo');
  await expect(page.locator('#footer-detail')).toContainText('PPO real', { timeout: 60000 });
  await page.locator('#step').click();
  await expect(page.locator('#steps')).toHaveText('1');
  let payload = await (await page.request.get('/api/state')).json();
  expect(payload.policy).toBe('ppo');
  expect(payload.last_action.code).toBeGreaterThanOrEqual(0);
  expect(payload.last_action.code).toBeLessThan(5);
  await page.locator('#policy').selectOption('random');
  await expect(page.locator('#footer-detail')).toContainText('aleatorio');
  await page.locator('#step').click();
  await expect(page.locator('#steps')).toHaveText('1');
  payload = await (await page.request.get('/api/state')).json();
  expect(payload.policy).toBe('random');
});

test('published API isolates visitors and restores a session after reload', async ({ page, browser }) => {
  const health = await page.request.get('/api/health');
  test.skip(!health.ok(), 'El visor local compartido no usa el adaptador stateless');
  await open(page);
  await page.locator('#step').click();
  await expect(page.locator('#steps')).toHaveText('1');
  const other = await browser.newContext();
  try {
    const fresh = await (await other.request.get(`${new URL(page.url()).origin}/api/state`)).json();
    expect(fresh.state.tiempo).toBe(0);
    await page.reload();
    await expect(page.locator('#scene-loading')).toBeHidden({ timeout: 45000 });
    await expect(page.locator('#steps')).toHaveText('1');
  } finally { await other.close(); }
});
