// Modelo servido y monitoreo de la API (enunciado: la interfaz muestra la versión servida y el monitoreo mínimo).
// - Indicador en la cabecera: GET /version al cargar; luego se actualiza con la cabecera X-Modelo-Servido
//   (<run_id>@<sha256 12>) de cualquier respuesta de la API.
// - Diálogo «Monitoreo»: GET /monitoreo (éxito y causas de fin por escenario, latencia de decisión, HTTP, episodios).
import { apiClient } from './api-client.js';

const el = (tag, props = {}, ...children) => { const node = Object.assign(document.createElement(tag), props); node.append(...children.filter(c => c != null)); return node; };
const pct = v => v == null ? '—' : `${Math.round(v * 100)}%`;
const ms = v => v == null ? '—' : `${Number(v).toFixed(1)} ms`;
const short = (s, n = 12) => s ? String(s).slice(0, n) : '—';
const causes = c => c && Object.keys(c).length ? Object.entries(c).map(([k, v]) => `${k} ${v}`).join(', ') : '—';
function table(headers, rows, empty) {
  if (!rows.length) return el('p', { className: 'preview-help', textContent: empty });
  return el('table', { className: 'model-table' }, el('thead', {}, el('tr', {}, ...headers.map(h => el('th', { textContent: h })))),
    el('tbody', {}, ...rows.map(r => el('tr', {}, ...r.map(c => el('td', { textContent: c }))))));
}

export function setupServiceStatus() {
  let api;
  try { api = apiClient(); } catch (error) { console.error(error); return; }

  const served = el('div', { id: 'served-model', className: 'served-model', title: 'Modelo que sirve la API (GET /version)' });
  served.setAttribute('role', 'status');
  document.querySelector('.masthead .connection').after(served);
  let version = null;
  const render = (texto, error = false) => { served.classList.toggle('error', error); served.textContent = texto; };
  const fromVersion = v => `MODELO SERVIDO · ${v.run_id} · sha256 ${short(v.model_sha256)} · ${v.environment_version} · commit ${short(v.git_commit, 7)}`;
  render('MODELO SERVIDO · consultando…');
  api.get('/version').then(v => { version = v; render(fromVersion(v)); }).catch(error => render(`MODELO SERVIDO · ${error.message}`, true));
  // Si cambia en el servidor (promoción o rollback), la cabecera lo dice antes que /version.
  api.onModeloServido(header => {
    const [runId, sha] = header.split('@');
    if (version && version.run_id === runId && short(version.model_sha256) === sha) return;
    version = null;render(`MODELO SERVIDO · ${runId} · sha256 ${sha || '—'}`);
  });

  const dialog = el('dialog', { className: 'monitor-dialog' });
  dialog.innerHTML = `<header><div><span class="eyebrow">API · GET /monitoreo</span><h2>Monitoreo</h2></div><div class="monitor-actions"><button class="button" id="monitor-refresh">Actualizar</button><button class="button" id="close-monitor" aria-label="Cerrar monitoreo">Cerrar ×</button></div></header><div id="monitor-body" aria-live="polite"></div>`;
  document.body.append(dialog);
  const body = dialog.querySelector('#monitor-body'), refresh = dialog.querySelector('#monitor-refresh');

  async function load() {
    refresh.disabled = true;body.replaceChildren(el('p', { className: 'preview-help', textContent: 'Consultando la API…' }));
    try {
      const m = await api.get('/monitoreo');
      const s = m.servido || {};
      const exito = (m.exito_por_escenario || []).map(r => [r.quien, r.escenario, r.episodios, pct(r.tasa_exito), causes(r.causas), causes(r.origen)]);
      const latencia = Object.entries(m.latencia_decision || {}).map(([q, l]) => [q, l.n, ms(l.p50_ms), ms(l.p95_ms), ms(l.max_ms)]);
      const http = Object.entries(m.http || {}).map(([ruta, r]) => [ruta, r.peticiones, r.errores_4xx, r.errores_5xx, ms(r.p50_ms), ms(r.p95_ms)]);
      const ep = m.episodios || {};
      body.replaceChildren(
        el('p', { className: 'model-kpis', textContent: `Servido: ${s.run_id || '—'} · sha256 ${short(s.model_sha256)} · ${s.environment_version || '—'} · nivel ${s.level_id || '—'} · anterior (rollback): ${s.anterior || '—'}` }),
        el('p', { className: 'preview-help', textContent: `Commit ${short(m.git_commit, 7)} · en marcha desde ${m.iniciado_en || '—'} · episodios en memoria ${ep.episodios ?? '—'} (activos ${ep.activos ?? '—'} de ${ep.maximo ?? '—'}). Contadores en memoria: se reinician con el servidor.` }),
        el('h4', { textContent: 'Éxito y causas de fin por escenario' }),
        table(['Modelo / política', 'Escenario', 'Episodios', 'Éxito', 'Causas de fin', 'Origen'], exito, 'Aún no hay episodios terminados ni evaluaciones.'),
        el('h4', { textContent: 'Latencia de decisión por paso' }),
        table(['Modelo / política', 'Pasos', 'p50', 'p95', 'Máx.'], latencia, 'Sin decisiones registradas.'),
        el('h4', { textContent: 'Peticiones y errores por ruta' }),
        table(['Ruta', 'Peticiones', 'Errores 4xx', 'Errores 5xx', 'p50', 'p95'], http, 'Sin peticiones registradas.'));
    } catch (error) {
      body.replaceChildren(el('p', { className: 'model-error', textContent: error.message }));
    } finally { refresh.disabled = false; }
  }

  const opener = el('button', { id: 'open-monitor', className: 'button', textContent: 'Monitoreo ↗' });
  (document.querySelector('#open-models') || document.querySelector('#open-catalog')).after(opener);
  opener.addEventListener('click', () => { dialog.showModal();load(); });
  refresh.addEventListener('click', load);
  dialog.querySelector('#close-monitor').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => opener.focus());
}
