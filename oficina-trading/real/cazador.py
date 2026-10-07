"""
Cazador de tendencias (parte "satélite" del fondo). Corre cada día.

  - Analista (busca): recorre una lista amplia de ETF/ETN de sectores, países y temas y
    se queda con los que están en tendencia alcista clara: precio > media 50 > media 200,
    rentabilidad positiva a 3 y 6 meses y cerca de máximos de un año.
  - Previsión: para cada candidato mira su propio historial. Cada vez que se dio esta misma
    situación, ¿qué pasó en las 20 sesiones siguientes? Si acertó menos del 55 % o de media
    perdió, se descarta. Es una tasa base del pasado, no una bola de cristal.
  - Riesgos: cada posición arriesga como mucho el 1 % del capital total hasta su stop
    (5 veces el movimiento diario medio por debajo). Ninguna pasa del 10 % y el cazador
    entero no pasa del tope de capital que le des (20 % por defecto).
  - Salidas: stop que sube con el precio (nunca baja). Opcional: cierre bajo la media 50.
Lógica pura con pandas: no se conecta a nada.
"""
import math

import numpy as np
import pandas as pd

PARAMS = {
    "media_corta": 50, "media_larga": 200,
    "cerca_maximo": 0.05,     # a menos de un 5 % del máximo de 252 sesiones
    "horizonte": 20,          # sesiones para la previsión
    "acierto_min": 0.55,      # tasa histórica mínima de acierto
    "riesgo_pos": 0.01,       # 1 % del capital total en riesgo por posición
    "atr_mult": 5.0,          # distancia del stop en movimientos medios diarios (de cierre a cierre)
    "max_pos": 0.10,          # 10 % del capital como máximo por posición
    "max_posiciones": 4,
    "toma_beneficio": 0.15,   # al +15 % vende la mitad y sube el stop a la entrada (el resto ya no puede perder)
    "salida_media": False,    # vender también si cierra bajo la media de 50 (en las pruebas daba más sustos que ayuda)
}


def _atr(c: pd.Series, n=20):
    """Movimiento diario medio (solo con cierres)."""
    return c.diff().abs().rolling(n).mean()


def senal(c: pd.Series, p=PARAMS) -> pd.Series:
    """True los días en que el activo está en tendencia alcista clara."""
    m1, m2 = c.rolling(p["media_corta"]).mean(), c.rolling(p["media_larga"]).mean()
    maximo = c.rolling(252, min_periods=200).max()
    return ((c > m1) & (m1 > m2) & (c / c.shift(63) > 1) & (c / c.shift(126) > 1)
            & (c >= maximo * (1 - p["cerca_maximo"])))


def prevision(c: pd.Series, p=PARAMS, hasta=None) -> dict:
    """Tasa base: tras cada día con señal (hasta `hasta`), rentabilidad de las 20 sesiones siguientes."""
    c = c.dropna()
    if hasta is not None:
        c = c.loc[:hasta]
    s = senal(c, p)
    fut = c.shift(-p["horizonte"]) / c - 1
    x = fut[s].dropna()
    if len(x) < 30:
        return {"casos": int(len(x)), "acierto": None, "media_%": None}
    return {"casos": int(len(x)), "acierto": round(float((x > 0).mean()), 3), "media_%": round(float(x.mean() * 100), 2)}


def buscar(P: pd.DataFrame, p=PARAMS) -> list:
    """Candidatos de hoy ordenados por momentum ajustado por volatilidad."""
    out = []
    for s in P.columns:
        c = P[s].dropna()
        if len(c) < 260 or not bool(senal(c, p).iloc[-1]):
            continue
        prev = prevision(c, p, hasta=c.index[-1 - p["horizonte"]])  # solo casos ya cerrados
        vol = c.pct_change().iloc[-63:].std() * math.sqrt(252)
        mom = c.iloc[-1] / c.iloc[-127] - 1
        out.append({"simbolo": s, "precio": float(c.iloc[-1]), "atr": float(_atr(c).iloc[-1]),
                    "momentum_6m_%": round(mom * 100, 1), "vol_%": round(vol * 100, 1),
                    "puntuacion": round(mom / vol, 2) if vol > 0 else 0, **prev,
                    "pasa_prevision": bool(prev["acierto"] is not None and prev["acierto"] >= p["acierto_min"] and prev["media_%"] > 0)})
    return sorted(out, key=lambda x: -x["puntuacion"])


