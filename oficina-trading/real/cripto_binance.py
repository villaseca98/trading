"""
Cripto automática en Binance: acumulación que nunca vende.

  - Cada semana compra con una parte del saldo en EUR, repartido entre CARTERA según su peso.
  - Si una moneda cae un 15, 30 o 45 % desde su máximo de 1 año, compra extra con la reserva.
  - Comisión de Binance: 0,1 % por compra. Orden mínima: unos 5 €.
Seguridad:
  - Claves en claves_binance.txt (dos líneas: API key y secret). NUNCA en el chat ni en el repo.
  - Al crear la clave en Binance: marca SOLO "Enable Reading" y "Enable Spot Trading".
    Nunca "Enable Withdrawals": así, aunque alguien robara la clave, no podría sacar tu dinero.
  - Con el archivo testnet.txt usa la red de pruebas de Binance (dinero ficticio).
  - Sin el archivo enviar_binance.txt solo dice lo que haría (modo prueba).

  python cripto_binance.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ESTADO = AQUI / "estado_binance.json"
OFICINA = AQUI.parent / "datos" / "binance.js"
CARTERA = {"BTC": 0.60, "ETH": 0.30, "SOL": 0.10}
QUOTE = "EUR"
REPARTO_SEMANAL = 0.25
RESERVA = 0.25
CAIDAS = (0.15, 0.30, 0.45)
TRAMO = 0.10       # cada tramo de caída usa un 10 % del saldo
MINIMO = 6.0       # euros por orden


def conectar():
    import ccxt
    f = AQUI / "claves_binance.txt"
    if not f.exists():
        sys.exit("Falta claves_binance.txt (dos líneas: API key y secret).")
    key, secret = [l.strip() for l in f.read_text().splitlines() if l.strip()][:2]
    ex = ccxt.binance({"apiKey": key, "secret": secret, "enableRateLimit": True})
    if (AQUI / "testnet.txt").exists():
        ex.set_sandbox_mode(True)
    return ex


def plan(saldo, valores, precios, maximos, semana_nueva, tramos):
    compras, tramos = [], dict(tramos)
    reserva = saldo * RESERVA
    libre = saldo - reserva
    for m in CARTERA:
        if m not in precios:
            continue
        caida = 1 - precios[m] / maximos[m]
        nivel = sum(caida >= c for c in CAIDAS)
        if caida < 0.05:
            tramos[m] = 0
        if nivel > tramos.get(m, 0):
            importe = min(reserva, TRAMO * saldo * (nivel - tramos.get(m, 0)))
            if importe >= MINIMO:
                compras.append({"moneda": m, "importe": round(importe, 2), "motivo": f"cae un {caida * 100:.0f} % desde su máximo: compra extra"})
                reserva -= importe; tramos[m] = nivel
    if semana_nueva and libre >= MINIMO:
        presupuesto = libre * REPARTO_SEMANAL if sum(valores.values()) > 0 else libre
        total = sum(valores.values()) + presupuesto
        faltas = {m: max(0.0, w * total - valores.get(m, 0)) for m, w in CARTERA.items() if m in precios}
        suma = sum(faltas.values())
        for m, f in faltas.items():
            importe = presupuesto * f / suma if suma else 0
            if importe >= MINIMO:
                compras.append({"moneda": m, "importe": round(importe, 2), "motivo": "compra periódica"})
    return compras, tramos


def main():
    import ccxt
    est = json.loads(ESTADO.read_text()) if ESTADO.exists() else {"semana": None, "tramos": {}, "log": []}
    ex = conectar()
    prueba = not (AQUI / "enviar_binance.txt").exists()
    red = "TESTNET" if (AQUI / "testnet.txt").exists() else "REAL"
    bal = ex.fetch_balance()
    saldo = float(bal.get("free", {}).get(QUOTE, 0) or 0)
    precios, maximos, valores = {}, {}, {}
    publico = ccxt.binance()  # precios del mercado real (la testnet tiene historia corta)
    for m in CARTERA:
        par = f"{m}/{QUOTE}"
        velas = publico.fetch_ohlcv(par, "1d", limit=365)
        precios[m] = float(velas[-1][4]); maximos[m] = max(v[2] for v in velas)
        valores[m] = float(bal.get("total", {}).get(m, 0) or 0) * precios[m]
    hoy = datetime.now(); semana = f"{hoy.isocalendar().year}-{hoy.isocalendar().week}"
    compras, tramos = plan(saldo, valores, precios, maximos, est["semana"] != semana, est["tramos"])
    log = lambda t: (est["log"].append(f"{hoy:%Y-%m-%d %H:%M} {t}"), print(t))
    for c in compras:
        par = f"{c['moneda']}/{QUOTE}"
        if prueba:
            log(f"[prueba · {red}] Compraría {c['importe']} € de {c['moneda']}: {c['motivo']}"); continue
        try:
            ex.create_order(par, "market", "buy", None, None, {"quoteOrderQty": c["importe"]})
            log(f"[{red}] Compro {c['importe']} € de {c['moneda']}: {c['motivo']}")
        except Exception as e:
            log(f"[{red}] Error comprando {c['moneda']}: {e}")
    if not compras:
        log(f"[{red}] Hoy no toca comprar cripto.")
    if not prueba:
        est["semana"] = semana; est["tramos"] = tramos
    est["log"] = est["log"][-200:]
    ESTADO.write_text(json.dumps(est, indent=2, ensure_ascii=False))
    filas = [{"moneda": m, "objetivo": w, "valor": round(valores.get(m, 0), 2), "caida": round((1 - precios[m] / maximos[m]) * 100, 1)} for m, w in CARTERA.items()]
    OFICINA.parent.mkdir(exist_ok=True)
    OFICINA.write_text("window.BINANCE = " + json.dumps({"fecha": f"{hoy:%Y-%m-%d %H:%M}", "red": red, "prueba": prueba, "saldo": saldo,
                       "filas": filas, "log": est["log"][-30:]}, ensure_ascii=False) + ";\n")


if __name__ == "__main__":
    main()
