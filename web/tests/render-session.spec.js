import { test, expect, API_BASE } from './visor-fixture.js';
import { sessionKeyFor } from '../src/api-client.js';
const key=sessionKeyFor(API_BASE);
async function ready(page){await page.goto('/');await expect(page.locator('#scene-loading')).toBeHidden();}

test('Render: todas las llamadas usan su origen y X-Sesion, sin cookies; recargar conserva partida',async({page,context})=>{
  await context.addCookies([{name:'no-enviar',value:'prueba',url:API_BASE}]);
  const calls=[];
  page.on('request',request=>{if(request.url().startsWith(API_BASE))calls.push({url:request.url(),headers:request.headers()});});
  await ready(page);
  const id=await page.evaluate(()=>window.warehouseViewer.state.sesion_id);expect(id).toBeTruthy();
  expect(await page.evaluate(k=>sessionStorage.getItem(k),key)).toBe(id);
  await page.locator('#step').click();await expect(page.locator('#steps')).toHaveText('1');
  await page.reload();await expect(page.locator('#scene-loading')).toBeHidden();
  await expect(page.locator('#steps')).toHaveText('1');
  expect(await page.evaluate(()=>window.warehouseViewer.state.sesion_id)).toBe(id);
  const sessionCalls=calls.filter(r=>/\/api\/(layout|step)/.test(r.url));
  expect(sessionCalls.length).toBeGreaterThan(1);
  for(const call of sessionCalls){expect(call.headers['x-sesion']).toBe(id);expect(call.headers.cookie).toBeUndefined();}
});

test('sesión perdida al recargar: se reinicia con modelo y semilla conservados y se avisa del stock',async({page})=>{
  await ready(page);
  await page.locator('#policy').selectOption('model:m1b-i1-seed1-best');
  await expect(page.locator('#mode-badge')).toContainText('m1b-i1-seed1-best');
  await page.locator('#order-seed').fill('123');await page.locator('#reset').click();
  await expect.poll(()=>page.evaluate(()=>window.warehouseViewer.state.seed)).toBe(123);
  await page.evaluate(k=>sessionStorage.setItem(k,'sesion-no-existe'),key);
  await page.reload();await expect(page.locator('#scene-loading')).toBeHidden();
  await expect(page.locator('#session-notice')).toContainText('stock inicial');
  const state=await page.evaluate(()=>window.warehouseViewer.state);
  expect(state.seed).toBe(123);expect(state.model.id).toBe('m1b-i1-seed1-best');expect(state.state.tiempo).toBe(0);
  expect(state.sesion_id).not.toBe('sesion-no-existe');
});

test('sesión perdida en step: libera busy, reinicia una sola vez y no repite ni reproduce pasos',async({page})=>{
  await ready(page);
  const initial=await page.evaluate(()=>window.warehouseViewer.state.sesion_id);let steps=0,resets=0;
  page.on('request',r=>{if(r.url().endsWith('/api/reset'))resets++;});
  await page.route('**/api/step',async route=>{
    steps++;
    await route.fulfill({status:404,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://127.0.0.1:8086'},body:JSON.stringify({error:'La partida caducó',codigo:'sesion_no_encontrada'})});
  });
  await page.locator('#play').click();
  await expect(page.locator('#session-notice')).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>window.warehouseViewer.state.sesion_id)).not.toBe(initial);
  await expect(page.locator('#steps')).toHaveText('0');
  await expect(page.locator('#play span')).toHaveText('Iniciar');
  expect(steps).toBe(1);expect(resets).toBe(1);
  expect(await page.evaluate(()=>window.warehouseViewer.running)).toBe(false);
});

test('servidor dormido: aviso mientras espera y recuperación normal de carga',async({page})=>{
  for(const path of ['version','api/state'])await page.route(`**/${path}`,async route=>{
    await new Promise(resolve=>setTimeout(resolve,3500));await route.continue();
  });
  await page.goto('/');
  await expect(page.locator('#network-notice')).toContainText('Despertando el servidor');
  await expect(page.locator('#scene-loading')).toBeHidden();
  await expect(page.locator('#network-notice')).toBeHidden();
});
