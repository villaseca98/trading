"""
Plan de acumulación (DCA inteligente). Nunca vende: solo compra y acumula.

  - Cartera objetivo fija (CARTERA): ETF índice, acciones sólidas, protección y cripto.
  - Compra normal: una vez por semana invierte una parte del efectivo libre en lo que esté
    más por debajo de su peso objetivo.
  - Compra extra en caídas: si un activo cae un 10 % desde su máximo de 1 año, compra un tramo
    extra; si cae un 20 %, dos; si cae un 30 %, tres. Para eso guarda siempre una reserva ("pólvora").
  - Lo que ingreses en la cuenta se reparte solo con estas reglas.

  python dca.py            → una pasada (el Mac la lanza cada día laborable)
  python dca.py --limpiar  → una sola vez: vende y cancela todo lo que no esté en el plan
"""
import json
import math
from datetime import datetime
from pathlib import Path

import config as C
import datos

AQUI = Path(__file__).resolve().parent
ESTADO = AQUI / "estado_dca.json"
OFICINA = AQUI.parent / "datos" / "dca.js"

# símbolo: (peso objetivo, grupo, descripción)
CARTERA = {
    "SPY":   (0.30, "Índices", "S&P 500"),
    "QQQ":   (0.20, "Índices", "Nasdaq-100"),
    "PG":    (0.05, "Sólidas", "Procter & Gamble"),
    "KO":    (0.05, "Sólidas", "Coca-Cola"),
    "JNJ":   (0.05, "Sólidas", "Johnson & Johnson"),
    "MSFT":  (0.05, "Sólidas", "Microsoft"),
    "GLD":   (0.10, "Protección", "Oro"),
    "IBIT":  (0.12, "Riesgo", "Bitcoin (ETF)"),
    "ETHA":  (0.08, "Riesgo", "Ethereum (ETF)"),
}
REPARTO_SEMANAL = 0.25   # cada semana invierte el 25 % del efectivo libre (el resto, poco a poco)
POLVORA = 0.20           # parte del efectivo que solo se usa para comprar caídas
TRAMO_CAIDA = 0.10       # cada tramo extra en una caída = 10 % de la pólvora disponible
CAIDAS = (0.10, 0.20, 0.30)


def plan(valor, efectivo, posiciones, precios, maximos, semana_nueva, ya_tramos):
    """Devuelve (compras, notas, tramos_nuevos). compras = [{simbolo, importe, motivo}]."""
    compras, notas, tramos = [], [], dict(ya_tramos)
    polvora = efectivo * POLVORA
    libre = efectivo - polvora
    # 1. compras extra en caídas (con la pólvora)
    for s, (w, g, d) in CARTERA.items():
        if s not in precios or s not in maximos:
            continue
        caida = 1 - precios[s] / maximos[s]
        nivel = sum(caida >= c for c in CAIDAS)
        if nivel > tramos.get(s, 0):
            importe = min(polvora, TRAMO_CAIDA * efectivo * (nivel - tramos.get(s, 0)))
            if importe >= C.MIN_ORDEN_EUR:
                compras.append({"simbolo": s, "importe": round(importe, 2), "motivo": f"cae un {caida * 100:.0f} % desde su máximo: compra extra"})
                polvora -= importe
                tramos[s] = nivel
        elif nivel < tramos.get(s, 0) and caida < 0.05:
            tramos[s] = 0  # se ha recuperado: se rearman los tramos
    # 2. compra normal semanal hacia los pesos objetivo
    if semana_nueva and libre > C.MIN_ORDEN_EUR:
        presupuesto = libre * REPARTO_SEMANAL if valor - efectivo > 0 else libre  # la primera vez entra con todo lo libre
        valor_inv = {s: posiciones.get(s, 0) * precios.get(s, 0) for s in CARTERA}
        total = sum(valor_inv.values()) + presupuesto
        faltas = {s: max(0.0, w * total - valor_inv[s]) for s, (w, _, _) in CARTERA.items() if s in precios}
        suma = sum(faltas.values())
        for s, f in sorted(faltas.items(), key=lambda x: -x[1]):
            importe = presupuesto * f / suma if suma else 0
            if importe >= C.MIN_ORDEN_EUR:
                compras.append({"simbolo": s, "importe": round(importe, 2), "motivo": "compra periódica hacia su peso objetivo"})
    if not compras:
        notas.append("Hoy no toca comprar: ni es día de compra periódica ni hay caídas nuevas.")
    return compras, notas, tramos


