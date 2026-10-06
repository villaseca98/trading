/*
 * Oficina de trading automatizada · motor
 * Un fondo simulado (paper trading) donde cada bot tiene un papel:
 *   traders (estrategias conocidas), incubadora, minería de estrategias,
 *   riesgos, macro, coberturas, comité y kill switch.
 * Funciona igual en el navegador (window.Oficina) y en Node (require).
 * No envía órdenes reales a ningún bróker.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Oficina = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ───────────────────────── utilidades ─────────────────────────
  function crearAzar(semilla) {
    let a = semilla >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function normal(r) { let u = 0, v = 0; while (!u) u = r(); while (!v) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  const limitar = (x, a, b) => Math.max(a, Math.min(b, x));
  const entero = (r, a, b) => a + Math.floor(r() * (b - a + 1));
  const real = (r, a, b, dec = 2) => +(a + r() * (b - a)).toFixed(dec);
  const elegir = (r, arr) => arr[Math.floor(r() * arr.length)];
  const signo = x => (x > 1e-9 ? 1 : x < -1e-9 ? -1 : 0);
  const pct = (x, d = 1) => (x >= 0 ? '+' : '') + (x * 100).toFixed(d).replace('.', ',') + ' %';

  // ───────────────────────── universo ─────────────────────────
  const UNIVERSO = [
    { s: 'SPY', nombre: 'S&P 500', clase: 'acciones', p0: 420, mu: 0.08, sig: 0.03, beta: 1.0, yahoo: 'SPY' },
    { s: 'QQQ', nombre: 'Nasdaq 100', clase: 'acciones', p0: 350, mu: 0.10, sig: 0.10, beta: 1.25, yahoo: 'QQQ' },
    { s: 'IWM', nombre: 'Russell 2000', clase: 'acciones', p0: 185, mu: 0.05, sig: 0.12, beta: 1.15, yahoo: 'IWM' },
    { s: 'VWCE', nombre: 'FTSE All-World', clase: 'acciones', p0: 100, mu: 0.07, sig: 0.05, beta: 0.85, yahoo: 'VWCE.DE' },
    { s: 'GLD', nombre: 'Oro', clase: 'materias', p0: 180, mu: 0.05, sig: 0.14, beta: 0.05, yahoo: 'GLD' },
    { s: 'SLV', nombre: 'Plata', clase: 'materias', p0: 22, par: { con: 'GLD', b: 1.3, theta: 0.035, sig: 0.16 }, yahoo: 'SLV' },
    { s: 'TLT', nombre: 'Bonos EE. UU. 20 años', clase: 'bonos', p0: 95, mu: 0.02, sig: 0.12, beta: -0.25, yahoo: 'TLT' },
    { s: 'USO', nombre: 'Petróleo', clase: 'materias', p0: 70, mu: 0.02, sig: 0.30, beta: 0.45, yahoo: 'USO' },
    { s: 'EURUSD', nombre: 'Euro / dólar', clase: 'divisas', p0: 1.08, mu: 0.0, sig: 0.07, beta: 0.05, yahoo: 'EURUSD=X' },
    { s: 'BTC', nombre: 'Bitcoin', clase: 'cripto', p0: 45000, mu: 0.30, sig: 0.50, beta: 0.6, yahoo: 'BTC-USD' },
    { s: 'ETH', nombre: 'Ethereum', clase: 'cripto', p0: 2500, par: { con: 'BTC', b: 1.15, theta: 0.03, sig: 0.30 }, yahoo: 'ETH-USD' },
  ];
  const PARES = [['GLD', 'SLV'], ['BTC', 'ETH'], ['SPY', 'QQQ'], ['SPY', 'IWM'], ['SPY', 'VWCE']];
  const ACCIONES = ['SPY', 'QQQ', 'IWM', 'VWCE'];

  // ───────────────────────── mercado ─────────────────────────
  class Mercado {
    constructor(simbolos) {
      this.simbolos = simbolos.slice();
      this.s = {};
      for (const s of simbolos) this.s[s] = { o: [], h: [], l: [], c: [], cum: [0], cum2: [0] };
      this.fechas = [];
      this.generador = null;
      this.memo = new Map();
      this.real = false;
    }
    get n() { return this.fechas.length; }
    meter(fecha, barras) {
      this.fechas.push(fecha);
      for (const s of this.simbolos) {
        const d = this.s[s], b = barras[s];
        d.o.push(b.o); d.h.push(b.h); d.l.push(b.l); d.c.push(b.c);
        d.cum.push(d.cum[d.cum.length - 1] + b.c);
        d.cum2.push(d.cum2[d.cum2.length - 1] + b.c * b.c);
      }
    }
    asegurar(t) {
      while (this.n <= t) { if (!this.generador) return false; this.generador.siguiente(this); }
      return true;
    }
    c(s, t) { return this.s[s].c[t]; }
    o(s, t) { return this.s[s].o[t]; }
    sma(s, t, n) { if (t - n + 1 < 0) return NaN; const d = this.s[s]; return (d.cum[t + 1] - d.cum[t + 1 - n]) / n; }
    desv(s, t, n) {
      if (t - n + 1 < 0) return NaN; const d = this.s[s];
      const m = (d.cum[t + 1] - d.cum[t + 1 - n]) / n;
      const v = (d.cum2[t + 1] - d.cum2[t + 1 - n]) / n - m * m;
      return Math.sqrt(Math.max(v, 0));
    }
    rsi(s, t, n) {
      if (t < n) return 50; const c = this.s[s].c; let g = 0, p = 0;
      for (let i = t - n + 1; i <= t; i++) { const d = c[i] - c[i - 1]; if (d > 0) g += d; else p -= d; }
      if (p === 0) return 100; if (g === 0) return 0; return 100 - 100 / (1 + g / p);
    }
    vol(s, t, n = 20) {
      const k = s + '|' + t + '|' + n; if (this.memo.has(k)) return this.memo.get(k);
      if (this.memo.size > 20000) this.memo.clear();
      if (t < n) return NaN; const c = this.s[s].c; let a = 0, b = 0;
      for (let i = t - n + 1; i <= t; i++) { const r = Math.log(c[i] / c[i - 1]); a += r; b += r * r; }
      const v = Math.sqrt(Math.max((b - a * a / n) / (n - 1), 1e-10) * 252);
      this.memo.set(k, v); return v;
    }
    atr(s, t, n) {
      if (t < n) return NaN; const d = this.s[s]; let a = 0;
      for (let i = t - n + 1; i <= t; i++) a += Math.max(d.h[i] - d.l[i], Math.abs(d.h[i] - d.c[i - 1]), Math.abs(d.l[i] - d.c[i - 1]));
      return a / n;
    }
    maxH(s, a, b) { const h = this.s[s].h; let m = -Infinity; for (let i = Math.max(0, a); i <= b; i++) m = Math.max(m, h[i]); return m; }
    minL(s, a, b) { const l = this.s[s].l; let m = Infinity; for (let i = Math.max(0, a); i <= b; i++) m = Math.min(m, l[i]); return m; }
  }

  // Mercado simulado: regímenes (alcista, lateral, bajista, crisis), volatilidad
  // que se agrupa, pares cointegrados (oro/plata, BTC/ETH) y algo de reversión diaria.
  class GeneradorSintetico {
    constructor(semilla, fechaFin, calentamiento) {
      this.r = crearAzar(semilla);
      this.regimen = 'alcista';
      this.vm = 1; this.ultimoMkt = 0;
      this.spread = {};
      this.k = {};
      // fechas hábiles: las primeras `calentamiento` acaban en fechaFin
      const d = new Date(fechaFin + 'T12:00:00Z'); let n = 0;
      while (n < calentamiento) { d.setUTCDate(d.getUTCDate() - 1); if (d.getUTCDay() % 6 !== 0) n++; }
      this.fecha = d;
    }
    static REG = {
      alcista: { mu: 0.16, vol: 0.12, quedar: 0.992, sig: ['lateral', 'bajista'] },
      lateral: { mu: 0.0, vol: 0.15, quedar: 0.985, sig: ['alcista', 'alcista', 'bajista'] },
      bajista: { mu: -0.22, vol: 0.26, quedar: 0.98, sig: ['lateral', 'crisis', 'alcista'] },
      crisis: { mu: -0.7, vol: 0.5, quedar: 0.94, sig: ['bajista', 'lateral'] },
    };
    siguiente(m) {
      const r = this.r;
      do { this.fecha.setUTCDate(this.fecha.getUTCDate() + 1); } while (this.fecha.getUTCDay() % 6 === 0);
      const R = GeneradorSintetico.REG[this.regimen];
      if (r() > R.quedar) this.regimen = elegir(r, R.sig);
      const z = normal(r);
      this.vm = Math.sqrt(0.94 * this.vm * this.vm + 0.06 * z * z);
      const mkt = R.mu / 252 + (R.vol / Math.sqrt(252)) * this.vm * z - 0.06 * this.ultimoMkt;
      this.ultimoMkt = mkt;
      const barras = {}, t = m.n;
      for (const a of UNIVERSO) {
        if (!m.s[a.s]) continue;
        const prev = t > 0 ? m.c(a.s, t - 1) : a.p0;
        let lr;
        if (a.par) {
          const base = barras[a.par.con];
          const lA = Math.log(base.c);
          if (this.k[a.s] === undefined) { this.k[a.s] = Math.log(a.p0) - a.par.b * lA; this.spread[a.s] = 0; }
          const s0 = this.spread[a.s];
          const s1 = s0 * (1 - a.par.theta) + (a.par.sig / Math.sqrt(252)) * normal(r);
          this.spread[a.s] = s1;
          lr = this.k[a.s] + a.par.b * lA + s1 - Math.log(prev);
        } else {
          lr = (a.mu - 0.5 * a.sig * a.sig) / 252 + a.beta * mkt + (a.sig / Math.sqrt(252)) * Math.sqrt(this.vm) * normal(r);
        }
        const c = prev * Math.exp(lr);
        const sd = Math.abs(lr) + 0.006 * this.vm;
        const o = prev * Math.exp(lr * r() * 0.35 + 0.001 * normal(r));
        const h = Math.max(o, c) * Math.exp(Math.abs(normal(r)) * sd * 0.45);
        const l = Math.min(o, c) * Math.exp(-Math.abs(normal(r)) * sd * 0.45);
        barras[a.s] = { o, h, l, c };
      }
      m.meter(this.fecha.toISOString().slice(0, 10), barras);
    }
  }

  function mercadoSintetico(semilla, fechaHoy, calentamiento) {
    const m = new Mercado(UNIVERSO.map(u => u.s));
    m.generador = new GeneradorSintetico(semilla, fechaHoy, calentamiento);
    for (let i = 0; i < calentamiento; i++) m.generador.siguiente(m);
    return m;
  }

  // datos = { fechas:[...], series:{ SPY:{o:[],h:[],l:[],c:[]}, ... } } ya alineados
  function mercadoReal(datos) {
    const sims = Object.keys(datos.series).filter(s => datos.series[s].c.length === datos.fechas.length);
    const m = new Mercado(sims); m.real = true;
    for (let i = 0; i < datos.fechas.length; i++) {
      const b = {};
      for (const s of sims) { const x = datos.series[s]; b[s] = { o: x.o[i], h: x.h[i], l: x.l[i], c: x.c[i] }; }
      m.meter(datos.fechas[i], b);
    }
    return m;
  }

  // ───────────────────────── estrategias ─────────────────────────
  // senal(m, t, sims, p, st) devuelve el peso deseado (-1..1) del símbolo, o un mapa {símbolo: peso}.
  // st es la memoria del bot; st.por guarda el motivo de la última decisión.
  const E = {};
  E.cruce = {
    nombre: 'Cruce de medias', escuela: 'Tendencia', autor: 'Golden cross',
    desc: 'Compra cuando la media rápida está por encima de la lenta; vende al cruzar a la baja.',
    defecto: { rapida: 50, lenta: 200, cortos: false },
    azar: r => { const f = entero(r, 5, 60); return { rapida: f, lenta: entero(r, Math.max(f * 2, 40), 250), cortos: r() < 0.25 }; },
    codigo: p => `MA${p.rapida}/${p.lenta}`,
    senal(m, t, [s], p, st) {
      const f = m.sma(s, t, p.rapida), l = m.sma(s, t, p.lenta); if (isNaN(l)) return 0;
      st.por = f > l ? `MA${p.rapida} > MA${p.lenta}` : `MA${p.rapida} < MA${p.lenta}`;
      return f > l ? 1 : p.cortos ? -1 : 0;
    },
  };
  E.faber = {
    nombre: 'Filtro de 200 sesiones', escuela: 'Tendencia', autor: 'Faber',
    desc: 'Invertido solo mientras el precio está por encima de su media larga. Fuera en tendencias bajistas.',
    defecto: { n: 200 },
    azar: r => ({ n: entero(r, 80, 250) }),
    codigo: p => `SMA${p.n}`,
    senal(m, t, [s], p, st) {
      const a = m.sma(s, t, p.n); if (isNaN(a)) return 0;
      st.por = m.c(s, t) > a ? `precio > media ${p.n}` : `precio < media ${p.n}`;
      return m.c(s, t) > a ? 1 : 0;
    },
  };
  E.rsi2 = {
    nombre: 'RSI-2', escuela: 'Reversión a la media', autor: 'Connors',
    desc: 'Compra caídas fuertes de 1-3 días (RSI muy bajo) dentro de una tendencia alcista y vende al rebote.',
    defecto: { n: 2, umbral: 10, salida: 5 },
    azar: r => ({ n: entero(r, 2, 4), umbral: entero(r, 4, 20), salida: entero(r, 3, 10) }),
    codigo: p => `RSI${p.n}<${p.umbral}`,
    senal(m, t, [s], p, st) {
      const c = m.c(s, t), f = m.sma(s, t, 200); if (isNaN(f)) return 0;
      if (st.dentro) { if (c > m.sma(s, t, p.salida)) { st.dentro = false; st.por = `cierre sobre MA${p.salida}`; } }
      else { const x = m.rsi(s, t, p.n); if (x < p.umbral && c > f) { st.dentro = true; st.por = `RSI${p.n} = ${x.toFixed(0)}`; } }
      return st.dentro ? 1 : 0;
    },
  };
  E.bollinger = {
    nombre: 'Bandas de Bollinger', escuela: 'Reversión a la media', autor: 'Bollinger',
    desc: 'Compra al perforar la banda inferior y cierra al volver a la media. Con cortos, al revés en la superior.',
    defecto: { n: 20, k: 2, cortos: false },
    azar: r => ({ n: entero(r, 10, 40), k: real(r, 1.5, 2.6, 1), cortos: r() < 0.35 }),
    codigo: p => `BB${p.n}x${String(p.k).replace('.', ',')}`,
    senal(m, t, [s], p, st) {
      const mid = m.sma(s, t, p.n), sd = m.desv(s, t, p.n), c = m.c(s, t); if (isNaN(mid)) return 0;
      if (st.lado === 1 && c >= mid) { st.lado = 0; st.por = 'vuelta a la media'; }
      if (st.lado === -1 && c <= mid) { st.lado = 0; st.por = 'vuelta a la media'; }
      if (!st.lado && c < mid - p.k * sd) { st.lado = 1; st.por = 'bajo la banda inferior'; }
      if (!st.lado && p.cortos && c > mid + p.k * sd) { st.lado = -1; st.por = 'sobre la banda superior'; }
      return st.lado || 0;
    },
  };
  E.donchian = {
    nombre: 'Canal Donchian', escuela: 'Ruptura', autor: 'Tortugas',
    desc: 'Entra cuando el precio rompe el máximo de N sesiones y sale al perder el mínimo de M sesiones.',
    defecto: { n: 20, salida: 10, cortos: true },
    azar: r => ({ n: entero(r, 15, 60), salida: entero(r, 5, 25), cortos: r() < 0.5 }),
    codigo: p => `DC${p.n}/${p.salida}`,
    senal(m, t, [s], p, st) {
      if (t < p.n + 1) return 0; const c = m.c(s, t);
      if (st.lado === 1 && c < m.minL(s, t - p.salida, t - 1)) { st.lado = 0; st.por = `pierde mínimo ${p.salida}`; }
      if (st.lado === -1 && c > m.maxH(s, t - p.salida, t - 1)) { st.lado = 0; st.por = `supera máximo ${p.salida}`; }
      if (!st.lado && c > m.maxH(s, t - p.n, t - 1)) { st.lado = 1; st.por = `rompe máximo de ${p.n}`; }
      else if (!st.lado && p.cortos && c < m.minL(s, t - p.n, t - 1)) { st.lado = -1; st.por = `rompe mínimo de ${p.n}`; }
      return st.lado || 0;
    },
  };
  E.momentum = {
    nombre: 'Momentum', escuela: 'Tendencia', autor: 'Moskowitz',
    desc: 'Si el activo ha subido en los últimos N días, se compra; si ha bajado, fuera (o corto).',
    defecto: { n: 126, cortos: false },
    azar: r => ({ n: entero(r, 30, 252), cortos: r() < 0.3 }),
    codigo: p => `MOM${p.n}`,
    senal(m, t, [s], p, st) {
      if (t < p.n) return 0; const roc = m.c(s, t) / m.c(s, t - p.n) - 1;
      st.por = `rentab. ${p.n} días ${pct(roc, 0)}`;
      return roc > 0 ? 1 : p.cortos ? -1 : 0;
    },
  };
  E.macd = {
    nombre: 'MACD', escuela: 'Tendencia', autor: 'Appel',
    desc: 'Comprado mientras la línea MACD está por encima de su señal.',
    defecto: { rapida: 12, lenta: 26, senal: 9, cortos: false },
    azar: r => ({ rapida: entero(r, 6, 16), lenta: entero(r, 20, 40), senal: entero(r, 5, 12), cortos: r() < 0.3 }),
    codigo: p => `MACD${p.rapida}/${p.lenta}`,
    senal(m, t, [s], p, st) {
      const c = m.c(s, t), ka = 2 / (p.rapida + 1), kb = 2 / (p.lenta + 1), ks = 2 / (p.senal + 1);
      if (st.t !== t - 1) { st.a = m.sma(s, t, p.rapida); st.b = m.sma(s, t, p.lenta); st.sg = 0; st.n = 0; }
      else { st.a += ka * (c - st.a); st.b += kb * (c - st.b); }
      st.t = t; if (isNaN(st.b)) return 0;
      const macd = st.a - st.b; st.sg += ks * (macd - st.sg); st.n++;
      if (st.n < p.senal) return 0;
      st.por = macd > st.sg ? 'MACD sobre su señal' : 'MACD bajo su señal';
      return macd > st.sg ? 1 : p.cortos ? -1 : 0;
    },
  };
  E.ibs = {
    nombre: 'IBS', escuela: 'Reversión a la media', autor: 'Pagonidis',
    desc: 'Compra cuando la vela cierra en la parte baja de su rango (IBS bajo) y sale cuando cierra arriba.',
    defecto: { umbral: 0.2, dias: 5 },
    azar: r => ({ umbral: real(r, 0.08, 0.3, 2), dias: entero(r, 2, 8) }),
    codigo: p => `IBS<${String(p.umbral).replace('.', ',')}`,
    senal(m, t, [s], p, st) {
      const d = m.s[s], rango = d.h[t] - d.l[t]; if (rango <= 0 || t < 200) return st.dentro ? 1 : 0;
      const ibs = (d.c[t] - d.l[t]) / rango;
      if (st.dentro) { st.dias++; if (ibs > 0.75 || st.dias >= p.dias) { st.dentro = false; st.por = `IBS ${ibs.toFixed(2)}`; } }
      else if (ibs < p.umbral && d.c[t] > m.sma(s, t, 200)) { st.dentro = true; st.dias = 0; st.por = `IBS ${ibs.toFixed(2)}`; }
      return st.dentro ? 1 : 0;
    },
  };
  E.williams = {
    nombre: 'Ruptura de volatilidad', escuela: 'Ruptura', autor: 'L. Williams',
    desc: 'Compra si el día sube más de k veces el rango medio (ATR) y mantiene unas sesiones.',
    defecto: { k: 1, n: 10, dias: 4 },
    azar: r => ({ k: real(r, 0.5, 1.6, 1), n: entero(r, 5, 20), dias: entero(r, 2, 10) }),
    codigo: p => `VB${String(p.k).replace('.', ',')}x${p.n}`,
    senal(m, t, [s], p, st) {
      if (t < p.n + 1) return 0;
      if (st.dentro) { st.dias++; if (st.dias >= p.dias) { st.dentro = false; st.por = `${p.dias} sesiones cumplidas`; } }
      else { const a = m.atr(s, t - 1, p.n); if (m.c(s, t) - m.c(s, t - 1) > p.k * a) { st.dentro = true; st.dias = 0; st.por = `subida > ${String(p.k).replace('.', ',')} ATR`; } }
      return st.dentro ? 1 : 0;
    },
  };
  E.pares = {
    nombre: 'Pares', escuela: 'Arbitraje estadístico', autor: 'Gatev',
    desc: 'Dos activos que suelen moverse juntos: si se separan demasiado, compra el barato y vende el caro hasta que se juntan.',
    defecto: { n: 60, entrada: 2, salida: 0.3 },
    azar: r => ({ n: entero(r, 30, 120), entrada: real(r, 1.5, 2.6, 1), salida: real(r, 0, 0.6, 1) }),
    codigo: p => `Z${p.n}±${String(p.entrada).replace('.', ',')}`,
    senal(m, t, [a, b], p, st) {
      if (t < p.n) return {}; let s1 = 0, s2 = 0, x = 0;
      for (let i = t - p.n + 1; i <= t; i++) { x = Math.log(m.c(a, i) / m.c(b, i)); s1 += x; s2 += x * x; }
      const mu = s1 / p.n, sd = Math.sqrt(Math.max(s2 / p.n - mu * mu, 1e-12)), z = (x - mu) / sd;
      if (st.lado && Math.abs(z) < p.salida) { st.lado = 0; st.por = `z = ${z.toFixed(1)}, se juntan`; }
      if (!st.lado && z > p.entrada) { st.lado = -1; st.por = `z = ${z.toFixed(1)}: ${a} caro`; }
      if (!st.lado && z < -p.entrada) { st.lado = 1; st.por = `z = ${z.toFixed(1)}: ${a} barato`; }
      const l = st.lado || 0; return { [a]: 0.5 * l, [b]: -0.5 * l };
    },
  };
  E.cobertura = {
    nombre: 'Cobertura del fondo', escuela: 'Coberturas', autor: 'Mesa de coberturas',
    desc: 'Cuando el régimen se vuelve bajista, vende en corto índice para proteger la exposición del fondo a bolsa.',
    defecto: { proporcion: 0.5 }, azar: () => ({ proporcion: 0.5 }), codigo: p => `HEDGE${Math.round(p.proporcion * 100)}`,
    senal() { return 0; }, // la calcula el fondo, que conoce la exposición total
  };
  const MINABLES = ['cruce', 'faber', 'rsi2', 'bollinger', 'donchian', 'momentum', 'macd', 'ibs', 'williams', 'pares'];

  // Backtest rápido (cierre a cierre, con coste y tamaño por volatilidad)
  function backtest(m, est, sims, p, a, b, coste = 0.0008, volObj = 0.15) {
    const st = {}, rets = []; let wPrev = {}, eq = 1, pico = 1, dd = 0, trades = 0, gan = 0, ladoPrev = 0, eqEntrada = 1;
    for (let t = a; t < b; t++) {
      let w = E[est].senal(m, t, sims, p, st); if (typeof w === 'number') w = { [sims[0]]: w };
      let r = 0, cost = 0;
      for (const s of sims) {
        const v = m.vol(s, t, 20) || 0.2, k = limitar(volObj / v, 0.2, 2);
        const wi = (w[s] || 0) * k;
        r += wi * (m.c(s, t + 1) / m.c(s, t) - 1);
        cost += Math.abs(wi - (wPrev[s] || 0)) * coste; wPrev[s] = wi;
      }
      const lado = signo(w[sims[0]] || 0);
      if (lado !== ladoPrev) {
        if (ladoPrev !== 0) { trades++; if (eq > eqEntrada) gan++; }
        if (lado !== 0) eqEntrada = eq;
        ladoPrev = lado;
      }
      eq *= 1 + r - cost; rets.push(r - cost); pico = Math.max(pico, eq); dd = Math.max(dd, 1 - eq / pico);
    }
    const n = rets.length || 1, mu = rets.reduce((x, y) => x + y, 0) / n;
    const sd = Math.sqrt(rets.reduce((x, y) => x + (y - mu) ** 2, 0) / n) || 1e-9;
    return { sharpe: (mu / sd) * Math.sqrt(252), ret: eq - 1, maxdd: dd, trades, acierto: trades ? gan / trades : 0 };
  }

  // ───────────────────────── nombres ─────────────────────────
  const APODOS = ['Lucía', 'Marco', 'Vega', 'Toro', 'Nora', 'Iker', 'Sira', 'Bruno', 'Alma', 'Teo', 'Lola', 'Hugo', 'Nico', 'Olga', 'Dani', 'Rita', 'Pau', 'Inés', 'Gael', 'Mía', 'Leo', 'Abril', 'Unai', 'Carla', 'Ciro', 'Elsa', 'Max', 'Noa', 'Saúl', 'Vera', 'Rubén', 'Ada', 'Jon', 'Gala', 'Óscar', 'Zoe', 'Fede', 'Luz', 'Ramón', 'Ane', 'Tomás', 'Irene', 'Biel', 'Lara', 'Coque', 'Maite', 'Raúl', 'Celia', 'Quique', 'Ona'];

  // ───────────────────────── fondo ─────────────────────────
  const AJUSTES = {
    capital: 100000,       // capital simulado del fondo
    killDD: 0.10,          // caída desde máximos que dispara el kill switch
    maxBruta: 1.5,         // exposición bruta máxima (1,5 = 150 % del patrimonio)
    volObjetivo: 0.15,     // volatilidad anual objetivo por posición
    stopTrade: 0.05,       // pérdida máxima por operación sobre el capital del trader
    enfriamiento: 5,       // sesiones de castigo tras saltar un stop
    maxVivos: 24,          // plazas en la sala de trading
    maxIncubadora: 40,     // plazas en la mesa de pruebas
    asignacion: 0.04,      // capital por trader ascendido (4 % del fondo)
    capitalVirtual: 10000, // capital ficticio de la incubadora
    cadaComite: 21,        // sesiones entre reuniones del comité
    cadaMineria: 5,        // sesiones entre rondas de minería
    comision: 0.0005, deslizamiento: 0.0003,
  };
  const ESCALA_REGIMEN = { 'Alcista tranquilo': 1, 'Alcista volátil': 0.75, 'Lateral': 0.8, 'Bajista tranquilo': 0.6, 'Bajista volátil': 0.4 };

  class Fondo {
    constructor(op = {}) {
      this.aj = Object.assign({}, AJUSTES, op.ajustes || {});
      this.r = crearAzar(op.semilla || 7);
      this.calentamiento = op.calentamiento || 750;
      if (op.datos) {
        this.m = mercadoReal(op.datos);
        this.t = Math.min(this.calentamiento, this.m.n - 2);
        if (op.desde) { const i = this.m.fechas.findIndex(f => f >= op.desde); if (i > 260) this.t = i; }
      } else {
        this.m = mercadoSintetico(op.semilla || 7, op.hoy || new Date().toISOString().slice(0, 10), this.calentamiento);
        this.t = this.m.n - 1;
      }
      this.t0 = this.t;
      this.bench = this.m.simbolos.includes('SPY') ? 'SPY' : this.m.simbolos[0];
      this.reserva = this.aj.capital;
      this.traders = []; this.minadas = []; this.eventos = []; this.informe = []; this.despedidos = 0;
      this.curva = [this.aj.capital]; this.pico = this.aj.capital; this.eqAyer = this.aj.capital;
      this.estado = 'operando'; this.regimen = 'Lateral'; this.escala = 1; this.recorte = 1;
      this.nId = 1; this.usados = new Set();
      this.fundar();
    }
    get fecha() { return this.m.fechas[this.t]; }
    precio(s, t = this.t) { return this.m.c(s, t); }

    // ── creación de bots
    crearTrader(est, sims, p, origen) {
      const libres = APODOS.filter(a => !this.usados.has(a));
      const apodo = libres.length ? elegir(this.r, libres) : elegir(this.r, APODOS) + ' ' + this.nId;
      this.usados.add(apodo);
      const tr = {
        id: this.nId++, apodo, est, sims, p, origen, codigo: `${E[est].codigo(p)} · ${sims.join('/')}`,
        sala: 'pruebas', vivo: false, cash: this.aj.capitalVirtual, pos: {}, st: {}, objetivo: {},
        trade: null, trades: [], curva: [], eqAyer: this.aj.capitalVirtual, base: this.aj.capitalVirtual,
        enfriamiento: 0, nacio: this.t, desdeAscenso: this.t, avisos: 0, por: '', hoy: 0,
      };
      this.traders.push(tr); return tr;
    }
    equity(tr, t = this.t, campo = 'c') {
      let e = tr.cash; for (const s in tr.pos) e += tr.pos[s] * this.m.s[s][campo][t]; return e;
    }
    patrimonio() { let e = this.reserva; for (const tr of this.traders) if (tr.vivo) e += this.equity(tr); return e; }
    salaDe(tr) { return tr.est === 'pares' ? 'arbitraje' : tr.est === 'cobertura' ? 'coberturas' : 'trading'; }

    fundar() {
      const base = [['cruce', ['SPY']], ['faber', ['VWCE']], ['rsi2', ['SPY']], ['bollinger', ['QQQ']], ['donchian', ['GLD']],
        ['momentum', ['QQQ']], ['macd', ['BTC']], ['ibs', ['SPY']], ['williams', ['IWM']], ['pares', ['GLD', 'SLV']],
        ['pares', ['BTC', 'ETH']], ['donchian', ['BTC']], ['momentum', ['TLT']], ['rsi2', ['QQQ']]]
        .filter(([, s]) => s.every(x => this.m.s[x]));
      const cand = base.map(([e, s]) => ({ e, s, p: Object.assign({}, E[e].defecto), bt: backtest(this.m, e, s, E[e].defecto, this.t - 400, this.t) }));
      cand.sort((a, b) => b.bt.sharpe - a.bt.sharpe);
      cand.forEach((c, i) => {
        const tr = this.crearTrader(c.e, c.s, c.p, 'fundador'); tr.bt = c.bt;
        if (i < 6 && c.bt.sharpe > 0) this.ascender(tr, true);
      });
      if (this.m.s.SPY) { const h = this.crearTrader('cobertura', ['SPY'], { proporcion: 0.5 }, 'fundador'); this.ascender(h, true, 0.05); }
      this.minar(300, true);
      this.evento('comite', `Abrimos el fondo con ${this.vivos().length} traders en sala y ${this.incubados().length} en pruebas.`, 'comite');
    }
    vivos() { return this.traders.filter(x => x.vivo); }
    activos() { return this.traders.filter(x => x.sala !== 'fuera' && x.sala !== 'minadas'); }
    incubados() { return this.traders.filter(x => !x.vivo && x.sala === 'pruebas'); }

    evento(quien, texto, tipo = 'info', extra) { this.eventos.push(Object.assign({ t: this.t, fecha: this.fecha, quien, texto, tipo }, extra || {})); }
    sacarEventos() { const e = this.eventos; this.eventos = []; return e; }

    // ── ejecución (Infraestructura). Ejecuta el objetivo de pesos a precios del campo dado.
    ejecutar(tr, campo) {
      const t = this.t, eq = this.equity(tr, t, campo); if (eq <= 0) return;
      const ladoAntes = signo(tr.pos[tr.sims[0]] || 0), eqAntes = eq;
      const sims = new Set([...Object.keys(tr.objetivo), ...Object.keys(tr.pos)]);
      for (const s of sims) {
        const px = this.m.s[s][campo][t], w = tr.objetivo[s] || 0, nocional = w * eq, qObj = nocional / px, q = tr.pos[s] || 0;
        const dif = qObj - q;
        if (Math.abs(dif * px) < 1e-6) continue;
        if (qObj !== 0 && signo(qObj) === signo(q) && Math.abs(dif * px) < 0.15 * Math.abs(nocional)) continue; // evita micro-ajustes
        const desliz = this.aj.deslizamiento * (this.m.s[s] && /BTC|ETH/.test(s) ? 3 : 1);
        const pxEj = px * (1 + Math.sign(dif) * desliz);
        tr.cash -= dif * pxEj + Math.abs(dif * pxEj) * this.aj.comision;
        if (Math.abs(qObj) < 1e-12) delete tr.pos[s]; else tr.pos[s] = qObj;
      }
      const ladoDesp = signo(tr.pos[tr.sims[0]] || 0);
      if (ladoAntes !== ladoDesp) {
        if (ladoAntes !== 0 && tr.trade) this.cerrarTrade(tr, campo);
        if (ladoDesp !== 0) {
          tr.trade = { t, eqIni: eqAntes, lado: ladoDesp };
          if (tr.est !== 'cobertura') {
            const verbo = tr.est === 'pares' ? (ladoDesp > 0 ? `Compro ${tr.sims[0]} y vendo ${tr.sims[1]}` : `Vendo ${tr.sims[0]} y compro ${tr.sims[1]}`) : (ladoDesp > 0 ? `Compro ${tr.sims[0]}` : `Corto en ${tr.sims[0]}`);
            this.evento(tr.id, `${verbo}: ${tr.por || E[tr.est].nombre}.`, 'entrada');
          }
        }
      }
    }
    cerrarTrade(tr, campo = 'c', motivo) {
      const eq = this.equity(tr, this.t, campo), pnl = eq - tr.trade.eqIni, ret = pnl / tr.trade.eqIni;
      tr.trades.push({ ini: tr.trade.t, fin: this.t, pnl, ret, lado: tr.trade.lado });
      if (tr.trades.length > 300) tr.trades.shift();
      tr.trade = null;
      if (tr.est !== 'cobertura') this.evento(tr.id, `${motivo || 'Cierro'} ${tr.sims.join('/')}: ${pct(ret)} (${fmt(pnl)}).`, pnl >= 0 ? 'ganancia' : 'perdida', { pnl });
    }
    liquidar(tr) { tr.objetivo = {}; this.ejecutar(tr, 'c'); }

    // ── un día de mercado
    paso() {
      if (this.estado === 'fin') return false;
      if (!this.m.asegurar(this.t + 1)) { this.estado = 'fin'; this.evento('analista', 'Se acabaron los datos históricos. Fin de la simulación.', 'info'); return false; }
      this.t++;
      const t = this.t, operando = this.estado === 'operando';

      // 1. Infraestructura ejecuta en la apertura las órdenes decididas ayer al cierre
      if (operando) for (const tr of this.activos()) this.ejecutar(tr, 'o');

      // 2. Riesgos: stops por operación
      for (const tr of this.activos()) {
        if (tr.trade && tr.est !== 'cobertura') {
          const eq = this.equity(tr);
          if (eq / tr.trade.eqIni - 1 < -this.aj.stopTrade) {
            this.liquidar(tr); tr.st = {}; tr.enfriamiento = this.aj.enfriamiento;
            this.evento('riesgos', `Stop a ${tr.apodo} en ${tr.sims.join('/')}.`, 'stop');
            this.evento(tr.id, 'Me saltó el stop. Pausa de cinco minutos.', 'stop');
          }
        }
        if (tr.enfriamiento > 0 && --tr.enfriamiento === 0) this.evento(tr.id, 'Listo, otra vez al lío.', 'info');
      }

      // 3. Cuentas del día
      const pat = this.patrimonio();
      this.pico = Math.max(this.pico, pat);
      for (const tr of this.activos()) { const e = this.equity(tr); tr.hoy = e - tr.eqAyer; tr.eqAyer = e; tr.curva.push(e); if (tr.curva.length > 260) tr.curva.shift(); }
      this.hoy = pat - this.eqAyer; this.eqAyer = pat;
      this.curva.push(pat); if (this.curva.length > 2000) this.curva.shift();

      // 4. Kill switch
      const caida = 1 - pat / this.pico;
      if (operando && caida > this.aj.killDD) this.kill(`caída del ${(caida * 100).toFixed(1).replace('.', ',')} % desde máximos`);

      // 5. Macro: régimen de mercado
      this.actualizarRegimen();

      // 6. Señales al cierre (se ejecutan mañana en la apertura)
      if (this.estado === 'operando') this.decidir();

      // 7. Comité, minería e informe
      if ((t - this.t0) % this.aj.cadaComite === 0) this.comite();
      if ((t - this.t0) % this.aj.cadaMineria === 0) this.minar(4);
      if ((t - this.t0) % 5 === 0) this.informeSemanal();
      return true;
    }

    actualizarRegimen() {
      const s = this.bench, t = this.t, m = this.m;
      const alc = m.c(s, t) > m.sma(s, t, 200), v20 = m.vol(s, t, 20), v250 = m.vol(s, t, 250);
      const volatil = v20 > 1.25 * v250;
      const lateral = Math.abs(m.c(s, t) / m.sma(s, t, 200) - 1) < 0.015;
      const reg = lateral ? 'Lateral' : alc ? (volatil ? 'Alcista volátil' : 'Alcista tranquilo') : (volatil ? 'Bajista volátil' : 'Bajista tranquilo');
      if (reg !== this.regimen) {
        this.regimen = reg; this.escala = ESCALA_REGIMEN[reg];
        this.evento('macro', `Cambio de régimen: ${reg.toLowerCase()}. Exposición al ${Math.round(this.escala * 100)} %.`, 'macro');
      }
    }

    decidir() {
      const t = this.t, m = this.m, pat = this.patrimonio();
      let bruta = 0;
      for (const tr of this.activos()) {
        if (tr.est === 'cobertura') continue;
        let w = E[tr.est].senal(m, t, tr.sims, tr.p, tr.st);
        tr.por = tr.st.por || tr.por;
        if (typeof w === 'number') w = { [tr.sims[0]]: w };
        const obj = {};
        for (const s of tr.sims) {
          const k = limitar(this.aj.volObjetivo / (m.vol(s, t, 20) || 0.2), 0.2, 2);
          obj[s] = (w[s] || 0) * k * (tr.vivo ? this.escala : 1);
        }
        if (tr.enfriamiento > 0) for (const s in obj) obj[s] = 0;
        tr.objetivo = obj;
        if (tr.vivo) for (const s in obj) bruta += Math.abs(obj[s]) * this.equity(tr);
      }
      // Riesgos: tope de exposición bruta del fondo
      const lim = this.aj.maxBruta * pat, rec = bruta > lim ? lim / bruta : 1;
      if (rec < 1) for (const tr of this.vivos()) for (const s in tr.objetivo) tr.objetivo[s] *= rec;
      if (Math.abs(rec - this.recorte) > 0.1) {
        this.evento('riesgos', rec < 1 ? `Recorto posiciones al ${Math.round(rec * 100)} %: exposición bruta por encima del ${Math.round(this.aj.maxBruta * 100)} %.` : 'Exposición dentro de límites, sin recortes.', 'riesgo');
        this.recorte = rec;
      }
      // Coberturas: protege la exposición neta a bolsa si el régimen es bajista
      const h = this.traders.find(x => x.est === 'cobertura' && x.vivo);
      if (h) {
        let neta = 0;
        for (const tr of this.vivos()) if (tr !== h) for (const s in tr.objetivo) if (ACCIONES.includes(s)) neta += tr.objetivo[s] * this.equity(tr);
        const bajista = this.regimen.startsWith('Bajista');
        const eqh = this.equity(h), w = bajista && neta > 0 ? -limitar(h.p.proporcion * neta / eqh, 0, 8) : 0;
        const antes = signo(h.objetivo.SPY || 0);
        h.objetivo = { SPY: w };
        if (signo(w) !== antes) this.evento(h.id, w < 0 ? `Cubro el ${Math.round(h.p.proporcion * 100)} % de la bolsa con cortos en SPY.` : 'Quito la cobertura.', 'riesgo');
      }
    }

    kill(motivo) {
      this.estado = 'kill';
      for (const tr of this.traders) if (tr.vivo) this.liquidar(tr);
      this.evento('kill', `¡KILL SWITCH! ${motivo}. Todo a liquidez.`, 'kill');
    }
    reabrir() {
      if (this.estado === 'fin') return;
      this.pico = this.patrimonio(); this.estado = 'operando';
      this.evento('kill', 'Recargado. Reabrimos la sala.', 'info');
    }

    stats(tr) {
      const n = tr.trades.length; let pnl = 0, g = 0, pg = 0, pp = 0, sr = 0;
      for (const x of tr.trades) { pnl += x.pnl; sr += x.ret; if (x.pnl > 0) { g++; pg += x.pnl; } else pp -= x.pnl; }
      const abierto = tr.trade ? this.equity(tr) - tr.trade.eqIni : 0;
      const c = tr.curva; let pico = -Infinity, dd = 0; for (const e of c) { pico = Math.max(pico, e); dd = Math.max(dd, 1 - e / pico); }
      const eq = this.equity(tr);
      return { n, pnl, media: n ? sr / n : 0, acierto: n ? g / n : 0, pf: pp > 0 ? pg / pp : (pg > 0 ? 9.9 : 0), abiertas: tr.trade ? 1 : 0, abierto, resultado: eq - tr.base, ret: eq / tr.base - 1, dd, sharpe: sharpe(c) };
    }

    ascender(tr, directo, frac) {
      const pat = this.patrimonio(), cap = Math.min(this.reserva, pat * (frac || this.aj.asignacion));
      if (cap < pat * 0.01) return false;
      tr.objetivo = {}; tr.pos = {}; tr.trade = null; tr.st = {};
      tr.vivo = true; tr.sala = this.salaDe(tr); tr.cash = cap; tr.base = cap; tr.eqAyer = cap; tr.curva = [cap]; tr.trades = [];
      tr.desdeAscenso = this.t; this.reserva -= cap;
      if (!directo) { this.evento('comite', `Ascendemos a ${tr.apodo} (${tr.codigo}) a la sala con ${fmt(cap)}.`, 'comite'); this.evento(tr.id, '¡Me suben a la sala!', 'ascenso'); }
      return true;
    }
    degradar(tr, despedir) {
      this.liquidar(tr);
      this.reserva += tr.cash; tr.cash = 0; tr.pos = {};
      if (despedir) { tr.sala = 'fuera'; tr.vivo = false; this.despedidos++; this.evento('comite', `${tr.apodo} queda despedido (${tr.codigo}).`, 'comite'); this.evento(tr.id, 'Recojo mis cosas.', 'despido'); }
      else {
        tr.vivo = false; tr.sala = 'pruebas'; tr.cash = this.aj.capitalVirtual; tr.base = tr.cash; tr.eqAyer = tr.cash; tr.curva = [tr.cash]; tr.trades = []; tr.trade = null; tr.st = {}; tr.nacio = this.t; tr.avisos++;
        this.evento('comite', `${tr.apodo} vuelve a la mesa de pruebas.`, 'comite'); this.evento(tr.id, 'Vuelvo a la mesa de pruebas.', 'degradado');
      }
    }

    comite() {
      const t = this.t; let cambios = 0;
      // 1. revisar la sala: quien pierde demasiado baja o se va
      for (const tr of this.vivos()) {
        if (tr.est === 'cobertura' || t - tr.desdeAscenso < 42) continue;
        const s = this.stats(tr);
        if (s.dd > 0.2 || (s.n >= 8 && s.pf < 0.9) || (s.n >= 4 && s.ret < -0.08)) { this.degradar(tr, tr.avisos >= 1); cambios++; }
      }
      // 2. limpiar la incubadora de los que no funcionan fuera de muestra
      for (const tr of this.incubados()) {
        const s = this.stats(tr);
        if (t - tr.nacio >= 126 && (s.ret < 0 || (s.n >= 6 && s.pf < 1))) { tr.sala = 'fuera'; this.despedidos++; this.evento(tr.id, 'No he pasado la prueba. Me voy.', 'despido'); cambios++; }
      }
      // 3. ascender a los mejores de la incubadora
      const plazas = this.aj.maxVivos - this.vivos().length;
      const cand = this.incubados().map(tr => ({ tr, s: this.stats(tr) }))
        .filter(({ tr, s }) => t - tr.nacio >= 42 && s.n >= 4 && s.pf >= 1.3 && s.ret > 0 && s.dd < 0.12)
        .sort((a, b) => b.s.sharpe - a.s.sharpe).slice(0, Math.min(3, Math.max(0, plazas)));
      for (const c of cand) if (this.ascender(c.tr)) cambios++;
      // 4. reasignar capital según la calidad reciente (Sharpe de ~3 meses)
      const pat = this.patrimonio(), base = pat * this.aj.asignacion;
      for (const tr of this.vivos()) {
        if (tr.est === 'cobertura') continue;
        const sc = limitar(sharpe(tr.curva.slice(-63)), -1, 3), obj = base * limitar(1 + 0.3 * sc, 0.5, 2);
        const eq = this.equity(tr); let mov = obj - eq;
        if (mov > 0) mov = Math.min(mov, this.reserva); else mov = Math.max(mov, -Math.max(0, tr.cash));
        if (Math.abs(mov) > base * 0.1) { tr.cash += mov; this.reserva -= mov; tr.base += mov; tr.eqAyer += mov; if (tr.trade) tr.trade.eqIni += mov; tr.curva = tr.curva.map(x => x + mov); }
      }
      this.evento('comite', cambios ? `Reunión del comité: ${cambios} cambio${cambios > 1 ? 's' : ''} de plantilla y capital reasignado.` : 'Reunión del comité: sin cambios de plantilla, capital reasignado.', 'comite');
    }

    minar(intentos, silencio) {
      const t = this.t, r = this.r, desde = Math.max(260, t - 500);
      let halladas = 0;
      for (let i = 0; i < intentos; i++) {
        const est = elegir(r, MINABLES);
        let sims;
        if (est === 'pares') { const par = elegir(r, PARES); if (!par.every(s => this.m.s[s])) continue; sims = par; }
        else sims = [elegir(r, this.m.simbolos)];
        const p = E[est].azar(r);
        const clave = est + sims.join() + JSON.stringify(p);
        if (this.traders.some(x => x.est + x.sims.join() + JSON.stringify(x.p) === clave)) continue;
        const bt = backtest(this.m, est, sims, p, desde, t);
        if (bt.sharpe > 0.7 && bt.trades >= 6 && bt.maxdd < 0.25) {
          this.minadas.push({ est, sims, p, bt, t, codigo: `${E[est].codigo(p)} · ${sims.join('/')}` }); halladas++;
        }
      }
      this.minadas.sort((a, b) => b.bt.sharpe - a.bt.sharpe);
      if (halladas && !silencio) this.evento('mineria', `He minado ${halladas} estrategia${halladas > 1 ? 's' : ''} nueva${halladas > 1 ? 's' : ''}. La mejor: ${this.minadas[0].codigo} (Sharpe ${this.minadas[0].bt.sharpe.toFixed(1).replace('.', ',')} en histórico).`, 'mineria');
      // pasan a la incubadora si hay sitio
      while (this.incubados().length < this.aj.maxIncubadora && this.minadas.length) {
        const x = this.minadas.shift(), tr = this.crearTrader(x.est, x.sims, x.p, 'minada'); tr.bt = x.bt;
        if (!silencio) this.evento(tr.id, `Me siento en la mesa de pruebas con ${tr.codigo}.`, 'info');
      }
      this.minadas = this.minadas.slice(0, 12);
      return halladas;
    }

    informeSemanal() {
      const pat = this.patrimonio(), vivos = this.vivos().map(tr => ({ tr, s: this.stats(tr) })).sort((a, b) => b.s.resultado - a.s.resultado);
      const mejor = vivos[0], peor = vivos[vivos.length - 1];
      const n = Math.min(5, this.curva.length - 1), sem = this.curva[this.curva.length - 1] / this.curva[this.curva.length - 1 - n] - 1;
      const linea = `${this.fecha}: patrimonio ${fmt(pat)} (${pct(sem)} en la semana). Régimen ${this.regimen.toLowerCase()}.` +
        (mejor ? ` Mejor: ${mejor.tr.apodo} ${fmt(mejor.s.resultado, true)}. Peor: ${peor.tr.apodo} ${fmt(peor.s.resultado, true)}.` : '');
      this.informe.unshift(linea); if (this.informe.length > 200) this.informe.pop();
      this.evento('analista', `Informe semanal: ${pct(sem)}.`, 'informe');
    }

    // resumen por grupos para el panel
    grupos() {
      const g = (nombre, lista) => {
        let res = 0, n = 0, sr = 0, gan = 0, ab = 0, abp = 0;
        for (const tr of lista) { const s = this.stats(tr); res += s.resultado; n += s.n; sr += s.media * s.n; gan += s.acierto * s.n; ab += s.abiertas; abp += s.abierto; }
        return { nombre, traders: lista.length, resultado: res, ops: n, media: n ? sr / n : 0, acierto: n ? gan / n : 0, abiertas: ab, abierto: abp };
      };
      return [
        g('Sala de trading', this.vivos().filter(x => x.sala === 'trading')),
        g('Arbitraje y coberturas', this.vivos().filter(x => x.sala !== 'trading')),
        g('Incubadora (virtual)', this.incubados()),
      ];
    }
  }

  function sharpe(curva) {
    if (curva.length < 10) return 0; const r = [];
    for (let i = 1; i < curva.length; i++) r.push(curva[i] / curva[i - 1] - 1);
    const mu = r.reduce((a, b) => a + b, 0) / r.length, sd = Math.sqrt(r.reduce((a, b) => a + (b - mu) ** 2, 0) / r.length);
    return sd > 0 ? (mu / sd) * Math.sqrt(252) : 0;
  }
  function fmt(x, signoSiempre) {
    const s = Math.round(Math.abs(x)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return (x < 0 ? '−' : signoSiempre ? '+' : '') + s + ' $';
  }

  return { Fondo, Mercado, ESTRATEGIAS: E, UNIVERSO, AJUSTES, backtest, fmt, pct, sharpe };
});
