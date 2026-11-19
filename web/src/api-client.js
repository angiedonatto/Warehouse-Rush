// Cliente único de Render: visor y catálogo usan la misma base y sesión, sin cookies.
export class ApiError extends Error {
  constructor(status, { codigo = null, mensaje = null, detalle = null } = {}) {
    super(mensaje || `HTTP ${status}`);
    this.name = 'ApiError';this.status = status;this.codigo = codigo;this.detalle = detalle;
  }
}
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0', '[::1]']);
export function resolveBaseUrl(raw, { prod = false } = {}) {
  const base = String(raw ?? '').trim();
  if (!base) throw new Error('Falta VITE_API_BASE_URL (URL base de la API, sin barra final).');
  if (base.endsWith('/')) throw new Error(`VITE_API_BASE_URL va sin barra final ("/"): ${base}`);
  let url;
  try { url = new URL(base); } catch { throw new Error(`VITE_API_BASE_URL no es una URL válida: ${base}`); }
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('VITE_API_BASE_URL debe ser el origen HTTP(S), sin credenciales, ruta ni parámetros.');
  }
  if (prod) {
    if (url.protocol !== 'https:') throw new Error(`En producción VITE_API_BASE_URL debe ser HTTPS: ${base}`);
    if (LOCAL_HOSTS.has(url.hostname)) throw new Error(`En producción VITE_API_BASE_URL no puede ser localhost: ${base}`);
  }
  return base;
}
export const sessionKeyFor = base => `warehouse-sesion:${base}`;
function browserStorage() { try { return globalThis.sessionStorage; } catch { return null; } }

export function createClient({ baseUrl, prod = false, fetchImpl = globalThis.fetch,
  storage = browserStorage(), slowAfterMs = 2500, timeoutMs = 90000 } = {}) {
  const base = resolveBaseUrl(baseUrl, { prod }), key = sessionKeyFor(base);
  let sessionId = null, modeloServido = null, seenResponse = false;
  try { sessionId = storage?.getItem(key) || null; } catch { /* Sesión en memoria si el almacenamiento está bloqueado. */ }
  const modelListeners = new Set(), sessionListeners = new Set(), activityListeners = new Set(), pending = new Set();
  function remember(value, path) {
    if (value === sessionId) return;
    const previous = sessionId;sessionId = value;
    try { value ? storage?.setItem(key, value) : storage?.removeItem(key); } catch { /* Mantener la pestaña operativa. */ }
    for (const fn of sessionListeners) fn({ previous, current: value, path });
  }
  function activity() {
    const slow = [...pending].find(r => r.slow);
    const event = { phase: slow ? (seenResponse ? 'waiting' : 'waking') : pending.size ? 'loading' : 'idle', path: slow?.path };
    for (const fn of activityListeners) fn(event);
  }
  async function request(path, { method = 'GET', body, query } = {}) {
    if (!/^\/(?!\/)/.test(path)) throw new Error('La ruta de API debe comenzar con una sola barra.');
    const qs = query ? new URLSearchParams(Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')).toString() : '';
    const init = { method, credentials: 'omit', headers: { Accept: 'application/json' } };
    if (sessionId) init.headers['X-Sesion'] = sessionId;
    if (body !== undefined) { init.headers['Content-Type'] = 'application/json';init.body = JSON.stringify(body); }
    const controller = new AbortController();init.signal = controller.signal;
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const entry = { path, slow: false };pending.add(entry);activity();
    const slowTimer = setTimeout(() => { entry.slow = true;activity(); }, slowAfterMs);
    try {
      let response;
      try { response = await fetchImpl(`${base}${path}${qs ? `?${qs}` : ''}`, init); }
      catch (cause) {
        throw new ApiError(0, { codigo: controller.signal.aborted ? 'tiempo_agotado' : 'sin_conexion',
          mensaje: controller.signal.aborted ? 'El servidor tardó demasiado en responder. Revisa el estado antes de reintentar.' : 'No se pudo conectar con la API. Puede estar despertando; espera y vuelve a intentar.',
          detalle: String(cause?.message || cause) });
      }
      seenResponse = true;
      const served = response.headers.get('X-Modelo-Servido');
      if (served && served !== modeloServido) { modeloServido = served;for (const fn of modelListeners) fn(served); }
      const text = await response.text();let data = null;
      if (text) { try { data = JSON.parse(text); } catch { /* Error HTTP o respuesta inválida. */ } }
      if (!response.ok) {
        const error = data?.error && typeof data.error === 'object' ? data.error : { codigo: data?.codigo, mensaje: data?.error };
        if (error.codigo === 'sesion_no_encontrada') remember(null, path);
        throw new ApiError(response.status, error);
      }
      if (response.status === 204) return null;
      if (data === null) throw new ApiError(response.status, { codigo: 'respuesta_invalida', mensaje: 'La API no devolvió una respuesta JSON válida.' });
      const next = response.headers.get('X-Sesion') || data.sesion_id;
      if (next) remember(next, path);
      return data;
    } finally { clearTimeout(timer);clearTimeout(slowTimer);pending.delete(entry);activity(); }
  }
  return {
    base, request, get: (path, query) => request(path, { query }), post: (path, body = {}) => request(path, { method: 'POST', body }),
    del: path => request(path, { method: 'DELETE' }), sessionId: () => sessionId, modeloServido: () => modeloServido,
    onModeloServido: fn => { modelListeners.add(fn);return () => modelListeners.delete(fn); },
    onSessionChange: fn => { sessionListeners.add(fn);return () => sessionListeners.delete(fn); },
    onActivity: fn => { activityListeners.add(fn);return () => activityListeners.delete(fn); },
  };
}
let shared = null;
export function apiClient() {
  shared ??= createClient({ baseUrl: import.meta.env.VITE_API_BASE_URL, prod: import.meta.env.MODE === 'production' });
  return shared;
}
