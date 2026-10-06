// Descarga precios diarios reales (Yahoo Finance, ~10 años) y los deja en datos/precios.js
// para que la oficina los use en vez del mercado simulado. Requiere Node 18 o superior.
//   node descargar.js
const fs = require('fs'), path = require('path');
const { UNIVERSO } = require('./engine.js');

async function bajar(sim) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sim)}?range=10y&interval=1d`;
  const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
  if (!r.ok) throw new Error(`${sim}: HTTP ${r.status}`);
  const j = await r.json(), x = j.chart.result[0], q = x.indicators.quote[0], out = {};
  x.timestamp.forEach((ts, i) => {
    if ([q.open[i], q.high[i], q.low[i], q.close[i]].some(v => v == null)) return;
    out[new Date(ts * 1000).toISOString().slice(0, 10)] = { o: q.open[i], h: q.high[i], l: q.low[i], c: q.close[i] };
  });
  return out;
}

(async () => {
  const brutos = {};
  for (const u of UNIVERSO) {
    try { brutos[u.s] = await bajar(u.yahoo); console.log('ok', u.s, Object.keys(brutos[u.s]).length, 'sesiones'); }
    catch (e) { console.log('sin datos', u.s, e.message); }
  }
  if (!brutos.SPY) throw new Error('Hace falta SPY como referencia de fechas.');
  // empezamos el día en que ya cotizan todos los activos (VWCE desde 2019)
  const inicio = Object.values(brutos).map(b => Object.keys(b).sort()[0]).sort().pop();
  const fechas = Object.keys(brutos.SPY).sort().filter(f => f >= inicio);
  const series = {};
  for (const s in brutos) {
    const o = [], h = [], l = [], c = []; let ult = null;
    for (const f of fechas) {
      const b = brutos[s][f] || (ult && { o: ult.c, h: ult.c, l: ult.c, c: ult.c }); // rellena huecos con el último cierre
      ult = b; o.push(b.o); h.push(b.h); l.push(b.l); c.push(b.c);
    }
    series[s] = { o, h, l, c };
  }
  const datos = { fechas, series };
  fs.mkdirSync(path.join(__dirname, 'datos'), { recursive: true });
  fs.writeFileSync(path.join(__dirname, 'datos', 'precios.json'), JSON.stringify(datos));
  fs.writeFileSync(path.join(__dirname, 'datos', 'precios.js'), 'window.DATOS_REALES = ' + JSON.stringify(datos) + ';\n');
  console.log(`Listo: ${fechas.length} sesiones (${fechas[0]} a ${fechas[fechas.length - 1]}), activos: ${Object.keys(series).join(', ')}`);
})().catch(e => { console.error('Error:', e.message); process.exit(1); });
