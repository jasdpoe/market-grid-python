const NS = 'http://www.w3.org/2000/svg';
const number = (value) => value == null ? '—' : new Intl.NumberFormat('en-CA', { maximumFractionDigits: 4 }).format(value);

export function compressPoints(points, maximum = 140) {
  if (points.length <= maximum) return points;
  const result = [];
  const size = Math.ceil(points.length / maximum);
  for (let start = 0; start < points.length; start += size) {
    const bucket = points.slice(start, start + size);
    result.push({ ...bucket.at(-1), startTime:bucket[0].time, count:bucket.length, open: bucket[0].open,
      high: Math.max(...bucket.map(p => p.high)), low: Math.min(...bucket.map(p => p.low)),
      volume: bucket.reduce((sum, p) => sum + p.volume, 0) });
  }
  return result;
}

export function formatTime(timestamp, interval) {
  return new Intl.DateTimeFormat('es-CA', interval.endsWith('m') || interval === '1h'
    ? { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }
    : { year: 'numeric', month: 'short', day: '2-digit' }).format(new Date(timestamp * 1000));
}

function svgElement(name, attributes = {}, text = null) {
  const element = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  if (text != null) element.textContent = text;
  return element;
}

export function drawChart(container, payload, expanded, open) {
  const points = compressPoints(payload.points);
  container.className = `chart${open ? ' can-expand' : ''}`;
  container.tabIndex = 0;
  container.setAttribute('role', open ? 'button' : 'img');
  container.setAttribute('aria-label', `${payload.symbol}: velas, Bollinger y RSI.${open ? ' Activar para ampliar.' : ' Enfocar para consultar la última vela.'}`);
  if (!points.length) { container.textContent = 'Sin velas completas.'; return; }
  const width = expanded ? 1200 : 420, height = expanded ? 700 : 250;
  const left = expanded ? 24 : 12, right = width - 14;
  const top = 18, bottom = expanded ? 495 : 162;
  const rsiTop = expanded ? 558 : 190, rsiBottom = height - 21;
  const prices = points.flatMap(p => [p.low, p.high, p.lower ?? p.low, p.upper ?? p.high]);
  const minimum = Math.min(...prices), span = Math.max(Math.max(...prices) - minimum, 0.0001);
  const x = i => left + (i + .5) / points.length * (right - left);
  const y = value => bottom - (value - minimum) / span * (bottom - top);
  const yr = value => rsiBottom - value / 100 * (rsiBottom - rsiTop);
  const chart = svgElement('svg', { viewBox: `0 0 ${width} ${height}`, preserveAspectRatio: 'none', 'aria-hidden': 'true' });
  const add = (name, attrs, text) => { const element = svgElement(name, attrs, text); chart.append(element); return element; };
  for (let tick = 0; tick < 5; tick++) add('line', { x1:left, x2:right, y1:top + tick / 4 * (bottom - top), y2:top + tick / 4 * (bottom - top), class:'chart-grid' });
  for (const value of [30,70]) {
    add('line', { x1:left, x2:right, y1:yr(value), y2:yr(value), class:'rsi-limit' });
    add('text', { x:right-3, y:yr(value)-4, 'text-anchor':'end', class:'axis-label' }, value);
  }
  const coords = field => points.flatMap((p,i) => p[field] == null ? [] : [`${x(i)},${y(p[field])}`]);
  const upper = coords('upper'), lower = coords('lower');
  if (upper.length && lower.length) add('polygon', { points:[...upper,...lower.reverse()].join(' '), class:'band-fill' });
  const bodyWidth = Math.max(1,Math.min(expanded ? 8 : 4,(right-left)/points.length*.62));
  points.forEach((p,i) => {
    const className = p.close >= p.open ? 'up-candle' : 'down-candle';
    add('line', { x1:x(i), x2:x(i), y1:y(p.high), y2:y(p.low), class:className });
    add('rect', { x:x(i)-bodyWidth/2, y:Math.min(y(p.open),y(p.close)), width:bodyWidth, height:Math.max(1,Math.abs(y(p.open)-y(p.close))), rx:.5, class:className });
  });
  for (const field of ['upper','lower','sma']) add('polyline', { points:coords(field).join(' '), class:field === 'sma' ? 'sma' : 'band' });
  add('polyline', { points:points.flatMap((p,i) => p.rsi == null ? [] : [`${x(i)},${yr(p.rsi)}`]).join(' '), class:'rsi' });
  add('text', { x:left+2, y:rsiTop+13, class:'axis-label' }, 'RSI');
  const dateOptions = payload.interval.endsWith('m') || payload.interval === '1h' ? {month:'short',day:'numeric'} : {year:'numeric',month:'short',day:'numeric'};
  add('text', { x:left, y:height-4, class:'axis-label' }, new Date(payload.points[0].time*1000).toLocaleDateString('es-CA', dateOptions));
  add('text', { x:right, y:height-4, 'text-anchor':'end', class:'axis-label' }, new Date(points.at(-1).time*1000).toLocaleDateString('es-CA', dateOptions));
  const crosshair = add('line', { y1:top, y2:rsiBottom, class:'crosshair', visibility:'hidden' });
  const tooltip = document.createElement('div');
  tooltip.className = 'tooltip'; tooltip.hidden = true;
  function show(index) {
    const p = points[index];
    crosshair.setAttribute('x1', x(index)); crosshair.setAttribute('x2', x(index)); crosshair.setAttribute('visibility','visible');
    const period = p.count > 1 ? `${formatTime(p.startTime,payload.interval)} — ${formatTime(p.time,payload.interval)} (${p.count} velas)` : formatTime(p.time,payload.interval);
    tooltip.textContent = `${period}\nO ${number(p.open)}   H ${number(p.high)}\nL ${number(p.low)}   C ${number(p.close)}\nSMA ${number(p.sma)}   RSI ${number(p.rsi)}\nBB+ ${number(p.upper)}   BB− ${number(p.lower)}`;
    tooltip.hidden = false;
  }
  function hide() { crosshair.setAttribute('visibility','hidden'); tooltip.hidden = true; }
  container.append(chart,tooltip);
  container.addEventListener('pointermove', event => {
    const bounds = chart.getBoundingClientRect();
    const position = (event.clientX-bounds.left)/bounds.width*width;
    show(Math.max(0,Math.min(points.length-1,Math.floor((position-left)/(right-left)*points.length))));
  });
  container.addEventListener('pointerleave',hide);
  container.addEventListener('focus',() => show(points.length-1));
  container.addEventListener('blur',hide);
  if (open) {
    const hint = document.createElement('span'); hint.className = 'expand-icon'; hint.setAttribute('aria-hidden','true');
    const icon = svgElement('svg',{viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':2});
    icon.append(svgElement('path',{d:'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5'})); hint.append(icon); container.append(hint);
    container.addEventListener('click',open);
    container.addEventListener('keydown',event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(); } });
  }
}
