"""
Bot pequeño para IBKR: aportación semanal a un ETF con filtro de media de 200 días.

Qué hace cada vez que lo ejecutas (pensado para una vez por semana):
  1. Suma la aportación semanal al "bote pendiente".
  2. Si el precio está por ENCIMA de su media de 200 sesiones, compra tantas
     participaciones enteras como permita el bote. Lo que sobra se queda para la
     semana siguiente.
  3. Si está por DEBAJO, no compra y el bote sigue creciendo hasta que el
     mercado vuelva a estar en tendencia.
  Nunca vende. Solo decide cuándo comprar.

Seguridad:
  - Por defecto MODO_PRUEBA = True: calcula y apunta lo que haría, sin enviar órdenes.
  - Se niega a operar si la cuenta no es de demo (las de demo empiezan por "DU"),
    salvo que cambies SOLO_DEMO a False a propósito.
  - Ninguna orden supera MAX_ORDEN_EUR.
"""

import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

# ---------------- Configuración ----------------
SIMBOLO = "VWCE"          # Vanguard FTSE All-World UCITS (acumulación)
BOLSA = "IBIS"            # Xetra en IBKR
DIVISA = "EUR"
APORTACION_SEMANAL = 50.0  # euros que "metes" cada semana
MAX_ORDEN_EUR = 500.0      # tope de seguridad por orden
DIAS_MEDIA = 200
MARGEN_LIMITE = 0.005      # orden limitada a precio +0,5 % para no pagar de más

HOST = "127.0.0.1"
PUERTO = 4002              # IB Gateway demo = 4002 · TWS demo = 7497
CLIENT_ID = 17

MODO_PRUEBA = True         # True = no envía órdenes, solo las apunta
SOLO_DEMO = True           # True = se niega a operar en cuenta real

CARPETA = Path(__file__).resolve().parent
ESTADO = CARPETA / "estado.json"
REGISTRO = CARPETA / "registro.csv"
# -----------------------------------------------


def media(valores, n):
    if len(valores) < n:
        return None
    return sum(valores[-n:]) / n


def decidir(cierres, pendiente, aportacion=APORTACION_SEMANAL,
            max_orden=MAX_ORDEN_EUR, dias=DIAS_MEDIA):
    """Lógica pura, sin conexión. Devuelve un dict con la decisión."""
    pendiente += aportacion
    precio = cierres[-1]
    sma = media(cierres, dias)
    if sma is None:
        return {"accion": "esperar", "motivo": f"faltan datos para la media de {dias}",
                "precio": precio, "media": None, "cantidad": 0, "pendiente": pendiente}
    if precio <= sma:
        return {"accion": "esperar", "motivo": "precio por debajo de la media",
                "precio": precio, "media": sma, "cantidad": 0, "pendiente": pendiente}
    presupuesto = min(pendiente, max_orden)
    cantidad = math.floor(presupuesto / (precio * (1 + MARGEN_LIMITE)))
    if cantidad == 0:
        return {"accion": "esperar", "motivo": "aún no llega para una participación",
                "precio": precio, "media": sma, "cantidad": 0, "pendiente": pendiente}
    return {"accion": "comprar", "motivo": "precio por encima de la media",
            "precio": precio, "media": sma, "cantidad": cantidad,
            "pendiente": pendiente}


def leer_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text())
    return {"pendiente": 0.0, "invertido": 0.0, "participaciones": 0}


def guardar_estado(estado):
    ESTADO.write_text(json.dumps(estado, indent=2))


def apuntar(fila):
    nuevo = not REGISTRO.exists()
    with REGISTRO.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fila.keys()))
        if nuevo:
            w.writeheader()
        w.writerow(fila)


def main():
    from ib_async import IB, Stock, LimitOrder

    ib = IB()
    ib.connect(HOST, PUERTO, clientId=CLIENT_ID, timeout=20)
    try:
        cuenta = ib.managedAccounts()[0]
        if SOLO_DEMO and not cuenta.startswith("DU"):
            sys.exit(f"La cuenta {cuenta} no es de demo. Paro por seguridad.")

        contrato = Stock(SIMBOLO, BOLSA, DIVISA)
        ib.qualifyContracts(contrato)
        barras = ib.reqHistoricalData(
            contrato, endDateTime="", durationStr="2 Y", barSizeSetting="1 day",
            whatToShow="TRADES", useRTH=True)
        cierres = [b.close for b in barras]
        if not cierres:
            sys.exit("No llegaron precios. ¿Tienes permisos de datos para Xetra?")

        estado = leer_estado()
        d = decidir(cierres, estado["pendiente"])
        estado["pendiente"] = d["pendiente"]
        orden_id = ""

        if d["accion"] == "comprar":
            limite = round(d["precio"] * (1 + MARGEN_LIMITE), 2)
            coste = d["cantidad"] * limite
            if MODO_PRUEBA:
                orden_id = "simulada"
            else:
                trade = ib.placeOrder(contrato, LimitOrder("BUY", d["cantidad"], limite, tif="DAY"))
                ib.sleep(5)
                orden_id = str(trade.order.orderId)
            estado["pendiente"] = round(d["pendiente"] - coste, 2)
            estado["invertido"] = round(estado["invertido"] + coste, 2)
            estado["participaciones"] += d["cantidad"]

        guardar_estado(estado)
        fila = {
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "cuenta": cuenta,
            "simbolo": SIMBOLO,
            "precio": round(d["precio"], 2),
            "media200": round(d["media"], 2) if d["media"] else "",
            "accion": d["accion"],
            "cantidad": d["cantidad"],
            "motivo": d["motivo"],
            "pendiente": estado["pendiente"],
            "invertido": estado["invertido"],
            "orden": orden_id,
            "modo": "prueba" if MODO_PRUEBA else "real",
        }
        apuntar(fila)
        print(json.dumps(fila, ensure_ascii=False, indent=2))
    finally:
        ib.disconnect()


if __name__ == "__main__":
    main()
