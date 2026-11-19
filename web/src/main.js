import { apiClient } from './api-client.js';
import { setupCatalog } from './catalog.js';
import { setupModelCatalog } from './models-catalog.js';
import { setupServiceStatus } from './service-status.js';
import './style.css';
import { renderOrderSheet, renderRack } from './order-sheet.js';
import { WarehouseScene } from './warehouse.js';

const $ = selector => document.querySelector(selector);
let scene, current, layoutInfo, running = false, busy = false, changing = false, timer = null;
let toastTimer;
const handling = document.createElement('div');handling.id='handling-status';handling.className='handling-status';handling.setAttribute('aria-live','polite');document.querySelector('.robot-panel .panel-title').after(handling);
let selectedRack = 'E01';
const sheet = document.createElement('section');sheet.id = 'order-sheet';sheet.className = 'order-sheet';sheet.setAttribute('aria-live', 'polite');document.querySelector('.sidebar').prepend(sheet);
const packingPanel=document.createElement('section');packingPanel.className='dispatch-panel';packingPanel.innerHTML='<span class="eyebrow">DESPACHO · EMPAQUE</span><p id="packing-status">Esperando productos</p><button id="inspect-dispatch" class="button">Ver despacho</button>';
sheet.after(packingPanel);
const inventoryPanel = document.createElement('section');inventoryPanel.className = 'order-sheet';
const rackSelect = document.createElement('select');rackSelect.setAttribute('aria-label', 'Seleccionar estantería');
for (let i = 1; i <= 6; i++) { const id = `E${String(i).padStart(2, '0')}`;rackSelect.add(new Option(id, id)); }
const rackDetail = document.createElement('div');rackDetail.id = 'rack-detail';inventoryPanel.append(rackSelect, rackDetail);packingPanel.after(inventoryPanel);
rackSelect.addEventListener('change', () => { selectedRack = rackSelect.value;if (scene) { scene.selectedRack = selectedRack;scene.inspectedStation = null;scene.dirty = true; }renderRack(rackDetail, current.state, selectedRack); });
const makeupLabel = document.createElement('label');makeupLabel.className = 'makeup-control';
makeupLabel.innerHTML = '<input id="makeup" type="checkbox"> Pedidos de maquillaje';
const seedInput = document.createElement('input');seedInput.id = 'order-seed';seedInput.type = 'number';seedInput.min = '0';seedInput.max = '4294967295';seedInput.value = '10000';seedInput.setAttribute('aria-label', 'Semilla del pedido');
const newOrder = document.createElement('button');newOrder.textContent = 'Generar pedido';newOrder.className = 'button';newOrder.addEventListener('click', () => { $('#makeup').checked = true;reset(); });
// Modo visible (enunciado: manual / aleatorio / referencia / evaluación / entrenamiento).
const modeBadge = document.createElement('span');modeBadge.id = 'mode-badge';modeBadge.className = 'mode-badge';modeBadge.setAttribute('role', 'status');
document.querySelector('.toolbar').append(makeupLabel, seedInput, newOrder, modeBadge);
const MODES = { manual: ['manual', 'MODO · CONTROL MANUAL'], random: ['random', 'MODO · ALEATORIO'], heuristic: ['reference', 'MODO · REFERENCIA (REGLA BFS)'], ppo: ['evaluation', 'MODO · EVALUACIÓN · MODELO CONGELADO'] };
// Enlace directo: ?modelo=<id>&cerrado=1&semilla=N carga ese modelo; ?catalogo=<id> abre su ficha.
const params = new URLSearchParams(location.search);
function syncUrl(payload) {
  const next = new URLSearchParams(location.search);
  for (const key of ['modelo', 'cerrado', 'semilla', 'catalogo']) next.delete(key);
  if (payload.model) { next.set('modelo', payload.model.id);if (payload.state.pasillo_bloqueado) next.set('cerrado', '1');next.set('semilla', payload.seed); }
  history.replaceState(null, '', `${location.pathname}${next.size ? `?${next}` : ''}`);
}
$('#makeup').addEventListener('change', reset);
const names = { iso: 'VISTA ISOMÉTRICA', fpv: 'PRIMERA PERSONA', side: 'VISTA LATERAL', station: 'DETALLE DE ESTACIÓN' };
const actionNames = { AVANZAR: 'Navegando al objetivo', GIRAR_IZQUIERDA: 'Girando a la izquierda', GIRAR_DERECHA: 'Girando a la derecha', FRENAR: 'Robot detenido', INTERACTUAR: 'Interactuando con estación', CARGAR:'Recogiendo producto', DESCARGAR:'Entregando productos', SUBIR:'Elevando plataforma', BAJAR:'Bajando plataforma' };
const speed = () => Number($('#speed').value);

