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
  const avisos = [];api.onModeloServido(v => avisos.push(v));
  await api.get('/version');
  expect(api.modeloServido()).toBe('m1b-i1-seed1-best');
  await api.get('/version');
  expect(api.modeloServido()).toBe('m1b-i1-seed1-best');
  expect(avisos).toEqual(['m1b-i1-seed1-best']);
});

const memoryStorage = () => {const values=new Map();return {getItem:key=>values.get(key)||null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};};

test('X-Sesion: se conserva al recargar y se envía también en el diagnóstico, sin cookies', async()=>{
  const storage=memoryStorage(), calls=[];
  const fetchImpl=async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify({sesion_id:'partida-a'}),{headers:{'X-Sesion':'partida-a'}});};
  const a=createClient({baseUrl:'https://api.ejemplo.dev',storage,fetchImpl});
  await a.get('/api/state');expect(calls[0].init.headers['X-Sesion']).toBeUndefined();
  const b=createClient({baseUrl:'https://api.ejemplo.dev',storage,fetchImpl});
  await b.get('/api/layout');await b.post('/api/step');await b.post('/api/evaluate',{model:'m1'});
  for(const call of calls.slice(1)){expect(call.init.headers['X-Sesion']).toBe('partida-a');expect(call.init.credentials).toBe('omit');}
  const other=createClient({baseUrl:'https://otra-api.dev',storage,fetchImpl});
  await other.get('/api/state');expect(calls.at(-1).init.headers['X-Sesion']).toBeUndefined();
});

test('error plano del visor: borra solo una sesión perdida; no reintenta POST', async()=>{
  const storage=memoryStorage();let n=0;
  const fetchImpl=async()=>{n++;return new Response(JSON.stringify(n===1?{sesion_id:'a'}:{error:'La partida caducó',codigo:'sesion_no_encontrada'}),{status:n===1?200:404});};
  const api=createClient({baseUrl:'https://api.ejemplo.dev',storage,fetchImpl});await api.get('/api/state');
  const error=await api.post('/api/step').catch(e=>e);
  expect([error.status,error.codigo,error.message]).toEqual([404,'sesion_no_encontrada','La partida caducó']);
  expect(api.sessionId()).toBeNull();expect(n).toBe(2);
  expect(createClient({baseUrl:'https://api.ejemplo.dev',storage,fetchImpl}).sessionId()).toBeNull();
});

test('X-Sesion en el cuerpo funciona y un reset que crea otra partida avisa', async()=>{
  let n=0;const api=createClient({baseUrl:'https://api.ejemplo.dev',storage:memoryStorage(),fetchImpl:async()=>new Response(JSON.stringify({sesion_id:++n===1?'a':'b'}))});
  const changes=[];api.onSessionChange(change=>changes.push(change));
  await api.get('/api/state');await api.post('/api/reset',{seed:42});
  expect(changes.at(-1)).toMatchObject({previous:'a',current:'b',path:'/api/reset'});
});

test('servidor lento avisa y un timeout no repite la acción', async()=>{
  const events=[];let calls=0;
  const api=createClient({baseUrl:'https://api.ejemplo.dev',storage:null,slowAfterMs:1,timeoutMs:30,
    fetchImpl:async(_url,{signal})=>{calls++;return new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(new Error('aborted'))));}});
  api.onActivity(event=>events.push(event.phase));
  const error=await api.post('/api/step').catch(e=>e);
  expect(error.codigo).toBe('tiempo_agotado');expect(calls).toBe(1);expect(events).toContain('waking');expect(events.at(-1)).toBe('idle');
});

test('una ruta no puede enviar la sesión a otro origen y 204 es válido',async()=>{
  const api=createClient({baseUrl:'https://api.ejemplo.dev',fetchImpl:async()=>new Response(null,{status:204})});
  await expect(api.get('//otro.example/x')).rejects.toThrow(/ruta/);
  expect(await api.del('/episodios/a')).toBeNull();
});
