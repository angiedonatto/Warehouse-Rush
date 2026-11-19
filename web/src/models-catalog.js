// Catálogo de modelos y experimentos (R4), con el mismo diálogo que el catálogo de productos de Naomi
// (catalog.js): buscar, filtrar, ver identidad, cargar en la bodega, evaluar y comparar.
// Datos: GET /catalogo de la API (estado, alias, evaluable, sha256, presupuesto, decisión y evaluación de la
// suite: la API manda) + /modelos/catalogo.json estático (`python -m pipelines.catalogo`), que solo aporta
// hipótesis, cambios, curva, enlace a MLflow y causas de fin. Se unen por run_id; lo que la API no lista no se muestra.
import { apiClient } from './api-client.js';
import { api as viewerApi } from './viewer-api.js';

const ESTADOS = { recomendado: 'Recomendado', candidato: 'Candidato', rechazado: 'Rechazado', fallido: 'Fallido', interrumpido: 'Interrumpido' };
const POLITICAS = { ppo: 'PPO', heuristic: 'Referencia (regla)', random: 'Aleatoria' };
const pct = value => value == null ? '—' : `${Math.round(value * 100)}%`;
const num = (value, digits = 1) => value == null ? '—' : Number(value).toFixed(digits);
const el = (tag, props = {}, ...children) => { const node = Object.assign(document.createElement(tag), props); node.append(...children.filter(c => c != null)); return node; };
function table(headers, rows) {
  const head = el('tr', {}, ...headers.map(h => el('th', { textContent: h })));
  return el('table', { className: 'model-table' }, el('thead', {}, head), el('tbody', {}, ...rows.map(r => el('tr', {}, ...r.map(c => el('td', { textContent: c }))))));
}
const reasons = r => r ? Object.entries(r).map(([k, v]) => `${k} ${v}`).join(', ') : '—';
// Evaluación de la API: {suite, episodios, determinista, ppo: {...}} o {..., por_escenario: {etiqueta: {...}}}.
function apiScenarios(evaluacion) {
  if (!evaluacion) return [];
  if (evaluacion.por_escenario) return Object.entries(evaluacion.por_escenario);
  return evaluacion.ppo ? [[evaluacion.suite, evaluacion.ppo]] : [];
}
function ppoSuccess(model) {
  return apiScenarios(model.evaluacion).map(([, m]) => m.success_rate).filter(v => v != null);
}
// Causas de fin del catálogo estático (la API no las publica): misma etiqueta de escenario o, si solo hay uno, ese.
function endReasons(estatico, etiqueta) {
  const evaluacion = estatico?.evaluacion || {};
  const entrada = evaluacion[etiqueta] || (Object.keys(evaluacion).length === 1 ? Object.values(evaluacion)[0] : null);
  return entrada?.ppo?.end_reasons || null;
}
function merge(api, estatico) {
  return {
    id: api.run_id, estado: api.estado, alias: api.alias || [], level_id: api.level_id, nivel: estatico?.nivel || api.level_id,
    seed: api.seed, environment_version: api.environment_version, algorithm: api.algorithm, model_sha256: api.model_sha256,
    manifiesto: api.manifest_uri, presupuesto_pasos: api.budget_steps, minutos: api.budget_minutes, decision: api.decision_reason,
    evaluable_con_api: api.evaluable_con_api, evaluacion: api.evaluacion, suite: api.evaluacion?.suite || api.evaluation_suite_id,
    test_final_api: api.test_final,
    // Solo del estático: descripción del experimento y detalle numérico del test final.
    hipotesis: estatico?.hipotesis, cambios: estatico?.cambios, curva: estatico?.curva, mlflow: estatico?.mlflow,
    test_final: estatico?.test_final, estatico,
    // «Cargar en la bodega» y el diagnóstico rápido: cualquier modelo que la API puede ejecutar (GET /catalogo
    // evaluable_con_api: versión NumPy verificada y ambiente vigente), no solo los dos recomendados (contrato 9.1).
    servido: Boolean(api.evaluable_con_api),
  };
}
// Evaluación oficial (docs/api-contrato.md, sección 6): POST /evaluaciones (202) y sondeo cada 2.5 s de
// GET /evaluaciones/trabajos/{id}. Suites fijas, política determinista, catálogo legacy-18: certificado: true.
// Solo suites de warehouse-v10 compatibles con el mapa del modelo (m1 y m1b: layout_v0.4; m1o: layout_v0.5).
const SUITES = { m1: ['suite-m1-v1', 'suite-m1b-v1', 'dev-m1-v1'], m1b: ['suite-m1b-v1', 'suite-m1-v1', 'dev-m1-v1'], m1o: ['suite-m1o-v1', 'dev-m1o-v1'] };
const POLITICAS_OFICIALES = { ppo: 'Este modelo (PPO)', heuristic: 'Referencia (regla BFS)', random: 'Aleatoria' };
const SONDEO_MS = 2500;
const ERRORES_OFICIALES = {
  cola_llena: 'La cola de evaluaciones está llena (3 esperando). Reintenta en un minuto.',
  evaluacion_no_encontrada: 'La evaluación se perdió: el servidor se reinició o pasaron más de 30 minutos. Lánzala de nuevo.',
  modelo_incompatible: 'El modelo no es compatible con esa suite (otro mapa o versión del ambiente).',
};
const espera = ms => new Promise(resolve => setTimeout(resolve, ms));
// Evaluación registrada en el manifiesto para esa suite (para comparar con la que se acaba de reconstruir).
function registrada(model, suite) {
  const ev = model.evaluacion;
  if (!ev) return null;
  if (ev.por_escenario) return Object.entries(ev.por_escenario).find(([label]) => label.startsWith(suite))?.[1] || null;
  return ev.suite === suite ? ev.ppo : null;
}