function toast(message) {
  clearTimeout(toastTimer);$('#toast').textContent = message;$('#toast').hidden = false;
  toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 6500);
}

const sessionNotice = document.createElement('p');sessionNotice.id='session-notice';sessionNotice.className='session-notice';sessionNotice.hidden=true;sessionNotice.setAttribute('role','alert');
const networkNotice = document.createElement('p');networkNotice.id='network-notice';networkNotice.className='session-notice';networkNotice.hidden=true;networkNotice.setAttribute('role','status');
document.querySelector('.toolbar').before(sessionNotice,networkNotice);
const LOST_SESSION = 'La partida se perdió porque el servidor se reinició o estuvo inactivo. Se inicia una misión nueva; el avance y el inventario acumulado no se pudieron recuperar. La bodega comienza con su stock inicial.';
function showLostSession() { sessionNotice.textContent=LOST_SESSION;sessionNotice.hidden=false; }
async function api(path, body) {
  const result = await apiClient().request(`/api/${path}`, body === undefined ? {} : { method:'POST', body });
  $('#connection-label').textContent = 'Simulador conectado';$('#connection-dot').style.background = '#5ae879';
  return result;
}

// Modelos recomendados de la API: su identidad y versión vienen de Render. Cada uno corre en el ambiente
// exacto de su evaluación (mapa, pedidos y recompensa), con identidad verificable.
const policyValue = payload => payload.model ? `model:${payload.model.id}` : payload.policy;
const shortSha = sha => sha ? sha.slice(0, 12) : '';
function populateModels() {
  const select = $('#policy');
  select.querySelectorAll('option[data-served]').forEach(option => option.remove());

  for (const model of layoutInfo?.models || []) {
    const option = document.createElement('option');
    option.value = `model:${model.id}`;option.dataset.served = '1';
    option.textContent = `PPO · ${model.id} · ${model.nivel.split(' · ')[0]} (${model.estado})`;
    select.append(option);
  }
  if(current?.model)ensureModelOption(current.model.id);
}
function ensureModelOption(id) {
  const value=`model:${id}`;
  if(![...$('#policy').options].some(option=>option.value===value)) {
    const option=new Option(`PPO · ${id}`,value);option.dataset.served='1';$('#policy').add(option);
  }
  return value;
}
function modelDetail(model) {
  const final = model.test_final?.ppo || {};
  const tests = Object.entries(final).filter(([,r])=>r && r.success_rate != null).map(([scenario, r]) => `${scenario} ${Math.round(r.success_rate * 100)}%`).join(' · ');
  return `${model.id} · ${model.environment_version} · sha256 ${shortSha(model.model_sha256)}${tests ? ` · test final: ${tests}` : ''}`;
}

function controls() {
  const manual = current?.policy === 'manual';
  $('#orders').closest('label').hidden = Boolean(current?.makeup || current?.model);
  $('#play').disabled = !current || current.done || manual || changing;
  $('#step').disabled = !current || current.done || running || manual || changing;
  $('#reset').disabled = changing;
  $('#policy').disabled = $('#orders').disabled = $('#blocked').disabled = changing;
  $('#play span').textContent = running ? 'Pausar' : 'Iniciar';
  $('#play svg').innerHTML = running ? '<path d="M5 4h3v12H5zM12 4h3v12h-3z"/>' : '<path d="m6 3 11 7-11 7z"/>';
  $('#manual-controls').hidden = !manual;
  for(const button of document.querySelectorAll('[data-action="6"], [data-action="7"]')) button.hidden=!current?.makeup;
  document.querySelectorAll('[data-action]').forEach(button => { button.disabled = !current || current.done || busy || changing; });

}