def gestionar(P: pd.DataFrame, cartera: dict, capital_total: float, tope: float, p=PARAMS, entero=True, subtopes=None, sin_compras=False):
    """
    Decide las órdenes del día para el cazador.
    cartera = {simbolo: {"cantidad", "entrada", "fecha", "stop", "maximo"}} (se actualiza aquí).
    subtopes = {nombre: (simbolos, fraccion)}: límite extra para un grupo (p. ej. cripto).
    Devuelve (ventas, compras, candidatos, notas) con cantidades enteras.
    """
    subtopes = subtopes or {}
    notas, ventas, compras = [], [], []
    hoy = P.index[-1]
    # 1. salidas: stop que sube o pérdida de la media 50
    for s, pos in list(cartera.items()):
        c = P[s].dropna() if s in P else pd.Series(dtype=float)
        if c.empty:
            continue
        px = float(c.iloc[-1]); atr = float(_atr(c).iloc[-1])
        pos["maximo"] = max(pos.get("maximo", px), px)
        pos["stop"] = round(max(pos["stop"], pos["maximo"] - p["atr_mult"] * atr), 4)
        m50 = float(c.rolling(p["media_corta"]).mean().iloc[-1])
        tp = p.get("toma_beneficio")
        if tp and not pos.get("parcial") and px >= pos["entrada"] * (1 + tp) and pos["cantidad"] >= 2 and px > pos["stop"]:
            q = pos["cantidad"] // 2
            ventas.append({"simbolo": s, "cantidad": q, "precio": px, "parcial": True,
                           "motivo": f"toma de beneficios al +{tp * 100:.0f} % (vende la mitad, el resto con stop en la entrada)",
                           "resultado_%": round((px / pos["entrada"] - 1) * 100, 1)})
            pos["cantidad"] -= q; pos["parcial"] = True
            pos["stop"] = round(max(pos["stop"], pos["entrada"]), 4)
            continue
        if px <= pos["stop"] or (p["salida_media"] and px < m50):
            motivo = "salta el stop" if px <= pos["stop"] else "pierde la media de 50"
            ventas.append({"simbolo": s, "cantidad": pos["cantidad"], "precio": px, "motivo": motivo,
                           "resultado_%": round((px / pos["entrada"] - 1) * 100, 1)})
    for v in ventas:
        if not v.get("parcial"):
            cartera.pop(v["simbolo"], None)
    if sin_compras:
        notas.append("Hoy no se abren posiciones nuevas: la cuenta ha caído más del límite diario.")
        return ventas, compras, buscar(P, p), notas
    # 2. entradas
    candidatos = buscar(P, p)
    usado = sum(pos["cantidad"] * float(P[s].dropna().iloc[-1]) for s, pos in cartera.items() if s in P)
    libre = tope * capital_total - usado
    for cand in candidatos:
        if len(cartera) >= p["max_posiciones"] or libre <= 0:
            break
        s = cand["simbolo"]
        if s in cartera or any(v["simbolo"] == s for v in ventas):
            continue
        if not cand["pasa_prevision"]:
            notas.append(f"{s} está en tendencia pero su historial no convence ({cand['acierto']} de acierto). Lo dejo pasar.")
            continue
        riesgo_unit = p["atr_mult"] * cand["atr"]
        if riesgo_unit <= 0:
            continue
        importe = min(p["riesgo_pos"] * capital_total / riesgo_unit * cand["precio"], p["max_pos"] * capital_total, libre)
        for nombre, (grupo, frac) in subtopes.items():
            if s in grupo:
                en_grupo = sum(pos["cantidad"] * float(P[x].dropna().iloc[-1]) for x, pos in cartera.items() if x in grupo and x in P)
                importe = min(importe, frac * capital_total - en_grupo)
        q = math.floor(importe / cand["precio"]) if entero else math.floor(importe / cand["precio"] * 1e4) / 1e4
        if q <= 0:
            if libre < cand["precio"]:
                notas.append(f"{s} interesa, pero el cazador ya usa casi todo su tope de capital.")
            else:
                notas.append(f"{s} interesa, pero una participación arriesgaría más del 1 % del capital.")
            continue
        stop = round(cand["precio"] - riesgo_unit, 4)
        cartera[s] = {"cantidad": q, "entrada": cand["precio"], "fecha": str(hoy.date()), "stop": stop, "maximo": cand["precio"]}
        compras.append({"simbolo": s, "cantidad": q, "precio": cand["precio"], "stop": stop,
                        "motivo": f"tendencia alcista, +{cand['momentum_6m_%']} % en 6 meses, acertó el {round(cand['acierto'] * 100)} % de las veces"})
        libre -= q * cand["precio"]
    return ventas, compras, candidatos, notas


def backtest(P: pd.DataFrame, tope=1.0, p=PARAMS, coste=0.002, desde=None) -> pd.Series:
    """Simula el cazador día a día (decide al cierre, opera al cierre siguiente). Devuelve rentabilidad diaria
    sobre el capital asignado al cazador. La previsión solo usa casos ya cerrados en cada fecha."""
    P = P.dropna(how="all")
    rets = P.pct_change().fillna(0)
    capital, cartera, out = 1.0, {}, {}
    inicio = 260 if desde is None else max(260, P.index.searchsorted(pd.Timestamp(desde)))
    for i in range(inicio, len(P) - 1):
        ventas, compras, _, _ = gestionar(P.iloc[: i + 1], cartera, capital, tope, p, entero=False)
        gasto = sum(v["cantidad"] * v["precio"] for v in ventas + compras) * coste
        # cantidades → pesos sobre el capital
        valor_pos = {s: pos["cantidad"] * float(P[s].iloc[i]) for s, pos in cartera.items()}
        r = sum(v * rets[s].iloc[i + 1] for s, v in valor_pos.items()) / capital - gasto / capital
        capital *= 1 + r
        out[P.index[i + 1]] = r
    return pd.Series(out, dtype=float)
