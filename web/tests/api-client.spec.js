import { test, expect } from '@playwright/test';
import { ApiError, createClient, resolveBaseUrl } from '../src/api-client.js';
// Cliente de la API (sin navegador): base URL, sin credenciales, formato de error y cabecera del modelo servido.

const fakeFetch = (status, body, headers = {}) => {
  const calls = [];
  const impl = async (url, init) => { calls.push({ url, init }); return new Response(body === undefined ? '' : JSON.stringify(body), { status, headers }); };
  return { impl, calls };
};

test('base URL: obligatoria, sin barra final; en producción HTTPS y nunca localhost', () => {
  expect(() => resolveBaseUrl('')).toThrow(/VITE_API_BASE_URL/);
  expect(() => resolveBaseUrl(undefined)).toThrow(/VITE_API_BASE_URL/);
  expect(() => resolveBaseUrl('https://api.ejemplo.dev/')).toThrow(/barra final/);
  expect(() => resolveBaseUrl('no es url')).toThrow(/no es una URL/);
  expect(resolveBaseUrl('http://127.0.0.1:7860')).toBe('http://127.0.0.1:7860');
  for (const local of ['https://localhost:7860', 'https://127.0.0.1', 'https://0.0.0.0:8000']) expect(() => resolveBaseUrl(local, { prod: true })).toThrow(/localhost/);
  expect(() => resolveBaseUrl('http://api.ejemplo.dev', { prod: true })).toThrow(/HTTPS/);
  expect(resolveBaseUrl('https://api.ejemplo.dev', { prod: true })).toBe('https://api.ejemplo.dev');
});

test('peticiones: URL absoluta, query sin vacíos, JSON y credentials omit', async () => {
  const { impl, calls } = fakeFetch(200, { ok: true });
  const api = createClient({ baseUrl: 'https://api.ejemplo.dev', fetchImpl: impl });
  expect(await api.get('/catalogo', { nivel: 'm1b', estado: '' })).toEqual({ ok: true });
  await api.post('/x', { a: 1 });
  await api.del('/x/1');
  expect(calls.map(c => [c.init.method, c.url])).toEqual([
    ['GET', 'https://api.ejemplo.dev/catalogo?nivel=m1b'],
    ['POST', 'https://api.ejemplo.dev/x'],
    ['DELETE', 'https://api.ejemplo.dev/x/1'],
  ]);
  for (const c of calls) expect(c.init.credentials).toBe('omit');
  expect(calls[1].init.body).toBe('{"a":1}');
  expect(calls[1].init.headers['Content-Type']).toBe('application/json');
  expect(calls[0].init.body).toBeUndefined();
});

test('errores: {"error": {codigo, mensaje, detalle}} → ApiError con status y codigo', async () => {
  const error = { codigo: 'episodio_no_encontrado', mensaje: 'El episodio no existe o caducó', detalle: { id: 'abc' } };
  const api = createClient({ baseUrl: 'https://api.ejemplo.dev', fetchImpl: fakeFetch(404, { error }).impl });
  const thrown = await api.get('/episodios/abc').catch(e => e);
  expect(thrown).toBeInstanceOf(ApiError);
  expect([thrown.status, thrown.codigo, thrown.message]).toEqual([404, 'episodio_no_encontrado', 'El episodio no existe o caducó']);
  expect(thrown.detalle).toEqual({ id: 'abc' });

  const busy = await createClient({ baseUrl: 'https://api.ejemplo.dev', fetchImpl: fakeFetch(429, { error: { codigo: 'x', mensaje: 'y' } }).impl }).post('/evaluaciones').catch(e => e);
  expect(busy.status).toBe(429);

  // Cuerpo que no es JSON o sin el formato acordado: mensaje genérico con el status.
  const raw = await createClient({ baseUrl: 'https://api.ejemplo.dev', fetchImpl: async () => new Response('Bad gateway', { status: 502 }) }).get('/version').catch(e => e);
  expect([raw.status, raw.codigo, raw.message]).toEqual([502, null, 'HTTP 502']);

  const offline = await createClient({ baseUrl: 'https://api.ejemplo.dev', fetchImpl: async () => { throw new TypeError('Failed to fetch'); } }).get('/version').catch(e => e);
  expect([offline.status, offline.codigo]).toEqual([0, 'sin_conexion']);
});

test('cabecera X-Modelo-Servido: se guarda la última recibida', async () => {
  let n = 0;
  const api = createClient({ baseUrl: 'https://api.ejemplo.dev', fetchImpl: async () => new Response('{}', { status: 200, headers: ++n === 1 ? { 'X-Modelo-Servido': 'm1b-i1-seed1-best' } : {} }) });
  expect(api.modeloServido()).toBeNull();
  await api.get('/version');
  expect(api.modeloServido()).toBe('m1b-i1-seed1-best');
  await api.get('/version');
  expect(api.modeloServido()).toBe('m1b-i1-seed1-best');
});
