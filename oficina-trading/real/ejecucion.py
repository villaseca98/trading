"""
Ejecución e infraestructura: convierte pesos objetivo en órdenes y las manda.
Dos "brókers":
  - BrokerVirtual: cartera de papel guardada en estado.json, a precios reales de cierre.
  - BrokerIBKR: cuenta demo de Interactive Brokers (IB Gateway en Paper Trading).
"""
import math
import sys
import time

import config as C


def comision(importe):
    return max(3.0, importe * 0.0005)  # aproximación a la tarifa fija de IBKR en Xetra


def planificar(pesos: dict, valor: float, posiciones: dict, precios: dict) -> list:
    """Órdenes para pasar de `posiciones` a `pesos` (fracción del valor). Ventas primero."""
    ordenes = []
    for s in sorted(set(pesos) | set(posiciones)):
        px = precios.get(s)
        if not px or px <= 0:
            continue
        actual = posiciones.get(s, 0)
        objetivo = math.floor(pesos.get(s, 0) * valor / px)
        delta = objetivo - actual
        if delta == 0:
            continue
        importe = abs(delta) * px
        if importe < C.MIN_ORDEN_EUR and objetivo != 0:
            continue  # ajuste pequeño: no compensa la comisión
        if importe > C.MAX_ORDEN_EUR:
            delta = int(math.copysign(math.floor(C.MAX_ORDEN_EUR / px), delta))
            if delta == 0:
                continue
        lado = "BUY" if delta > 0 else "SELL"
        limite = round(px * (1 + C.MARGEN_LIMITE if lado == "BUY" else 1 - C.MARGEN_LIMITE), 2)
        ordenes.append({"simbolo": s, "lado": lado, "cantidad": abs(delta), "limite": limite,
                        "importe": round(abs(delta) * px, 2), "objetivo": objetivo})
    return sorted(ordenes, key=lambda o: o["lado"] != "SELL")


class BrokerVirtual:
    """Cartera de papel persistente. Llena al precio límite si el cierre lo permite."""

    def __init__(self, estado):
        v = estado.setdefault("virtual", {"efectivo": C.CAPITAL_FICTICIO, "posiciones": {}})
        self.v = v
        self.cuenta = "VIRTUAL"

    def valor(self, precios):
        return self.v["efectivo"] + sum(q * precios.get(s, 0) for s, q in self.v["posiciones"].items())

    def posiciones(self):
        return dict(self.v["posiciones"])

    def ejecutar(self, ordenes, precios):
        hechas = []
        for o in ordenes:
            px = precios[o["simbolo"]]
            importe = o["cantidad"] * px
            if o["lado"] == "BUY":
                if importe + comision(importe) > self.v["efectivo"]:
                    o["cantidad"] = int((self.v["efectivo"] - comision(importe)) // px)
                    importe = o["cantidad"] * px; o["importe"] = round(importe, 2)
                    if o["cantidad"] <= 0:
                        o["estado"] = "sin efectivo suficiente"; hechas.append(o); continue
                coste = importe + comision(importe)
                self.v["efectivo"] -= coste
                self.v["posiciones"][o["simbolo"]] = self.v["posiciones"].get(o["simbolo"], 0) + o["cantidad"]
            else:
                self.v["efectivo"] += importe - comision(importe)
                q = self.v["posiciones"].get(o["simbolo"], 0) - o["cantidad"]
                if q > 0:
                    self.v["posiciones"][o["simbolo"]] = q
                else:
                    self.v["posiciones"].pop(o["simbolo"], None)
            o["estado"] = "ejecutada (virtual)"; hechas.append(o)
        self.v["efectivo"] = round(self.v["efectivo"], 2)
        return hechas

    def cerrar(self):
        pass


class BrokerIBKR:
    """Cuenta demo de IBKR. Se niega a operar en una cuenta real si SOLO_DEMO está activo."""

    def __init__(self):
        from ib_async import IB
        self.ib = IB()
        self.ib.connect(C.HOST, C.PUERTO, clientId=C.CLIENT_ID, timeout=20)
        self.cuenta = self.ib.managedAccounts()[0]
        if C.SOLO_DEMO and not self.cuenta.startswith("DU"):
            self.ib.disconnect()
            sys.exit(f"La cuenta {self.cuenta} no es de demo. Paro por seguridad (SOLO_DEMO = True).")
        self.contratos = {}

    def _contrato(self, s):
        if s not in self.contratos:
            from ib_async import Stock
            c = Stock(s, "SMART", C.DIVISA, primaryExchange=C.BOLSA)
            if not self.ib.qualifyContracts(c):
                raise RuntimeError(f"IBKR no reconoce {s} en {C.BOLSA}")
            self.contratos[s] = c
        return self.contratos[s]

    def _cuenta(self, etiqueta):
        for v in self.ib.accountValues(self.cuenta):
            if v.tag == etiqueta and v.currency in (C.DIVISA, "BASE"):
                return float(v.value)
        return 0.0

    def valor(self, precios):
        return self._cuenta("NetLiquidation")

    def posiciones(self):
        return {p.contract.symbol: int(p.position) for p in self.ib.positions(self.cuenta) if p.position}

    def ejecutar(self, ordenes, precios):
        from ib_async import LimitOrder
        hechas = []
        ventas = [o for o in ordenes if o["lado"] == "SELL"]
        compras = [o for o in ordenes if o["lado"] == "BUY"]
        for grupo in (ventas, compras):
            if grupo is compras and ventas:
                time.sleep(15)  # deja que se llenen las ventas para tener efectivo
            disponible = self._cuenta("AvailableFunds") if grupo is compras else None
            for o in grupo:
                if disponible is not None:
                    cabe = int((disponible - comision(o["cantidad"] * o["limite"])) // o["limite"])
                    if cabe < o["cantidad"]:
                        o["cantidad"] = max(0, cabe); o["importe"] = round(o["cantidad"] * o["limite"], 2)
                    if o["cantidad"] == 0 or o["importe"] < C.MIN_ORDEN_EUR:
                        o["estado"] = "sin efectivo suficiente"; hechas.append(o); continue
                    disponible -= o["cantidad"] * o["limite"]
                if C.MODO_PRUEBA:
                    o["estado"] = "simulada (MODO_PRUEBA)"; hechas.append(o); continue
                try:
                    t = self.ib.placeOrder(self._contrato(o["simbolo"]),
                                           LimitOrder(o["lado"], o["cantidad"], o["limite"], tif="DAY"))
                    self.ib.sleep(3)
                    o["estado"] = t.orderStatus.status; o["orden"] = t.order.orderId
                except Exception as e:
                    o["estado"] = f"error: {e}"
                hechas.append(o)
        return hechas

    def cerrar(self):
        self.ib.disconnect()