const ALIAS = { 'servido:produccion': 'en producción', 'anterior:produccion': 'producción anterior (rollback)' };
const aliasText = alias => alias.map(a => ALIAS[a] || a.replace(':', ' para ')).join(' · ');

export function setupModelCatalog({ load, initial }) {
  const dialog = el('dialog', { className: 'models-dialog' });
  dialog.innerHTML = `<header><div><span class="eyebrow">CATÁLOGO DE MODELOS · MANIFIESTOS + MLFLOW</span><h2>Modelos y experimentos</h2></div><button class="button" id="close-models" aria-label="Cerrar catálogo de modelos">Cerrar ×</button></header>
  <div class="catalog-filters"><label>Buscar run o hipótesis<input id="models-search" type="search" placeholder="m1-c3, entropía, potencial…"></label><label>Nivel<select id="models-level"><option value="">Todos los niveles</option></select></label><label>Estado<select id="models-state"><option value="">Todos los estados</option></select></label><button class="button" id="models-compare" disabled>Comparar (0)</button><span id="models-count" role="status"></span></div>
  <div class="catalog-body"><div id="models-grid" class="catalog-grid"></div><section class="product-preview model-detail" id="model-detail" aria-live="polite"></section></div>`;
  document.body.append(dialog);
  const $ = s => dialog.querySelector(s), grid = $('#models-grid'), detail = $('#model-detail');
  const opener = el('button', { id: 'open-models', className: 'button', textContent: 'Modelos y experimentos ↗' });
  document.querySelector('#open-catalog').after(opener);
  let models = [], tracking = '', selected = null;
  const oficiales = new Map();   // clave run|suite|política → estado de la evaluación oficial (sobrevive a cambiar de ficha)
  const compare = new Set();

  async function data() {
    if (models.length) return;
    const [publicado, estatico] = await Promise.all([
      apiClient().get('/catalogo'),
      fetch('/modelos/catalogo.json').then(r => r.ok ? r.json() : null).catch(() => null),
    ]);
    const porId = new Map((estatico?.modelos || []).map(m => [m.run_id || m.id, m]));
    models = publicado.modelos.map(m => merge(m, porId.get(m.run_id)));tracking = estatico?.tracking_uri || '';
    for (const level of new Set(models.map(m => m.level_id))) $('#models-level').add(new Option(models.find(m => m.level_id === level).nivel, level));
    for (const state of new Set(models.map(m => m.estado))) $('#models-state').add(new Option(ESTADOS[state] || state, state));
  }

  function apiEvaluationBlock(model) {
    const scenarios = apiScenarios(model.evaluacion);
    if (!scenarios.length) return null;
    const rows = scenarios.map(([scenario, m]) => [scenario, 'PPO', pct(m.success_rate), num(m.mean_steps), num(m.mean_collisions, 2), reasons(endReasons(model.estatico, scenario))]);
    return el('div', {}, el('h4', { textContent: `Evaluación registrada · ${model.suite || ''} · ${model.evaluacion.episodios} episodios${model.evaluacion.determinista ? ' · determinista' : ''}` }),
      table(['Escenario', 'Política', 'Éxito', 'Pasos', 'Choques/ep', 'Causas de fin'], rows));
  }

  function evaluationBlock(title, block) {
    if (!block) return null;
    const rows = [];
    for (const [scenario, policies] of Object.entries(block)) {
      for (const [policy, m] of Object.entries(policies)) {
        rows.push([scenario, POLITICAS[policy] || policy, pct(m.success_rate), num(m.mean_steps), num(m.mean_collisions, 2), reasons(m.end_reasons)]);
      }
    }
    return el('div', {}, el('h4', { textContent: title }), table(['Escenario', 'Política', 'Éxito', 'Pasos', 'Choques/ep', 'Causas de fin'], rows));
  }

  // Diagnóstico rápido de la API (POST /api/evaluate): pocas semillas, catálogo de la web, certificado: false.
  // La evaluación oficial es POST /evaluaciones (suites fijas); este botón no la reemplaza.
  async function evaluate(model, blocked, out, button) {
    button.disabled = true;out.replaceChildren(el('p', { className: 'preview-help', textContent: 'Diagnóstico en curso en el servidor… (modelo congelado, determinista; unos 5 s, hasta ~15 s si el modelo falla)' }));
    try {
      const result = await viewerApi('evaluate', { model: model.id, blocked, episodes: 10 }, { waitMessage: 'Diagnóstico en curso… si el servidor estaba dormido, primero tiene que despertar (~20 s).' });
      const s = result.summary, mon = result.monitoring;
      out.replaceChildren(
        el('span', { className: 'mode-badge evaluation', textContent: result.certificado === false ? 'DIAGNÓSTICO · NO CERTIFICADO' : 'MODO · EVALUACIÓN' }),
        result.nota ? el('p', { className: 'preview-help', textContent: result.nota }) : null,
        el('p', { textContent: `${result.episodes.length} episodios · semillas ${result.seeds.join('–')} · paso ${result.scenario} · catálogo ${result.catalog} · ${result.environment_version}` }),
        el('p', { className: 'model-kpis', textContent: `Éxito ${pct(s.success_rate)} · pasos (éxitos) ${num(s.mean_steps_success)} · choques/ep ${num(s.mean_collisions, 2)} · causas: ${reasons(s.end_reasons)}` }),
        el('p', { className: 'preview-help', textContent: `Monitoreo: inferencia ${num(mon.inference_ms_mean, 2)} ms/paso (p95 ${num(mon.inference_ms_p95, 2)}) · ${mon.steps} pasos · errores ${mon.errors} · sha256 servido ${mon.served_sha256.slice(0, 12)}` }),
        table(['Semilla', 'Éxito', 'Pasos', 'Choques', 'Fin'], result.episodes.map(e => [e.seed, e.success ? 'sí' : 'no', e.steps ?? '—', e.collisions ?? '—', e.end_reason || e.error])));
    } catch (error) {
      // 429 diagnostico_en_curso / demasiadas_sesiones llegan ya con un mensaje para el usuario (viewer-api.js).
      out.replaceChildren(el('p', { className: 'model-error', textContent: error.message }));
    } finally { button.disabled = false; }
  }

  function renderOficial(out, trabajo, model) {
    if (!out.isConnected && out.dataset.clave) return;   // la ficha cambió: el estado queda en `oficiales`
    const { estado, progreso = {}, error } = trabajo;
    const nodos = [el('span', { className: 'mode-badge evaluation', textContent: 'EVALUACIÓN OFICIAL · CERTIFICADA' }),
      el('p', { className: 'preview-help', textContent: `${trabajo.suite_id || trabajo.suite} · ${POLITICAS_OFICIALES[trabajo.politica] || trabajo.politica}${trabajo.episodios ? ` · ${trabajo.episodios} episodios` : ''}${trabajo.semillas ? ` · semillas ${trabajo.semillas.join('–')}` : ''}${trabajo.catalog_version ? ` · catálogo ${trabajo.catalog_version}` : ''}${trabajo.model_sha256 ? ` · sha256 ${trabajo.model_sha256.slice(0, 12)}` : ''}` })];
    if (error) nodos.push(el('p', { className: 'model-error', textContent: error }));
    else if (estado === 'enviando') nodos.push(el('p', { className: 'preview-help', textContent: 'Enviando… (si el servidor estaba dormido, tarda unos 20 s en despertar)' }));
    else if (estado === 'en_cola') nodos.push(el('p', { className: 'preview-help', textContent: `En cola: posición ${trabajo.posicion_en_cola ?? '—'} (se evalúa de a una).` }));
    else if (estado === 'en_curso') {
      const hechos = progreso.episodios_hechos, total = progreso.episodios_total || trabajo.episodios;
      const barra = el('progress', { className: 'official-progress', max: total || 1 });
      if (hechos != null) barra.value = hechos;
      nodos.push(barra, el('p', { className: 'preview-help', textContent: hechos != null ? `En curso: ${hechos} de ${total} episodios` : 'En curso (la política aleatoria no informa avance)' }));
    } else if (estado === 'terminada') {
      const r = trabajo.resultado.resumen, previa = trabajo.politica === 'ppo' ? registrada(model, trabajo.suite_id) : null;
      nodos.push(el('p', { className: 'model-kpis', textContent: `Éxito ${pct(r.success_rate)} · pasos ${num(r.mean_steps)} · choques/ep ${num(r.mean_collisions, 2)} · entregas/ep ${num(r.mean_deliveries, 2)} · causas: ${reasons(r.end_reasons)} · ${num(trabajo.segundos)} s en el servidor` }));
      if (previa) {
        const igual = Math.abs(previa.success_rate - r.success_rate) < 1e-9 && Math.abs((previa.mean_steps ?? 0) - (r.mean_steps ?? 0)) < 0.005;
        nodos.push(el('p', { className: igual ? 'preview-help official-match' : 'model-error', textContent: `Registrada en el manifiesto: éxito ${pct(previa.success_rate)} · pasos ${num(previa.mean_steps)} → ${igual ? 'la evaluación se reproduce igual' : 'no coincide con la registrada'}` }));
      }
      nodos.push(table(['Semilla', 'Éxito', 'Pasos', 'Choques', 'Entregas', 'Fin'], trabajo.resultado.por_episodio.map(e => [e.seed, e.success ? 'sí' : 'no', e.steps ?? '—', e.collisions ?? '—', e.deliveries ?? '—', e.end_reason || '—'])));
    } else if (estado === 'fallida') nodos.push(el('p', { className: 'model-error', textContent: `La evaluación no terminó: ${trabajo.error?.mensaje || trabajo.error || 'error desconocido'}` }));
    out.replaceChildren(...nodos);
  }

  async function evaluarOficial(model, suite, politica, out, button) {
    const clave = `${model.id}|${suite}|${politica}`;
    const trabajo = { estado: 'enviando', suite, politica };
    oficiales.set(clave, trabajo);out.dataset.clave = clave;
    const pintar = () => { if (out.dataset.clave === clave) renderOficial(out, trabajo, model); };
    button.disabled = true;pintar();
    try {
      const cuerpo = politica === 'ppo' ? { suite_id: suite, politica, run_id: model.id } : { suite_id: suite, politica };
      Object.assign(trabajo, await apiClient().post('/evaluaciones', cuerpo));pintar();
      while (trabajo.estado === 'en_cola' || trabajo.estado === 'en_curso') {
        await espera(SONDEO_MS);
        Object.assign(trabajo, await apiClient().get(`/evaluaciones/trabajos/${encodeURIComponent(trabajo.evaluacion_id)}`));pintar();
      }
    } catch (error) {
      trabajo.error = ERRORES_OFICIALES[error.codigo] || error.message;pintar();
    } finally { if (button.isConnected) button.disabled = false; }
  }

  function choose(model) {
    selected = model;
    grid.querySelectorAll('.product-card').forEach(card => card.setAttribute('aria-pressed', card.dataset.id === model.id ? 'true' : 'false'));
    const c = model.cambios || {};
    const changes = [
      c.recompensa && Object.keys(c.recompensa).length ? `recompensa ${Object.entries(c.recompensa).map(([k, v]) => `${k}=${v}`).join(', ')}` : null,
      c.ppo && Object.keys(c.ppo).length ? `PPO ${Object.entries(c.ppo).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ')}` : null,
      c.parada_estancamiento ? `parada por estancamiento ${c.parada_estancamiento}` : null,
      c.parent_run_id ? `continúa desde ${c.parent_run_id}` : null,
      c.layout ? `mapa ${c.layout.split('/').pop()}` : null,
    ].filter(Boolean);
    const evalOut = el('div', { className: 'model-eval-out' });
    const suites = SUITES[model.level_id] || [];
    const officialOut = el('div', { className: 'official-out', id: 'official-out' });
    const suiteSelect = el('select', { id: 'official-suite' }, ...suites.map(s => new Option(s, s, s === model.suite, s === model.suite)));
    const politicaSelect = el('select', { id: 'official-policy' }, ...Object.entries(POLITICAS_OFICIALES).map(([v, t]) => new Option(t, v)));
    const officialButton = el('button', { className: 'button', id: 'official-run', textContent: 'Evaluación oficial · suite fija (certificada)' });
    const mostrarOficial = () => {
      const clave = `${model.id}|${suiteSelect.value}|${politicaSelect.value}`, trabajo = oficiales.get(clave);
      officialOut.dataset.clave = clave;
      if (trabajo) renderOficial(officialOut, trabajo, model); else officialOut.replaceChildren();
      officialButton.disabled = trabajo && ['enviando', 'en_cola', 'en_curso'].includes(trabajo.estado);
    };
    suiteSelect.setAttribute('aria-label', 'Suite de la evaluación oficial');politicaSelect.setAttribute('aria-label', 'Política a evaluar');
    suiteSelect.addEventListener('change', mostrarOficial);politicaSelect.addEventListener('change', mostrarOficial);
    officialButton.addEventListener('click', () => evaluarOficial(model, suiteSelect.value, politicaSelect.value, officialOut, officialButton));
    const official = model.servido && suites.length ? el('section', { className: 'official-eval' },
      el('h4', { textContent: 'Evaluación oficial (la del registro)' }),
      el('p', { className: 'preview-help', textContent: 'Corre en el servidor sobre una suite fija (semillas fijas, determinista, catálogo legacy-18), igual que la evaluación registrada. Tarda unos 25 s con 50 episodios, más si el modelo falla. Se evalúa de a una.' }),
      el('div', { className: 'model-actions' }, suiteSelect, politicaSelect, officialButton), officialOut) : null;
    const blockedInput = el('input', { type: 'checkbox', id: 'models-blocked' });
    const actions = model.servido ? el('div', { className: 'model-actions' },
      el('label', { className: 'model-check' }, blockedInput, ' Paso (6,14) cerrado'),
      el('button', { className: 'button', textContent: 'Cargar en la bodega', onclick: () => { dialog.close();load(model.id, blockedInput.checked); } }),
      el('button', { className: 'button', textContent: 'Diagnóstico rápido · 10 episodios (no certificado)', title: 'Diagnóstico no certificado: 10 semillas con el catálogo de la web. La evaluación oficial usa las suites fijas.', onclick: event => evaluate(model, blockedInput.checked, evalOut, event.currentTarget) }))
      : el('p', { className: 'preview-help', textContent: `Modelo histórico: identidad, evaluación y curva disponibles. La API no lo ejecuta (${model.environment_version !== 'warehouse-v10' ? `es de ${model.environment_version}; se reproduce desde su etiqueta env/${model.environment_version}` : 'sin versión NumPy publicada'}); sus pesos están en DVC.` });
    detail.replaceChildren(
      el('span', { className: `state-badge ${model.estado}`, textContent: ESTADOS[model.estado] || model.estado }),
      el('h3', { textContent: model.id }),
      el('p', { className: 'model-kpis', textContent: `${model.nivel} · semilla ${model.seed} · ${model.environment_version} · ${model.algorithm?.toUpperCase()}` }),
      el('dl', { className: 'model-facts' },
        el('dt', { textContent: 'Hipótesis' }), el('dd', { textContent: model.hipotesis || '—' }),
        el('dt', { textContent: 'Cambios frente a la base' }), el('dd', { textContent: changes.join(' · ') || 'receta base' }),
        el('dt', { textContent: 'Presupuesto' }), el('dd', { textContent: `${(model.presupuesto_pasos || 0).toLocaleString('es')} pasos · ${num(model.minutos)} min` }),
        el('dt', { textContent: 'Estado' }), el('dd', {}, model.estado, model.alias.length ? ` · ${aliasText(model.alias)}` : '', model.mlflow?.run_url ? ' · ' : '', model.mlflow?.run_url ? el('a', { href: model.mlflow.run_url, target: '_blank', rel: 'noopener', textContent: `run ${model.mlflow.experimento || ''} en MLflow ↗` }) : null),
        el('dt', { textContent: 'Identidad' }), el('dd', { textContent: `sha256 ${model.model_sha256?.slice(0, 16)}… · ${model.manifiesto}${model.evaluable_con_api ? ' · ejecutable en la API' : ` · se evalúa desde ${model.environment_version}`}` }),
        model.decision ? el('dt', { textContent: 'Decisión' }) : null, model.decision ? el('dd', { textContent: model.decision }) : null),
      actions, evalOut, official,
      apiEvaluationBlock(model),
      model.test_final_api ? el('p', { className: 'model-kpis', textContent: `Test final reservado (una sola vez) · ${model.test_final_api.suite} · ${model.test_final_api.met ? 'cumple' : 'no cumple'}: ${model.test_final_api.criterion}` }) : null,
      evaluationBlock('Test final · detalle', model.test_final),
      model.curva ? el('figure', { className: 'model-curve' }, el('span', { className: 'mode-badge training', textContent: 'MODO · ENTRENAMIENTO (registro del run)' }), el('img', { src: model.curva, alt: `Curvas de entrenamiento de ${model.id}`, loading: 'lazy' })) : null);
    if (official) mostrarOficial();   // muestra una evaluación oficial en curso o terminada de este modelo
    history.replaceState(null, '', `${location.pathname}?${new URLSearchParams({ ...Object.fromEntries(new URLSearchParams(location.search)), catalogo: model.id })}`);
  }

  function filter() {
    const query = $('#models-search').value.toLocaleLowerCase('es'), level = $('#models-level').value, state = $('#models-state').value;
    const shown = models.filter(m => (!level || m.level_id === level) && (!state || m.estado === state) && `${m.id} ${m.hipotesis || ''}`.toLocaleLowerCase('es').includes(query));
    grid.replaceChildren();$('#models-count').textContent = `${shown.length} modelos`;
    for (const model of shown) {
      const success = ppoSuccess(model);
      const card = el('button', { className: 'product-card model-card', type: 'button' },
        el('span', { className: `state-badge ${model.estado}`, textContent: `${ESTADOS[model.estado] || model.estado}${model.servido ? ' · en vivo' : ''}` }),
        el('strong', { textContent: model.id }),
        el('small', { textContent: `${model.nivel} · éxito ${success.map(pct).join(' / ') || '—'}` }));
      card.dataset.id = model.id;card.setAttribute('aria-pressed', 'false');
      const pick = el('input', { type: 'checkbox', checked: compare.has(model.id), title: 'Agregar a la comparación' });
      pick.addEventListener('click', event => { event.stopPropagation(); if (pick.checked && compare.size >= 3) { pick.checked = false; return; } pick.checked ? compare.add(model.id) : compare.delete(model.id); updateCompare(); });
      card.append(el('label', { className: 'model-check', onclick: event => event.stopPropagation() }, pick, ' comparar'));
      card.addEventListener('click', () => choose(model));
      grid.append(card);
    }
    if (!shown.length) grid.append(el('p', { textContent: 'No hay modelos con ese filtro.' }));
    const keep = shown.find(m => m.id === selected?.id) || shown[0];
    if (keep) choose(keep);
  }

  function updateCompare() { $('#models-compare').textContent = `Comparar (${compare.size})`;$('#models-compare').disabled = compare.size < 2; }
  $('#models-compare').addEventListener('click', () => {
    const chosen = models.filter(m => compare.has(m.id));
    const suites = new Set(chosen.map(m => m.suite));
    const rows = [];
    for (const m of chosen) for (const [scenario, p] of apiScenarios(m.evaluacion)) {
      rows.push([m.id, m.nivel, ESTADOS[m.estado] || m.estado, m.seed, (m.presupuesto_pasos || 0).toLocaleString('es'), scenario, pct(p.success_rate), num(p.mean_steps), num(p.mean_collisions, 2), reasons(endReasons(m.estatico, scenario))]);
    }
    detail.replaceChildren(el('h3', { textContent: 'Comparación de candidatos' }),
      suites.size > 1 ? el('p', { className: 'model-error', textContent: `Atención: suites distintas (${[...suites].join(', ')}); los resultados no son comparables entre niveles o mapas.` }) : el('p', { className: 'preview-help', textContent: `Misma suite (${[...suites][0]}): mismas semillas, política determinista.` }),
      table(['Run', 'Nivel', 'Estado', 'Semilla', 'Pasos', 'Escenario', 'Éxito', 'Pasos/ep', 'Choques/ep', 'Causas de fin'], rows));
  });

  async function open(id) {
    try { await data(); } catch (error) { alert(error.message); return; }
    dialog.showModal();filter();
    const target = id && models.find(m => m.id === id);
    if (target) choose(target);
  }
  opener.addEventListener('click', () => open());
  $('#models-search').addEventListener('input', filter);$('#models-level').addEventListener('change', filter);$('#models-state').addEventListener('change', filter);
  $('#close-models').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    const params = new URLSearchParams(location.search);params.delete('catalogo');
    history.replaceState(null, '', `${location.pathname}${params.size ? `?${params}` : ''}`);opener.focus();
  });
  if (initial) open(initial);
}
