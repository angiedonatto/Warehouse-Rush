// Las pruebas preparan la partida en la misma API que usa la página (VITE_API_BASE_URL, capa /api/*) y le
// pasan la sesión por sessionStorage, como la guarda la web (src/viewer-api.js). Sin cookies.
export const API = (process.env.WAREHOUSE_API_URL || 'http://127.0.0.1:7860').replace(/\/+$/, '');
export const CLAVE_SESION = 'warehouse-sesion';

export function viewerSession(request) {
  let id = null;
  async function call(method, path, data) {
    const headers = id ? { 'X-Sesion': id } : {};
    const url = `${API}/api/${path}`;
    const response = method === 'GET' ? await request.get(url, { headers }) : await request.post(url, { headers, data });
    const nueva = response.headers()['x-sesion'];
    if (nueva) id = nueva;
    return response;
  }
  return {
    get id() { return id; },
    get: path => call('GET', path),
    post: (path, data = {}) => call('POST', path, data),
    // La página o el contexto empiezan con esta sesión; si la web ya guardó otra (p. ej. tras perderla), se respeta.
    attach: target => target.addInitScript(([clave, valor]) => {
      if (valor && !sessionStorage.getItem(clave)) sessionStorage.setItem(clave, valor);
    }, [CLAVE_SESION, id]),
  };
}
