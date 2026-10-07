"""
Mesa de futuros micro: SOLO PLAN, no envía órdenes.
Para cada futuro decide largo (tendencia alcista), corto (tendencia bajista) o fuera,
y cuántos contratos caben arriesgando FUTUROS_RIESGO del capital con un stop de 3 movimientos medios.
"""
import math
import pandas as pd

import config as C


def plan(precios: pd.DataFrame, capital_eur: float, eurusd: float = 1.1) -> list:
    filas = []
    for s, (y, mult, nombre) in C.FUTUROS.items():
        if y not in precios or precios[y].dropna().size < 260:
            filas.append({"simbolo": s, "nombre": nombre, "lado": "sin datos"}); continue
        c = precios[y].dropna()
        px = float(c.iloc[-1]); m200 = float(c.rolling(200).mean().iloc[-1])
        m3 = px / float(c.iloc[-64]) - 1; m6 = px / float(c.iloc[-127]) - 1
        if px > m200 and m3 > 0 and m6 > 0:
            lado = "LARGO"
        elif px < m200 and m3 < 0 and m6 < 0:
            lado = "CORTO"
        else:
            lado = "FUERA"
        mov = float(c.diff().abs().rolling(20).mean().iloc[-1])
        dist = 3 * mov
        riesgo_contrato_eur = dist * mult / eurusd
        n = math.floor(C.FUTUROS_RIESGO * capital_eur / riesgo_contrato_eur) if lado != "FUERA" and riesgo_contrato_eur > 0 else 0
        n = min(n, math.floor(capital_eur * eurusd / (px * mult)))  # nunca más exposición que el capital (sin apalancamiento neto)
        stop = px - dist if lado == "LARGO" else px + dist if lado == "CORTO" else None
        filas.append({"simbolo": s, "nombre": nombre, "lado": lado, "precio": round(px, 2), "stop": round(stop, 2) if stop else None,
                      "contratos": n, "exposicion_eur": round(n * px * mult / eurusd), "riesgo_contrato_eur": round(riesgo_contrato_eur),
                      "nota": "no cabe ni un contrato con el riesgo permitido" if lado != "FUERA" and n == 0 else ""})
    return filas
