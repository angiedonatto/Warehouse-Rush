// Capa /api/* del visor (docs/api-contrato.md, sección 9): mismas rutas y formatos que el /api de Vercel,
// ahora servidas por la API de Render. Base de la función api() de la sección 9.3.
// - Dirección: VITE_API_BASE_URL (sin barra final). Sin ella se usa la ruta relativa /api/... (desarrollo local).
// - Sesión sin cookies: el identificador vive en sessionStorage y viaja en la cabecera X-Sesion (9.2).
// - Errores de /api/*: {"error": "texto", "codigo": "..."} (9.7). El Error lanzado lleva .codigo y .status.
// - Espera: si una petición tarda más de SLOW_MS, se avisa (Render Free tarda ~18 s en despertar, sección 8).

const API_BASE = String(import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '');
export const API_BASE_URL = API_BASE;   // '' = mismo servidor que la web (desarrollo local)
export const CLAVE_SESION = 'warehouse-sesion';
const SLOW_MS = 3000;
export const MENSAJE_DESPERTANDO = 'Despertando el servidor… (la primera petición puede tardar unos 20 s)';

// sessionStorage puede no existir o lanzar (modo privado, almacenamiento bloqueado): la sesión sigue en memoria.
const storage = {
  get() { try { return sessionStorage.getItem(CLAVE_SESION); } catch { return null; } },
  set(value) { try { sessionStorage.setItem(CLAVE_SESION, value); } catch { /* solo en memoria */ } },
  remove() { try { sessionStorage.removeItem(CLAVE_SESION); } catch { /* solo en memoria */ } },
};
let sesionId = storage.get();

// Mensajes para el usuario cuando el código pide algo distinto del texto del servidor.
const MENSAJES = {
  demasiadas_sesiones: 'El servidor tiene el máximo de partidas abiertas (100). Espera unos minutos y vuelve a intentarlo.',
  diagnostico_en_curso: 'Ya hay un diagnóstico corriendo en el servidor (se hacen de a uno). Espera unos segundos y vuelve a intentarlo.',
  sesion_no_encontrada: 'La sesión se perdió porque el servidor se reinició o estuvo inactivo. Se reinicia la misión.',
};

// Avisos de espera: los oyentes reciben el mensaje mientras alguna petición lenta sigue abierta, y null al terminar.
const oyentes = new Set();
const lentas = new Map();
let siguiente = 0;
function avisar() {
  const mensaje = lentas.size ? [...lentas.values()].at(-1) : null;
  for (const fn of oyentes) fn(mensaje);
}
export function onWait(fn) { oyentes.add(fn); return () => oyentes.delete(fn); }

export async function api(path, body, { waitMessage = MENSAJE_DESPERTANDO } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (sesionId) headers['X-Sesion'] = sesionId;
  const id = ++siguiente;
  const reloj = setTimeout(() => { lentas.set(id, waitMessage); avisar(); }, SLOW_MS);
  let response;
  try {
    response = await fetch(`${API_BASE}/api/${path}`, {
      method: body === undefined ? 'GET' : 'POST', headers, credentials: 'omit',   // sin cookies
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    const error = new Error('No se pudo conectar con la API. Si estuvo inactiva, puede estar despertando (~20 s): reintenta.');
    error.codigo = 'sin_conexion';
    throw error;
  } finally {
    clearTimeout(reloj);
    if (lentas.delete(id)) avisar();
  }
  let result = {};
  try { result = await response.json(); } catch { /* cuerpo vacío o no JSON: se informa con el estado HTTP */ }
  const nueva = response.headers.get('X-Sesion') || result.sesion_id;          // la API la devuelve siempre
  if (nueva && nueva !== sesionId) { sesionId = nueva; storage.set(nueva); }
  if (!response.ok) {
    if (result.codigo === 'sesion_no_encontrada') { sesionId = null; storage.remove(); }
    const texto = typeof result.error === 'string' ? result.error : result.error?.mensaje;
    const error = new Error(MENSAJES[result.codigo] || texto || `HTTP ${response.status}`);
    error.codigo = result.codigo || result.error?.codigo || null;
    error.status = response.status;
    throw error;
  }
  return result;
}
