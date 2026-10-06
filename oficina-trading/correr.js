// Ejecuta el fondo sin pantalla y saca un informe. Útil para probar ajustes rápido.
//   node correr.js                 → 3 años de mercado simulado
//   node correr.js --dias 750 --semilla 11
//   node correr.js --reales        → usa datos/precios.json (antes: node descargar.js)
const fs = require('fs'), path = require('path');
const O = require('./engine.js');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const reales = process.argv.includes('--reales');
let op = { semilla: +arg('semilla', 7) };
if (reales) {
  const datos = JSON.parse(fs.readFileSync(path.join(__dirname, 'datos', 'precios.json'), 'utf8'));
  op.datos = datos; op.calentamiento = 300; // empieza tras ~1 año de historia
}
const f = new O.Fondo(op), dias = +arg('dias', 750), ini = f.fecha;
let kills = 0;
for (let i = 0; i < dias; i++) {
  if (!f.paso()) break;
  for (const e of f.sacarEventos()) if (e.tipo === 'kill' && e.quien === 'kill' && e.texto.startsWith('¡KILL')) kills++;
  if (f.estado === 'kill') f.reabrir(); // en modo informe reabrimos al día siguiente
}
const pat = f.patrimonio(), maxdd = (() => { let p = 0, d = 0; for (const e of f.curva) { p = Math.max(p, e); d = Math.max(d, 1 - e / p); } return d; })();
console.log(`\n${reales ? 'DATOS REALES' : 'MERCADO SIMULADO'} · ${ini} → ${f.fecha}`);
console.log(`Patrimonio ${O.fmt(pat)} (${O.pct(pat / f.aj.capital - 1)}) · caída máx. ${(maxdd * 100).toFixed(1)} % · Sharpe ${O.sharpe(f.curva).toFixed(2)} · kill switch ${kills} veces`);
console.log(`En sala: ${f.vivos().length} · en pruebas: ${f.incubados().length} · despedidos: ${f.despedidos}\n`);
const filas = f.vivos().map(tr => ({ tr, s: f.stats(tr) })).sort((a, b) => b.s.resultado - a.s.resultado);
for (const { tr, s } of filas) console.log(`${tr.apodo.padEnd(8)} ${tr.codigo.padEnd(26)} ${O.fmt(s.resultado, true).padStart(10)}  ops ${String(s.n).padStart(3)}  acierto ${String(Math.round(s.acierto * 100)).padStart(3)} %`);
console.log('\nÚltimos informes:\n' + f.informe.slice(0, 5).join('\n'));
