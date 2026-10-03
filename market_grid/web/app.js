import { drawChart, formatTime } from './charts.js';

const $ = id => document.getElementById(id);
const STORAGE_KEY = 'market-grid-local-preferences-v1';
const state = { config:null, symbols:[], interval:'1d', range:'6mo', auto:true,
  records:new Map(), cards:new Map(), controller:null, generation:0, busy:false, focused:null };
const element = (tag, className, content) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content != null) node.textContent = content;
  return node;
};
const parseSymbols = text => [...new Set(text.toUpperCase().split(/[\s,;]+/).filter(Boolean))];
const numeric = value => value == null ? '—' : new Intl.NumberFormat('en-CA', { maximumFractionDigits:4 }).format(value);

function persist() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ symbols:state.symbols, interval:state.interval, range:state.range, auto:state.auto })); } catch { /* Private browsing may disable storage. */ }
}
function notice(message = '') {
  for (const id of ['notice','focus-notice']) { $(id).textContent = message; $(id).hidden = !message; }
}
function syncControls() {
  const valid = state.config.intervals.find(item => item.value === state.interval);
  if (!valid.ranges.includes(state.range)) state.range = valid.fallback;
  for (const id of ['interval','focus-interval']) $(id).value = state.interval;
  for (const id of ['range','focus-range']) {
    for (const option of $(id).options) option.disabled = !valid.ranges.includes(option.value);
    $(id).value = state.range;
  }
  $('auto').setAttribute('aria-pressed', String(state.auto));
  $('auto').textContent = state.auto ? 'Auto · 5 min' : 'Auto desactivado';
}
function openFocused(symbol) {
  state.focused = symbol;
  renderFocused();
  $('focused').showModal();
  document.body.classList.add('focus-open');
  $('back').focus();
}
function renderFocused() {
  if (!state.focused) return;
  $('focus-title').textContent = state.focused;
  $('focus-card').replaceChildren(makeCard(state.focused, true));
}
function makeCard(symbol, expanded = false) {
  const record = state.records.get(symbol) || {};
  const data = record.data;
  const card = element('article','asset-card');
  const header = element('div','card-header');
  const info = element('div','asset-info');
  const title = element('div','symbol-row');
  title.append(element('h3','symbol',symbol), element('span','exchange',data?.exchange || 'YAHOO FINANCE'));
  info.append(title,element('p','asset-name',data?.longName || 'Velas · Bollinger · RSI'));
  header.append(info);
  if (data) {
    const quote = element('div','quote');
    const close = data.points.at(-1).close, previous = data.previousClose;
    quote.append(element('p','price',`${numeric(close)} ${data.currency}`));
    const difference = previous == null ? null : close - previous;
    quote.append(element('p',`change ${difference >= 0 ? 'up' : 'down'}`, difference == null ? '—'
      : `${difference >= 0 ? '+' : ''}${numeric(difference)} (${previous ? (difference / previous * 100).toFixed(2) : '—'}%)`));
    header.append(quote);
  }
  card.append(header);
  if (data) {
    const chart = element('div');
    drawChart(chart,data,expanded,expanded ? null : () => openFocused(symbol));
    card.append(chart);
    const legend = element('div','legend');
    legend.append(element('span','sma-key','SMA 30'),element('span','bb-key','BB ±2σ'),element('span','rsi-key','RSI 14'));
    const time = element('time',null,formatTime(data.points.at(-1).time,data.interval));
    time.dateTime = new Date(data.points.at(-1).time*1000).toISOString();
    legend.append(time);
    card.append(legend);
    if (record.loading || record.error) card.append(element('div',`update-note${record.error ? ' stale-note' : ''}`,
      record.error ? `${record.error} Se conserva el historial anterior (${data.interval} / ${data.range}).` : `Actualizando… Se conserva ${data.interval} / ${data.range}.`));
  } else {
    const box = element('div',record.error ? 'error-box' : 'loading-box');
    box.append(element('p',record.error ? 'error-message' : null,record.error || 'Consultando historial…'));
    card.append(box);
  }
  if (record.error) {
    const retry = element('button',null,'Reintentar');
    retry.type = 'button'; retry.disabled = state.busy;
    retry.addEventListener('click',() => loadBatch([symbol]));
    if (data) { const footer = element('div','legend'); footer.append(retry); card.append(footer); }
    else card.lastChild.append(retry);
  }
  return card;
}
function renderSymbol(symbol) {
  const card = makeCard(symbol);
  const previous = state.cards.get(symbol);
  if (previous) previous.replaceWith(card);
  else $('grid').append(card);
  state.cards.set(symbol,card);
  if (state.focused === symbol) renderFocused();
}
function syncGrid() {
  state.cards.clear(); $('grid').replaceChildren();
  const keep = new Set(state.symbols);
  for (const symbol of state.records.keys()) if (!keep.has(symbol)) state.records.delete(symbol);
  for (const symbol of state.symbols) renderSymbol(symbol);
  $('asset-count').textContent = `${state.symbols.length} activos · YAHOO FINANCE`;
  if (state.focused && !keep.has(state.focused)) $('focused').close();
}
async function fetchData(symbol, signal) {
  const query = new URLSearchParams({symbol, interval:state.interval, range:state.range});
  const response = await fetch(`/api/market?${query}`,{ signal });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'No se pudo cargar el historial.');
  if (!Array.isArray(data.points) || !data.points.length) throw new Error('No hay velas disponibles.');
  return data;
}
async function loadBatch(targets = state.symbols) {
  state.controller?.abort();
  const controller = new AbortController(); state.controller = controller;
  const generation = ++state.generation;
  if (!targets.length) { notice('Introduce al menos un ticker.'); return; }
  state.busy = true;
  $('load').disabled = $('refresh').disabled = true;
  $('progress').hidden = false; $('progress').value = 0;
  notice(); persist();
  for (const symbol of targets) { state.records.set(symbol,{...state.records.get(symbol), loading:true, error:null}); renderSymbol(symbol); }
  let next = 0, completed = 0;
  const updateProgress = () => { $('progress').value = completed / targets.length * 100; $('status').textContent = `Cargando ${completed}/${targets.length}…`; };
  updateProgress();
  async function worker() {
    while (next < targets.length && generation === state.generation) {
      const symbol = targets[next++];
      try {
        const data = await fetchData(symbol,controller.signal);
        if (generation !== state.generation) return;
        state.records.set(symbol,{data,loading:false,error:null});
      } catch (error) {
        if (generation !== state.generation || error.name === 'AbortError') return;
        state.records.set(symbol,{...state.records.get(symbol),loading:false,error:error.message || 'Error de conexión.'});
      }
      completed++; renderSymbol(symbol); updateProgress();
    }
  }
  await Promise.all(Array.from({length:Math.min(4,targets.length)},worker));
  if (generation !== state.generation) return;
  state.busy = false;
  $('load').disabled = $('refresh').disabled = false; $('progress').hidden = true;
  for (const symbol of state.symbols) {
    const retry = state.cards.get(symbol)?.querySelector('button'); if (retry) retry.disabled = false;
  }
  if (state.focused) renderFocused();
  const failed = state.symbols.filter(symbol => state.records.get(symbol)?.error).length;
  $('status').textContent = `Actualizado ${new Date().toLocaleTimeString('es-CA')}`;
  if (failed) notice(`${failed} activo(s) no pudieron actualizarse. Puedes reintentar en su tarjeta.`);
}
async function initialize() {
  try {
    const response = await fetch('/api/config');
    if (!response.ok) throw new Error('No se pudo cargar la configuración.');
    state.config = await response.json();
    state.symbols = state.config.defaultSymbols;
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (saved && typeof saved === 'object') {
        if (Array.isArray(saved.symbols) && saved.symbols.length && saved.symbols.every(item => typeof item === 'string')) state.symbols = parseSymbols(saved.symbols.join(' '));
        if (state.config.intervals.some(item => item.value === saved.interval)) state.interval = saved.interval;
        if (state.config.ranges.some(item => item.value === saved.range)) state.range = saved.range;
        if (typeof saved.auto === 'boolean') state.auto = saved.auto;
      }
    } catch { /* Corrupt or unavailable preferences do not prevent startup. */ }
    for (const id of ['interval','focus-interval']) for (const item of state.config.intervals) $(id).add(new Option(item.label,item.value));
    for (const id of ['range','focus-range']) for (const item of state.config.ranges) $(id).add(new Option(item.label,item.value));
    $('symbols').value = state.symbols.join(' ');
    syncControls(); syncGrid();
    $('controls').addEventListener('submit',event => {
      event.preventDefault();
      const symbols = parseSymbols($('symbols').value);
      if (!symbols.length) { notice('Introduce al menos un ticker.'); return; }
      state.symbols = symbols; $('symbols').value = symbols.join(' '); syncGrid(); loadBatch();
    });
    for (const id of ['interval','focus-interval','range','focus-range']) $(id).addEventListener('change',event => {
      state[id.includes('interval') ? 'interval' : 'range'] = event.target.value;
      syncControls(); loadBatch();
    });
    $('refresh').addEventListener('click',() => loadBatch());
    $('auto').addEventListener('click',() => { state.auto = !state.auto; syncControls(); persist(); });
    $('back').addEventListener('click',() => $('focused').close());
    $('focused').addEventListener('close',() => {
      const symbol = state.focused; state.focused = null; document.body.classList.remove('focus-open');
      state.cards.get(symbol)?.querySelector('.chart')?.focus({preventScroll:true});
    });
    setInterval(() => { if (state.auto && !state.busy && state.symbols.length) loadBatch(); },state.config.autoRefreshMs);
    await loadBatch();
  } catch (error) {
    $('status').textContent = 'No se pudo iniciar';
    notice(`${error.message} Mantén Python abierto y recarga esta página.`);
  }
}
initialize();