function mountScene() {
  scene?.dispose();
  $('#station-labels').replaceChildren();
  scene = new WarehouseScene(layoutInfo.layout, $('#world'), $('#stage'), layoutInfo.catalog);
  scene.onDispatchSelect = inspectDispatch;
  scene.onPackingChange = status => {
    const phases={waiting:'Esperando productos',conveying:'Cinta en marcha · llevando productos a la caja',closing:'Cerrando la caja',partial:'Productos en caja · esperando el resto',ready:'♡ Caja preparada'};
    $('#packing-status').textContent=`${phases[status.phase]} · ${status.packed}/${status.requested} unidades encajadas`;
    packingPanel.dataset.phase=status.phase;
  };
  scene.onRackSelect = id => { scene.selectedRack = id;scene.inspectedStation = null;scene.dirty = true;selectedRack = id;rackSelect.value = id;renderRack(rackDetail, current.state, id); };
  $('.minimap-caption > span:last-child').textContent = `${layoutInfo.layout.width} × ${layoutInfo.layout.height} m`;
}

function settingsKey(){return `warehouse-controls:${apiClient().base}`;}
function rememberSettings(payload) {
  const settings=payload.model ? {policy:'ppo',model:payload.model.id,blocked:payload.state.pasillo_bloqueado,seed:payload.seed}
    : {orders:Math.min(2,payload.orders),policy:payload.policy,blocked:payload.state.pasillo_bloqueado,seed:payload.seed,makeup:payload.makeup};
  try {sessionStorage.setItem(settingsKey(),JSON.stringify(settings));}catch{/* Almacenamiento no disponible. */}
}
function previousSettings(){try{return JSON.parse(sessionStorage.getItem(settingsKey()));}catch{return null;}}
function renderState(payload, instant = false) {
  rememberSettings(payload);
  current = payload;
  scene.selectedRack = payload.makeup ? selectedRack : null;
  scene.setState(payload, instant);
  const s = payload.state, config = layoutInfo.layout.simulation;
  $('#position').innerHTML = `(${s.x}, ${s.y}) <span>m</span>`;
  $('#orientation').textContent = `${s.theta * 90}° · ${['Norte', 'Este', 'Sur', 'Oeste'][s.theta]}`;
  $('#velocity').innerHTML = `${s.v.toFixed(1)} <span>m/s</span>`;
  const batteryPercent = Math.max(0, s.bateria / config.battery_capacity * 100);
  $('#battery-value').innerHTML = `${Math.round(batteryPercent)}<span>%</span>`;
  $('#battery-fill').style.width = `${batteryPercent}%`;
  $('#battery-fill').style.background = batteryPercent < 20 ? '#ff6767' : batteryPercent < 40 ? '#edbd4a' : '#50ce6a';
  $('.battery-track').setAttribute('aria-valuenow', Math.round(batteryPercent));
  $('#cargo').innerHTML = s.carga ? `<span class="loaded-cargo">▣ Paquete ${s.carga}</span>` : '<span class="empty-cargo">Sin paquete</span>';
  $('#target').textContent = { P1: 'Recogida 1 (P1)', P2: 'Recogida 2 (P2)', DELIVERY: 'Entrega (D)' }[s.objetivo] || 'Misión completada';
  $('#target').classList.toggle('delivery-target', s.objetivo === 'DELIVERY');
  $('#steps').textContent = s.tiempo;$('#max-steps').textContent = config.max_steps;
  $('#step-progress').style.width = `${s.tiempo / config.max_steps * 100}%`;
  $('#deliveries').innerHTML = `${s.entregas} <small>/ ${payload.orders}</small>`;
  $('#collisions').textContent = s.colisiones;$('#reward').textContent = s.recompensa_total.toFixed(2);
  $('#robot-activity').textContent = payload.done ? payload.info.success ? 'Todas las entregas completadas' : 'Episodio finalizado' : payload.last_action ? actionNames[payload.last_action.name] : 'Listo para comenzar';
  $('#robot-mode').textContent = payload.done ? payload.info.success ? 'MISIÓN COMPLETA' : 'FINALIZADO' : s.carga ? 'CON CARGA' : s.tiempo === 0 ? 'EN BASE' : s.v ? 'EN MOVIMIENTO' : 'DETENIDO';
  $('#mission-title').textContent = payload.orders === 2 ? 'P1 → ENTREGA → P2 → ENTREGA' : 'P1 → ENTREGA';
  const completedStages = s.entregas * 2 + (s.carga ? 1 : 0);
  $('#mission-sequence').innerHTML = (payload.orders === 2 ? ['P1', 'D', 'P2', 'D'] : ['P1', 'D']).map((label, index) => `${index ? '<i></i>' : ''}<span class="${index < completedStages ? 'complete' : index === completedStages ? 'current' : ''}">${label}</span>`).join('');
  $('#mission-status').textContent = payload.done ? payload.info.success ? 'Misión completada ✓' : 'Límite del episodio' : running ? 'Misión en ejecución' : s.tiempo ? 'En pausa' : 'Esperando inicio';
  const last = payload.events.at(-1);
  $('#last-event').textContent = last?.text || 'Simulador listo';
  $('#event-step').textContent = `${String(Math.floor(s.tiempo / 60)).padStart(2, '0')}:${String(s.tiempo % 60).padStart(2, '0')}`;
  $('#footer-detail').textContent = `1 paso = 1 s · Semilla ${payload.seed} · ${payload.model ? `PPO ${modelDetail(payload.model)}` : payload.policy === 'ppo' ? 'PPO real, sin acciones BFS' : payload.policy === 'manual' ? 'Acciones manuales' : payload.policy === 'heuristic' ? 'Baseline heurístico BFS' : 'Baseline aleatorio'}`;
  const [modeKind, modeText] = MODES[payload.policy] || ['', payload.policy];
  modeBadge.className = `mode-badge ${modeKind}`;modeBadge.textContent = payload.model ? `${modeText} · ${payload.model.id}` : `${modeText}${!payload.makeup ? ' · MODO HISTÓRICO P1/P2' : ''}`;
  const banner = $('#mission-banner');banner.hidden = !payload.done;
  if (payload.done) {
    banner.classList.toggle('warning', !payload.info.success);
    banner.textContent = payload.info.success ? `✓ Misión completada · ${s.entregas} ${payload.makeup ? 'líneas entregadas' : 'entregas'} · ${s.tiempo} pasos` : `Episodio finalizado · ${{ time_limit: 'Límite de tiempo', battery_depleted: 'Batería agotada', unreachable_target: 'Objetivo inaccesible', insufficient_budget: 'Batería o tiempo insuficientes para recoger y volver' }[payload.info.end_reason] || payload.info.end_reason}`;
    pause();
  }
  document.querySelectorAll('.legend li').forEach(el => { if (['P1', 'P2'].includes(el.querySelector('kbd')?.textContent)) el.hidden = Boolean(payload.makeup); });
  handling.hidden = !s.lift;
  renderOrderSheet(sheet, s);
  inventoryPanel.hidden = !s.inventory;
  packingPanel.hidden = !payload.makeup;
  if (s.inventory) renderRack(rackDetail, s, selectedRack);
  if (s.order) {
    const line = s.order.lines[s.pedido_actual];
    if (s.lift) {
      const phases={idle:'Plataforma baja · puede desplazarse',raising:'Elevando · desplazamiento bloqueado',ready:'Altura alcanzada · listo para transferir',lowering:'Bajando carga · desplazamiento bloqueado'};
      const reasons={nearby_product:'Siguiente producto cercano que cabe en la carga',capacity:'Volver a despacho: capacidad completa',battery_or_time:'Volver a despacho: reservar batería y tiempo',all_picked:'Pedido recogido: ir a despacho',complete:'Pedido entregado',insufficient_budget:'No iniciar: presupuesto insuficiente para volver'};
      handling.textContent=`${phases[s.lift.phase]} · ${s.lift.height.toFixed(2)} m / ${s.lift.target.toFixed(2)} m · ${reasons[s.lift.plan.reason] || ''} · Viajes a despacho: ${s.lift.dispatch_visits}`;
      if (s.lift.phase !== 'idle' && !payload.done) $('#robot-activity').textContent=phases[s.lift.phase];
    }
    $('#cargo').textContent = s.cargo_lines?.length ? s.cargo_lines.map(l => `${l.name || l.subcategory} × ${l.quantity}`).join(' · ') : 'Sin productos';
    $('#target').textContent = !s.objetivo ? 'Entrega confirmada' : s.objetivo === 'DELIVERY' ? 'Despacho' : line ? `${line.level} · ${line.name || line.subcategory} × ${line.quantity}` : 'Entrega confirmada';
    $('#mission-title').textContent = `ORDEN ${s.order.id.slice(0, 8)} · ${s.order.state}`;
    $('#mission-sequence').textContent = s.order.lines.map(l => `${l.level} ${l.delivered ? '✓' : l.picked ? '→ Despacho' : '○'}`).join(' · ');
  }
  controls();
}

