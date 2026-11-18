// Catálogo de modelos y experimentos (R4), con el mismo diálogo que el catálogo de productos de Naomi
// (catalog.js): buscar, filtrar, ver identidad, cargar en la bodega, evaluar y comparar.
// Datos: /modelos/catalogo.json, generado por `python -m pipelines.catalogo` desde manifiestos + MLflow.

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
function ppoSuccess(model) {
  return Object.values(model.evaluacion || {}).map(p => p.ppo?.success_rate).filter(v => v != null);
}

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
  const compare = new Set();

  async function data() {
    if (models.length) return;
    const response = await fetch('/modelos/catalogo.json');
    if (!response.ok) throw new Error('No se pudo cargar el catálogo de modelos');
    const json = await response.json();
    models = json.modelos;tracking = json.tracking_uri;
    for (const level of new Set(models.map(m => m.nivel))) $('#models-level').add(new Option(level, level));
    for (const state of new Set(models.map(m => m.estado))) $('#models-state').add(new Option(ESTADOS[state] || state, state));
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

  async function evaluate(model, blocked, out, button) {
    button.disabled = true;out.replaceChildren(el('p', { className: 'preview-help', textContent: 'Evaluando en el servidor… (modelo congelado, determinista)' }));
    try {
      const response = await fetch('/api/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: model.id, blocked, episodes: 10 }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Error al evaluar');
      const s = result.summary, mon = result.monitoring;
      out.replaceChildren(
        el('span', { className: 'mode-badge evaluation', textContent: 'MODO · EVALUACIÓN' }),
        el('p', { textContent: `${result.episodes.length} episodios · semillas ${result.seeds.join('–')} · paso ${result.scenario} · catálogo ${result.catalog} · ${result.environment_version}` }),
        el('p', { className: 'model-kpis', textContent: `Éxito ${pct(s.success_rate)} · pasos (éxitos) ${num(s.mean_steps_success)} · choques/ep ${num(s.mean_collisions, 2)} · causas: ${reasons(s.end_reasons)}` }),
        el('p', { className: 'preview-help', textContent: `Monitoreo: inferencia ${num(mon.inference_ms_mean, 2)} ms/paso (p95 ${num(mon.inference_ms_p95, 2)}) · ${mon.steps} pasos · errores ${mon.errors} · sha256 servido ${mon.served_sha256.slice(0, 12)}` }),
        table(['Semilla', 'Éxito', 'Pasos', 'Choques', 'Fin'], result.episodes.map(e => [e.seed, e.success ? 'sí' : 'no', e.steps ?? '—', e.collisions ?? '—', e.end_reason || e.error])));
    } catch (error) {
      out.replaceChildren(el('p', { className: 'model-error', textContent: error.message }));
    } finally { button.disabled = false; }
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
    const blockedInput = el('input', { type: 'checkbox', id: 'models-blocked' });
    const actions = model.servido ? el('div', { className: 'model-actions' },
      el('label', { className: 'model-check' }, blockedInput, ' Paso (6,14) cerrado'),
      el('button', { className: 'button', textContent: 'Cargar en la bodega', onclick: () => { dialog.close();load(model.id, blockedInput.checked); } }),
      el('button', { className: 'button', textContent: 'Evaluar 10 episodios', onclick: event => evaluate(model, blockedInput.checked, evalOut, event.currentTarget) }))
      : el('p', { className: 'preview-help', textContent: 'Modelo histórico: identidad, evaluación y curva disponibles; la API ejecuta en vivo los modelos recomendados (pesos de los demás en DVC).' });
    detail.replaceChildren(
      el('span', { className: `state-badge ${model.estado}`, textContent: ESTADOS[model.estado] || model.estado }),
      el('h3', { textContent: model.id }),
      el('p', { className: 'model-kpis', textContent: `${model.nivel} · semilla ${model.seed} · ${model.environment_version} · ${model.algorithm?.toUpperCase()}` }),
      el('dl', { className: 'model-facts' },
        el('dt', { textContent: 'Hipótesis' }), el('dd', { textContent: model.hipotesis || '—' }),
        el('dt', { textContent: 'Cambios frente a la base' }), el('dd', { textContent: changes.join(' · ') || 'receta base' }),
        el('dt', { textContent: 'Presupuesto' }), el('dd', { textContent: `${(model.presupuesto_pasos || 0).toLocaleString('es')} pasos · ${num(model.minutos)} min` }),
        el('dt', { textContent: 'Estado en MLflow' }), el('dd', {}, `${model.estado} · `, el('a', { href: model.mlflow.run_url, target: '_blank', rel: 'noopener', textContent: `run ${model.mlflow.experimento || ''} ↗` })),
        el('dt', { textContent: 'Identidad' }), el('dd', { textContent: `sha256 ${model.model_sha256?.slice(0, 16)}… · ${model.manifiesto}` }),
        model.decision ? el('dt', { textContent: 'Decisión' }) : null, model.decision ? el('dd', { textContent: model.decision }) : null),
      actions, evalOut,
      evaluationBlock(`Evaluación registrada · ${model.suite || ''}`, model.evaluacion),
      evaluationBlock('Test final reservado (una sola vez)', model.test_final),
      model.curva ? el('figure', { className: 'model-curve' }, el('span', { className: 'mode-badge training', textContent: 'MODO · ENTRENAMIENTO (registro del run)' }), el('img', { src: model.curva, alt: `Curvas de entrenamiento de ${model.id}`, loading: 'lazy' })) : null);
    history.replaceState(null, '', `${location.pathname}?${new URLSearchParams({ ...Object.fromEntries(new URLSearchParams(location.search)), catalogo: model.id })}`);
  }

  function filter() {
    const query = $('#models-search').value.toLocaleLowerCase('es'), level = $('#models-level').value, state = $('#models-state').value;
    const shown = models.filter(m => (!level || m.nivel === level) && (!state || m.estado === state) && `${m.id} ${m.hipotesis}`.toLocaleLowerCase('es').includes(query));
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
    for (const m of chosen) for (const [scenario, policies] of Object.entries(m.evaluacion || {})) {
      const p = policies.ppo || {};
      rows.push([m.id, m.nivel, ESTADOS[m.estado] || m.estado, m.seed, (m.presupuesto_pasos || 0).toLocaleString('es'), scenario, pct(p.success_rate), num(p.mean_steps), num(p.mean_collisions, 2), reasons(p.end_reasons)]);
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
