// Sólo representa cantidades confirmadas por el simulador.
export function renderOrderSheet(container, state) {
  const previous = new Map([...container.querySelectorAll('li[data-sku]')].map(el => [el.dataset.sku, el.className]));
  container.replaceChildren();
  if (!state.order) { container.hidden = true;return; }
  container.hidden = false;
  const order = state.order;
  const heading = document.createElement('h2');heading.textContent = '♡ Hoja de pedido';container.append(heading);
  const number = document.createElement('p');number.className = 'order-number';number.textContent = `Orden ${order.id.slice(0, 8)} · ${order.state}${state.inventory?.catalog_version === 'legacy-18' ? ' · Catálogo anterior conservado' : ''}`;container.append(number);
  const list = document.createElement('ul');
  for (const line of order.lines) {
    const item = document.createElement('li');item.dataset.sku = line.sku;
    item.className = line.delivered === line.quantity ? 'delivered' : line.picked === line.quantity ? 'picked' : '';
    if (previous.has(line.sku) && previous.get(line.sku) !== item.className) item.classList.add('line-updated');
    const check = document.createElement('input');check.type = 'checkbox';check.disabled = true;check.checked = line.picked === line.quantity;check.setAttribute('aria-label', `${line.subcategory} recogido`);
    const text = document.createElement('span');text.textContent = `${line.name || line.subcategory} · ${line.sku}`;
    const detail = document.createElement('small');detail.textContent = `${line.level} · ${line.height_m?.toFixed(2) || '?'} m · Solicitadas ${line.quantity} · Recogidas ${line.picked} · Entregadas ${line.delivered}${line.pending_return ? ` · Devolución pendiente ${line.pending_return}` : ''}`;
    text.append(detail);item.append(check, text);list.append(item);
  }
  container.append(list);
  const total = document.createElement('p');total.dataset.orderTotal = '';total.textContent = `Total: ${order.lines.reduce((n, l) => n + l.quantity, 0)} unidades · Capacidad ${state.capacity}`;container.append(total);
  const status = document.createElement('p');status.className = 'order-confirmation';status.textContent = order.state === 'DELIVERED' ? '✓ Entrega confirmada' : ['FAILED', 'CANCELLED'].includes(order.state) ? `${order.state} · Revisa carga pendiente de devolución` : '✧ Entrega pendiente';container.append(status);
}

export function renderRack(container, state, rack) {
  container.replaceChildren();
  const products = state.inventory?.products.filter(p => p.rack === rack) || [];
  const heading = document.createElement('h3');heading.textContent = `${rack} · ${products[0]?.category || ''}`;container.append(heading);
  for (const p of products) {
    const line = document.createElement('p');line.textContent = `${p.level} · ${p.name || p.subcategory} · ${p.height_m?.toFixed(2) || '?'} m`;
    const detail = document.createElement('small');detail.textContent = `${p.sku}${p.temporary ? " (temporal)" : ""} · Total ${p.stock_total} · Reservado ${p.stock_reserved} · Disponible ${p.stock_available}`;line.append(detail);container.append(line);
  }
}