function pause() {
  running = false;clearTimeout(timer);timer = null;controls();
  if (current && !current.done) $('#mission-status').textContent = current.state.tiempo ? 'En pausa' : 'Esperando inicio';
}

async function executeStep(action) {
  if (busy || changing || !current || current.done) return;
  let lost=false;busy=true;controls();
  try { renderState(await api('step',action === undefined ? {} : {action})); }
  catch(error) {
    pause();
    if(error.codigo==='sesion_no_encontrada') {showLostSession();lost=true;}
    else {toast(error.message);$('#connection-label').textContent='Revisa la conexión';}
  } finally {busy=false;controls();}
  // Liberar busy antes de reset(): reset espera las transiciones en curso.
  // Nunca repetir el paso perdido ni reanudar automáticamente la reproducción.
  if(lost) await reset();
}

function schedule() {
  timer = setTimeout(async () => {
    if (!running) return;
    await executeStep();
    if (running && !current.done) schedule();
  }, 650 / speed());
}

async function reset() {
  pause();
  if (changing) return;
  // No reiniciar en medio de una petición: esperar su transición real primero.
  changing = true;controls();
  try {
    while (busy) await new Promise(resolve => setTimeout(resolve, 20));
    const choice = $('#policy').value;
    const result = await api('reset', choice.startsWith('model:')
      ? { policy: 'ppo', model: choice.slice(6), blocked: $('#blocked').checked, seed: Number(seedInput.value) }
      : { orders: Number($('#orders').value), policy: choice, blocked: $('#blocked').checked, seed: Number(seedInput.value), makeup: $('#makeup').checked });
    if (layoutInfo.layout_sha256 !== result.info.layout_sha256) {
      layoutInfo = await api('layout');
      populateModels();
      mountScene();
    }
    renderState(result, true);
    $('#makeup').checked = result.makeup;syncUrl(result);
    if (result.model) toast(`Modelo ${modelDetail(result.model)}`);

  } catch (error) {
    toast(error.message);
    if (current) { $('#orders').value = Math.min(2, current.orders);$('#policy').value = policyValue(current);$('#blocked').checked = current.state.pasillo_bloqueado; }
  } finally { changing = false;controls(); }
}

