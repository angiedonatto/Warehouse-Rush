import { test, expect } from '@playwright/test';

test('order checklist follows real pickup, delivery and stock; rack details and mobile', async ({ page, request }) => {
  await request.post('/api/reset', { data: { makeup: true, seed: 42, orders: 1, policy: 'heuristic', blocked: true } });
  const errors = [];page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page.locator('#scene-loading')).toBeHidden();
  await expect(page.locator('#order-sheet li')).toHaveCount(3);
  expect(await page.locator('#order-sheet input:checked').count()).toBe(0);
  await page.getByLabel('Seleccionar estantería').selectOption('E06');
  await expect(page.locator('#rack-detail')).toContainText('Toy Story');
  await expect(page.locator('#rack-detail')).toContainText('TRD-06-03');
  await page.locator('#speed').selectOption('4');
  await page.locator('#play').click();
  await expect(page.locator('#order-sheet li.picked').first()).toBeVisible({ timeout: 45000 });
  await expect(page.locator('.order-confirmation')).toHaveText('✓ Entrega confirmada', { timeout: 70000 });
  expect(await page.locator('#order-sheet input:checked').count()).toBe(3);
  const state = await page.evaluate(() => window.warehouseViewer.state);
  expect(state.info.success).toBe(true);
  expect(state.state.colisiones).toBe(0);
  for (const line of state.state.order.lines) {
    expect(line.delivered).toBe(line.quantity);
    const product = state.state.inventory.products.find(p => p.sku === line.sku);
    expect(product.stock_reserved).toBe(0);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('#order-sheet')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  await page.screenshot({ path: '/tmp/warehouse-makeup-mobile.png', fullPage: true });
});
