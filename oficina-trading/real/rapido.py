"""
Mesa rápida: compraventa activa de cripto en Alpaca, cada hora, 24/7.
Cripto porque en Alpaca no tiene la regla de "pattern day trader" (con menos de 25.000 $
solo se permiten 3 operaciones intradía por semana en acciones) y cotiza todo el día.

Reglas (velas de 1 hora):
  Entra  : precio > media 50 h > media 200 h y rompe el máximo de las últimas 24 h.
  Filtro : solo opera un par si las mismas reglas han ganado dinero en sus últimos 90 días.
  Sale   : stop inicial a 2 movimientos medios; toma de beneficio al +3 %;
           o cierre bajo la media de 20 h. El stop sube con el precio, nunca baja.
  Tamaño : arriesga RAPIDO_RIESGO del valor de la cuenta por operación, con tope RAPIDO_TOPE en total.
Alpaca no permite cortos en cripto: cuando baja, la mesa se queda en liquidez.
Solo cuenta Paper salvo SOLO_DEMO = False y el archivo de confirmación (igual que el resto del fondo).

  python rapido.py           → una pasada (el Mac la lanza cada hora)
  python rapido.py --simular → backtest rápido con las velas descargadas, sin operar
"""
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import config as C

AQUI = Path(__file__).resolve().parent
ESTADO = AQUI / "estado_rapido.json"
PARES = ["BTC/USD", "ETH/USD", "SOL/USD"]
P = {"media_l": 200, "media_m": 50, "media_s": 20, "ruptura": 24, "stop_mov": 2.0, "toma": 0.03, "coste": 0.0025}


def velas(par, horas=400):
    from alpaca.data.historical import CryptoHistoricalDataClient
    from alpaca.data.requests import CryptoBarsRequest
    from alpaca.data.timeframe import TimeFrame
    cli = CryptoHistoricalDataClient()
    r = cli.get_crypto_bars(CryptoBarsRequest(symbol_or_symbols=par, timeframe=TimeFrame.Hour,
                                              start=datetime.now(timezone.utc) - timedelta(hours=horas)))
    df = r.df.reset_index()
    return df[df["symbol"] == par].set_index("timestamp")["close"].astype(float)


def senal(c: pd.Series):
    px = c.iloc[-1]
    ml, mm, ms = (c.rolling(P[k]).mean().iloc[-1] for k in ("media_l", "media_m", "media_s"))
    maximo = c.iloc[-P["ruptura"] - 1:-1].max()
    mov = c.diff().abs().rolling(24).mean().iloc[-1]
    return {"px": float(px), "entra": bool(px > mm > ml and px > maximo), "ms": float(ms), "mov": float(mov)}


def simular(c: pd.Series):
    """Backtest simple sobre las velas: devuelve nº operaciones, acierto y resultado acumulado."""
    pos, ops = None, []
    for i in range(P["media_l"] + 1, len(c)):
        s = senal(c.iloc[: i + 1]); px = s["px"]
        if pos:
            pos["stop"] = max(pos["stop"], px - P["stop_mov"] * s["mov"])
            if px <= pos["stop"] or px >= pos["entrada"] * (1 + P["toma"]) or px < s["ms"]:
                ops.append(px / pos["entrada"] - 1 - P["coste"] * 2); pos = None
        elif s["entra"]:
            pos = {"entrada": px, "stop": px - P["stop_mov"] * s["mov"]}
    if not ops:
        return {"operaciones": 0}
    return {"operaciones": len(ops), "acierto_%": round(sum(o > 0 for o in ops) / len(ops) * 100),
            "resultado_%": round((math.prod(1 + o for o in ops) - 1) * 100, 1)}


def main():
    if "--simular" in sys.argv:
        for par in PARES:
            print(par, simular(velas(par, 24 * 120)))
        return
    from ejecucion import BrokerAlpaca
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    est = json.loads(ESTADO.read_text()) if ESTADO.exists() else {"posiciones": {}, "log": []}
    b = BrokerAlpaca()
    valor = b.valor({}); efectivo = float(b.t.get_account().cash)
    reales = b.posiciones()
    log = lambda t: (est["log"].append(f"{datetime.now():%Y-%m-%d %H:%M} {t}"), print(t))
    for par in PARES:
        sim = par.replace("/", "")
        try:
            c = velas(par, 24 * 90)
        except Exception as e:
            log(f"{par}: sin datos ({e})"); continue
        s = senal(c); pos = est["posiciones"].get(par)
        if pos and reales.get(sim, 0) <= 0:
            est["posiciones"].pop(par); pos = None
        if pos:
            pos["stop"] = max(pos["stop"], s["px"] - P["stop_mov"] * s["mov"])
            motivo = "stop" if s["px"] <= pos["stop"] else f"beneficio +{P['toma'] * 100:.0f} %" if s["px"] >= pos["entrada"] * (1 + P["toma"]) else "pierde la media de 20 h" if s["px"] < s["ms"] else None
            if motivo:
                q = reales.get(sim, pos["cantidad"])
                if C.MODO_PRUEBA:
                    log(f"[prueba] Vendería {q} {par}: {motivo}")
                else:
                    b.t.submit_order(MarketOrderRequest(symbol=par, qty=q, side=OrderSide.SELL, time_in_force=TimeInForce.GTC))
                    log(f"Vendo {q} {par} a ~{s['px']:.2f} $: {motivo} ({(s['px'] / pos['entrada'] - 1) * 100:+.1f} %)")
                    est["posiciones"].pop(par)
            continue
        if s["entra"]:
            prueba = simular(c)
            if prueba.get("resultado_%", -1) <= 0:
                log(f"{par} da señal, pero estas reglas no han ganado en los últimos 90 días ({prueba}). No entro."); continue
            usado = sum(p["cantidad"] * p["entrada"] for p in est["posiciones"].values())
            riesgo = P["stop_mov"] * s["mov"]
            importe = min(C.RAPIDO_RIESGO * valor / riesgo * s["px"], C.RAPIDO_TOPE * valor - usado, efectivo * 0.95)
            q = math.floor(importe / s["px"] * 1e6) / 1e6
            if importe < 10 or q <= 0:
                log(f"{par} da señal, pero no queda hueco en el tope de la mesa rápida."); continue
            if C.MODO_PRUEBA:
                log(f"[prueba] Compraría {q} {par} (~{importe:.0f} $)"); continue
            b.t.submit_order(MarketOrderRequest(symbol=par, qty=q, side=OrderSide.BUY, time_in_force=TimeInForce.GTC))
            est["posiciones"][par] = {"cantidad": q, "entrada": s["px"], "stop": s["px"] - riesgo, "fecha": f"{datetime.now():%Y-%m-%d %H:%M}"}
            efectivo -= importe
            log(f"Compro {q} {par} a ~{s['px']:.2f} $ (~{importe:.0f} $), stop {s['px'] - riesgo:.2f} $, objetivo +{P['toma'] * 100:.0f} %")
    est["log"] = est["log"][-300:]
    ESTADO.write_text(json.dumps(est, indent=2))
    datos = AQUI.parent / "datos" / "rapido.js"
    datos.parent.mkdir(exist_ok=True)
    datos.write_text("window.RAPIDO = " + json.dumps({"posiciones": est["posiciones"], "log": est["log"][-40:], "tope": C.RAPIDO_TOPE}) + ";\n")


if __name__ == "__main__":
    main()
