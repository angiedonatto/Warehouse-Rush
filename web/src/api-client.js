// Cliente HTTP de la API de simulación (FastAPI en otro dominio, HTTPS).
// - Base: VITE_API_BASE_URL, sin barra final. Sin cookies ni credenciales (credentials: 'omit').
// - Errores: la API responde {"error": {"codigo", "mensaje", "detalle"}}; se lanzan como ApiError
//   con status HTTP y codigo para que la interfaz decida (p. ej. 429 o 404 episodio_no_encontrado).
// - Producción: falla si la base falta, no es HTTPS o apunta a localhost.

export class ApiError extends Error {
  constructor(status, { codigo = null, mensaje = null, detalle = null } = {}) {
    super(mensaje || `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.codigo = codigo;
    this.detalle = detalle;
  }
}

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0', '[::1]']);

export function resolveBaseUrl(raw, { prod = false } = {}) {
  const base = String(raw ?? '').trim();
  if (!base) throw new Error('Falta VITE_API_BASE_URL (URL base de la API, sin barra final).');
  if (base.endsWith('/')) throw new Error(`VITE_API_BASE_URL va sin barra final ("/"): ${base}`);
  let url;
  try { url = new URL(base); } catch { throw new Error(`VITE_API_BASE_URL no es una URL válida: ${base}`); }
  if (prod) {
    if (url.protocol !== 'https:') throw new Error(`En producción VITE_API_BASE_URL debe ser HTTPS: ${base}`);
    if (LOCAL_HOSTS.has(url.hostname)) throw new Error(`En producción VITE_API_BASE_URL no puede ser localhost: ${base}`);
  }
  return base;
}

export function createClient({ baseUrl, prod = false, fetchImpl = globalThis.fetch } = {}) {
  const base = resolveBaseUrl(baseUrl, { prod });
  let modeloServido = null;
  const oyentes = new Set();

  async function request(path, { method = 'GET', body, query } = {}) {
    const qs = query ? new URLSearchParams(Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')).toString() : '';
    const url = `${base}${path.startsWith('/') ? path : `/${path}`}${qs ? `?${qs}` : ''}`;
    const init = { method, credentials: 'omit', headers: { Accept: 'application/json' } };
    if (body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(body); }
    let response;
    try { response = await fetchImpl(url, init); }
    catch (cause) { throw new ApiError(0, { codigo: 'sin_conexion', mensaje: 'No se pudo conectar con la API.', detalle: String(cause?.message || cause) }); }
    // Solo legible entre dominios si la API la expone (Access-Control-Expose-Headers).
    const header = response.headers.get('X-Modelo-Servido');
    if (header && header !== modeloServido) { modeloServido = header; for (const fn of oyentes) fn(header); }
    const text = await response.text();
    let data = null;
    if (text) { try { data = JSON.parse(text); } catch { data = null; } }
    if (!response.ok) throw new ApiError(response.status, data?.error && typeof data.error === 'object' ? data.error : { mensaje: `HTTP ${response.status}` });
    return data;
  }

  return {
    base,
    request,
    get: (path, query) => request(path, { query }),
    post: (path, body = {}) => request(path, { method: 'POST', body }),
    del: path => request(path, { method: 'DELETE' }),
    modeloServido: () => modeloServido,
    // Avisa cuando cambia X-Modelo-Servido (formato de la API: <run_id>@<sha256 12>). Devuelve la baja.
    onModeloServido: fn => { oyentes.add(fn); return () => oyentes.delete(fn); },
  };
}

// Cliente configurado por Vite. Es una función para que el módulo se pueda importar fuera de Vite (pruebas).
// La regla de producción (HTTPS, nunca localhost) aplica al modo `production` (el de `vite build` y Vercel);
// las pruebas locales compilan con `vite build --mode e2e` contra una API en 127.0.0.1.
let shared = null;
export function apiClient() {
  shared ??= createClient({ baseUrl: import.meta.env.VITE_API_BASE_URL, prod: import.meta.env.MODE === 'production' });
  return shared;
}
