import { test, expect } from '@playwright/test';

test('order checklist follows real pickup, delivery and stock; rack details and mobile', async ({ page, request }) => {
  const response = await request.post('/api/reset', { data: { makeup: true, seed: 42, orders: 1, policy: 'heuristic', blocked: true } });
  expect(response.ok()).toBeTruthy();
  const initial = await response.json();
  const initialUnits = initial.state.inventory.products.reduce((n, p) => n + p.stock_total, 0);
  const errors = [];page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page.locator('#scene-loading')).toBeHidden();
  await expect(page.locator('#order-sheet li')).toHaveCount(3);
  expect(await page.locator('#order-sheet input:checked').count()).toBe(0);
  await page.getByLabel('Seleccionar estantería').selectOption('E06');
  await expect(page.locator('#rack-detail')).toContainText('Toy Story');
  await expect(page.locator('#rack-detail')).toContainText('TMP-E06-L3');
  const visuals = await page.evaluate(() => {
    const scene = window.warehouseViewer.scene;
    return { background: scene.scene.background.getHexString(), body: getComputedStyle(document.documentElement).backgroundColor,
      legacy: scene.legacyStations.visible, genericCargo: scene.cargo.visible,
      units: [...scene.stockVisuals.products.values()].reduce((n, p) => n + p.shelf.count, 0) };
  });
  expect(visuals).toEqual({background: 'f8e7ef', body: 'rgb(255, 245, 249)', legacy: false, genericCargo: false, units: initialUnits});
  await page.locator('#speed').selectOption('4');
  await page.locator('#play').click();
  await expect(page.locator('#order-sheet li.picked').first()).toBeVisible({ timeout: 45000 });
  await page.locator('#play').click();
  const carrying = await page.evaluate(() => {
    const {scene, state} = window.warehouseViewer;
    return { lines: state.state.cargo_lines, picked: state.state.order.lines.reduce((n, l) => n + l.picked, 0),
      stockUnits: [...scene.stockVisuals.products.values()].reduce((n, p) => n + p.shelf.count, 0),
      cargoUnits: [...scene.stockVisuals.products.values()].reduce((n, p) => n + p.cargo.count, 0),
      genericCargo: scene.cargo.visible };
  });
  expect(carrying.cargoUnits).toBeGreaterThan(0);
  expect(carrying.cargoUnits).toBe(carrying.lines.reduce((n, l) => n + l.quantity, 0));
  expect(carrying.stockUnits).toBe(initialUnits - carrying.picked);
  expect(carrying.genericCargo).toBe(false);
  await page.screenshot({path: '/tmp/warehouse-picking.png'});
  await page.locator('#play').click();
  await expect(page.locator('.order-confirmation')).toHaveText('✓ Entrega confirmada', { timeout: 70000 });
  expect(await page.locator('#order-sheet input:checked').count()).toBe(3);
  const state = await page.evaluate(() => window.warehouseViewer.state);
  expect(state.info.success).toBe(true);
  await expect(page.locator('#target')).toHaveText('Entrega confirmada');
  expect(state.state.colisiones).toBe(0);
  for (const line of state.state.order.lines) {
    expect(line.delivered).toBe(line.quantity);
    const product = state.state.inventory.products.find(p => p.sku === line.sku);
    expect(product.stock_reserved).toBe(0);
    const mesh = await page.evaluate(sku => {
      const p = window.warehouseViewer.scene.stockVisuals.products.get(sku);
      return {stock: p.shelf.count, cargo: p.cargo.count, delivered: p.delivered.count};
    }, line.sku);
    expect(mesh).toEqual({stock: product.stock_total, cargo: 0, delivered: line.quantity});
  }
  const events = state.state.order.events;
  expect(Math.max(...events.filter(e => e.kind.startsWith('PICK:')).map(e => e.time))).toBeLessThan(Math.min(...events.filter(e => e.kind.startsWith('DELIVER:')).map(e => e.time)));
  await page.screenshot({path: '/tmp/warehouse-shelves-desktop.png', fullPage: true});
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('#order-sheet')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  await page.screenshot({ path: '/tmp/warehouse-makeup-mobile.png', fullPage: true });
});