$('#play').addEventListener('click', () => {
  if (running) return pause();
  if (!current || current.done || changing) return;
  running = true;controls();$('#mission-status').textContent = 'Misión en ejecución';
  executeStep().then(() => { if (running) schedule(); });
});
$('#step').addEventListener('click', () => executeStep());
$('#reset').addEventListener('click', reset);
for (const id of ['policy', 'orders', 'blocked']) $(`#${id}`).addEventListener('change', reset);
$('#speed').addEventListener('change', () => { if (scene) scene.motionSpeed = 9 * speed();if (running) { clearTimeout(timer);schedule(); } });
$('#toggle-route').addEventListener('click', event => { scene.showRoute = !scene.showRoute;scene.dirty = true;event.currentTarget.classList.toggle('active', scene.showRoute);event.currentTarget.setAttribute('aria-pressed', scene.showRoute); });
$('#toggle-sensors').addEventListener('click', event => { scene.showSensors = !scene.showSensors;scene.dirty = true;event.currentTarget.classList.toggle('active', scene.showSensors);event.currentTarget.setAttribute('aria-pressed', scene.showSensors); });
function selectCamera(name) {
  if (!scene) return;
  scene.selectCamera(name);$('#camera-label').textContent = names[name];
  document.querySelectorAll('[data-camera]').forEach(button => { const selected = button.dataset.camera === name;button.classList.toggle('selected', selected);button.setAttribute('aria-pressed', selected); });
}
document.querySelectorAll('[data-camera]').forEach(button => button.addEventListener('click', () => selectCamera(button.dataset.camera)));
$('#home-camera').addEventListener('click', () => selectCamera('iso'));
function inspectDispatch() {
  if (!scene) return;
  scene.inspectedStation='DELIVERY';selectCamera('station');$('#camera-label').textContent='DETALLE DE DESPACHO';
}
$('#inspect-dispatch').addEventListener('click',inspectDispatch);
// OrbitControls captura punteros en el escenario; los controles superpuestos
// deben conservar su click en lugar de iniciar una órbita de cámara.
$('.scene-toggles').addEventListener('pointerdown', event => event.stopPropagation());
document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => executeStep(Number(button.dataset.action))));
window.addEventListener('keydown', event => {
  if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(document.activeElement.tagName)) return;
  if (current?.policy === 'manual') {
    const action = { w: 0, ArrowUp: 0, a: 1, ArrowLeft: 1, d: 2, ArrowRight: 2, s: 3, ArrowDown: 3, e: 4, q: 5, r: 6, f: 7 }[event.key];
    if (action !== undefined) { event.preventDefault();executeStep(action); }
  } else if (event.code === 'Space' && !event.repeat) { event.preventDefault();$('#play').click(); }
});
window.addEventListener('pagehide', () => { pause();scene?.dispose(); });