def main():
    from ejecucion import BrokerAlpaca
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    est = json.loads(ESTADO.read_text()) if ESTADO.exists() else {"semana": None, "tramos": {}, "log": [], "historia": []}
    todo = datos.descargar({s: s for s in CARTERA}, años=2)
    precios = {s: float(todo[s].dropna().iloc[-1]) for s in CARTERA if s in todo and todo[s].notna().any()}
    maximos = {s: float(todo[s].dropna().iloc[-252:].max()) for s in precios}
    b = BrokerAlpaca()
    if "--limpiar" in __import__("sys").argv:  # una sola vez: vende lo que no está en el plan
        for o in b.t.get_orders():
            if o.symbol not in CARTERA:
                b.t.cancel_order_by_id(o.id); print(f"Cancelo la orden pendiente de {o.symbol}")
        for p in b.t.get_all_positions():
            if p.symbol not in CARTERA:
                b.t.close_position(p.symbol); print(f"Vendo todo {p.symbol}: no está en el plan")
        return
    cuenta = b.t.get_account()
    valor, efectivo = float(cuenta.equity), float(cuenta.cash)
    posiciones = b.posiciones()
    hoy = datetime.now()
    semana = f"{hoy.isocalendar().year}-{hoy.isocalendar().week}"
    compras, notas, tramos = plan(valor, efectivo, posiciones, precios, maximos, est["semana"] != semana, est["tramos"])
    log = lambda t: (est["log"].append(f"{hoy:%Y-%m-%d %H:%M} {t}"), print(t))
    for c in compras:
        if C.MODO_PRUEBA:
            log(f"[prueba] Compraría {c['importe']} $ de {c['simbolo']}: {c['motivo']}"); continue
        try:
            b.t.submit_order(MarketOrderRequest(symbol=c["simbolo"], notional=c["importe"], side=OrderSide.BUY, time_in_force=TimeInForce.DAY))
            log(f"Compro {c['importe']} $ de {c['simbolo']} ({CARTERA[c['simbolo']][2]}): {c['motivo']}")
        except Exception as e:
            log(f"Error comprando {c['simbolo']}: {e}")
    for n in notas:
        log(n)
    if not C.MODO_PRUEBA:
        est["semana"] = semana
        est["tramos"] = tramos
    est["historia"].append({"fecha": f"{hoy:%Y-%m-%d}", "valor": round(valor, 2)})
    est["historia"] = est["historia"][-500:]; est["log"] = est["log"][-300:]
    ESTADO.write_text(json.dumps(est, indent=2, ensure_ascii=False))
    filas = [{"simbolo": s, "grupo": g, "nombre": d, "objetivo": w, "valor": round(posiciones.get(s, 0) * precios.get(s, 0), 2),
              "caida": round((1 - precios[s] / maximos[s]) * 100, 1) if s in precios else None} for s, (w, g, d) in CARTERA.items()]
    OFICINA.parent.mkdir(exist_ok=True)
    OFICINA.write_text("window.DCA = " + json.dumps({"fecha": f"{hoy:%Y-%m-%d %H:%M}", "valor": valor, "efectivo": efectivo, "filas": filas,
                       "log": est["log"][-40:], "historia": est["historia"], "polvora": POLVORA, "caidas": CAIDAS}, ensure_ascii=False) + ";\n")
    print(f"Listo. Valor {valor:,.2f} $, efectivo {efectivo:,.2f} $.")


if __name__ == "__main__":
    main()
