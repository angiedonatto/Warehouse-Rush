import { test, expect } from '@playwright/test';
import { API, CLAVE_SESION, viewerSession } from './api-session.js';
// Avisos de la web frente a la API de Render (docs/api-contrato.md 8, 9.6 y 9.7): servidor despertando, sesión
// perdida y 429. Las respuestas anómalas se simulan con page.route; el resto va a la API real.

const json = (status, body) => ({ status, contentType: 'application/json', body: JSON.stringify(body),
  headers: { 'access-control-allow-origin': '*', 'access-control-expose-headers': 'X-Sesion' } });
const perdida = { error: 'La sesión no existe o caducó', codigo: 'sesion_no_encontrada' };
// Simula solo la primera respuesta y deja pasar las demás a la API. No se usa { times: 1 }: al quitarse la ruta se
// apaga la intercepción mientras el navegador hace la consulta previa CORS de la petición siguiente, que queda colgada.
const unaVez = respuesta => { let usada = false; return route => usada ? route.continue() : (usada = true, route.fulfill(respuesta)); };

async function open(page) {
  await page.goto('/');
  await expect(page.locator('#scene-loading')).toBeHidden({ timeout: 45000 });
}
const guardada = page => page.evaluate(clave => sessionStorage.getItem(clave), CLAVE_SESION);

test('una petición lenta muestra «Despertando el servidor…» y lo quita al responder', async ({ page }) => {
  let demorada = false;
  await page.route(`${API}/api/layout`, async route => {
    if (!demorada) { demorada = true; await new Promise(resolve => setTimeout(resolve, 3800)); }
    await route.continue();
  });
  await page.goto('/');
  await expect(page.locator('#server-wait')).toBeVisible({ timeout: 6000 });
  await expect(page.locator('#server-wait')).toContainText('Despertando el servidor');
  await expect(page.locator('#scene-loading')).toBeHidden({ timeout: 45000 });
  await expect(page.locator('#server-wait')).toBeHidden();
});

test('sin cookies: la sesión viaja en X-Sesion y se guarda en sessionStorage', async ({ page }) => {
  const enviadas = [];
  page.on('request', r => { if (r.url().startsWith(`${API}/api/`)) enviadas.push({ url: r.url(), sesion: r.headers()['x-sesion'], cookie: r.headers().cookie }); });
  await open(page);
  const id = await guardada(page);
  expect(id).toBeTruthy();
  await page.locator('#step').click();
  await expect(page.locator('#steps')).toHaveText('1');
  const paso = enviadas.find(r => r.url.endsWith('/api/step'));
  expect(paso.sesion).toBe(id);
  expect(enviadas.every(r => !r.cookie)).toBe(true);
});

test('sesión perdida en un paso: avisa y reinicia la misión con una sesión nueva', async ({ page }) => {
  await open(page);
  await page.locator('#step').click();
  await expect(page.locator('#steps')).toHaveText('1');
  const vieja = await guardada(page);
  await page.route(`${API}/api/step`, unaVez(json(404, perdida)));
  const reset = page.waitForRequest(r => r.url() === `${API}/api/reset`);
  await page.locator('#step').click();
  await expect(page.locator('#toast')).toContainText('La sesión se perdió');
  const peticion = await reset;
  expect(peticion.headers()['x-sesion']).toBeUndefined();
  await expect(page.locator('#steps')).toHaveText('0');
  await expect.poll(() => guardada(page)).not.toBe(vieja);
  await page.locator('#step').click();
  await expect(page.locator('#steps')).toHaveText('1');
});

test('al abrir con una sesión guardada que caducó: avisa y empieza una nueva', async ({ page, request }) => {
  await page.addInitScript(clave => sessionStorage.setItem(clave, 'sesion-caducada-de-prueba'), CLAVE_SESION);
  await open(page);
  await expect(page.locator('#toast')).toContainText('La sesión se perdió');
  const nueva = await guardada(page);
  expect(nueva).not.toBe('sesion-caducada-de-prueba');
  expect((await request.get(`${API}/api/state`, { headers: { 'X-Sesion': nueva } })).ok()).toBe(true);
});

test('429: demasiadas sesiones al reiniciar y diagnóstico en curso, con mensajes entendibles', async ({ page, request }) => {
  const api = viewerSession(request);
  await api.post('reset', { orders: 2, blocked: true, policy: 'heuristic', seed: 10000 });
  await api.attach(page);
  await open(page);
  await page.route(`${API}/api/reset`, unaVez(json(429, { error: 'Hay 100 sesiones en curso', codigo: 'demasiadas_sesiones' })));
  await page.locator('#reset').click();
  await expect(page.locator('#toast')).toContainText('máximo de partidas abiertas');

  await page.route(`${API}/api/evaluate`, route => route.fulfill(json(429, { error: 'Ya hay un diagnóstico en curso', codigo: 'diagnostico_en_curso' })));
  await page.locator('#open-models').click();
  await page.locator('#models-state').selectOption('recomendado');
  await page.locator('.model-card', { hasText: 'm1b-i1-seed1-best' }).click();
  const boton = page.getByRole('button', { name: /Diagnóstico rápido/ });
  await boton.click();
  await expect(page.locator('.model-eval-out .model-error')).toContainText('Ya hay un diagnóstico corriendo');
  await expect(boton).toBeEnabled();
});