async function start() {
  try {
    const client=apiClient();
    client.onActivity(({phase})=>{
      networkNotice.hidden=!['waking','waiting'].includes(phase);
      networkNotice.textContent=phase==='waking' ? 'Despertando el servidor… Si estuvo inactivo, el primer acceso puede tardar unos 20 segundos.' : 'Esperando respuesta del servidor…';
    });
    client.onSessionChange(({previous,current})=>{if(previous&&current&&previous!==current)showLostSession();});
    try {current=await api('state');}
    catch(error) {
      if(error.codigo!=='sesion_no_encontrada')throw error;
      showLostSession();
      current=await api('reset',previousSettings() || {orders:Number($('#orders').value),policy:$('#policy').value,blocked:$('#blocked').checked,seed:Number(seedInput.value),makeup:$('#makeup').checked});
    }
    // Primero obtener/reanudar la partida, después su mapa con la misma X-Sesion.
    layoutInfo=await api('layout');
    populateModels();
    $('#policy').value = policyValue(current);$('#orders').value = Math.min(2, current.orders);$('#blocked').checked = current.state.pasillo_bloqueado;$('#makeup').checked = current.makeup;seedInput.value = current.seed;
    mountScene();
    renderState(current, true);
    $('#scene-loading').hidden = true;
    const linked = params.get('modelo');
    if (linked && layoutInfo.models?.some(m => m.id === linked)) {
      $('#policy').value = `model:${linked}`;$('#blocked').checked = params.get('cerrado') === '1';
      if (/^\d+$/.test(params.get('semilla') || '')) seedInput.value = params.get('semilla');
      await reset();
    } else if (current.model) syncUrl(current);
    // Diagnóstico de la integración sin exponer acciones privilegiadas al modelo.
    window.warehouseViewer = { get state() { return current; }, get scene() { return scene; }, get running() { return running; } };
  } catch (error) {
    $('#scene-loading').innerHTML = '<b>No se pudo iniciar la visualización</b><span>Comprueba la conexión con la API y la compatibilidad WebGL de tu navegador. Si el servidor está despertando, espera un momento y recarga.</span>';
    $('#connection-label').textContent = 'Sin conexión';$('#connection-dot').style.background = '#ff6767';toast(error.message);console.error(error);
  }
}
setupCatalog();
setupModelCatalog({
  load: (id, blocked) => {
    $('#policy').value=ensureModelOption(id);$('#blocked').checked=blocked;reset();
  },
  initial: params.get('catalogo'),
});
setupServiceStatus();
start();
