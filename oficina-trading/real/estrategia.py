"""
Cerebro del fondo real: decide los pesos objetivo de la cartera.

Lo que hace, en el lenguaje de la oficina:
  - Macro / traders de tendencia: cada activo recibe una nota de 0 a 1 según
    cuántas de estas señales están a favor: precio sobre su media de 200 sesiones,
    y rentabilidad positiva a 3, 6 y 12 meses. Media de varios horizontes en vez de
    un parámetro "óptimo": así no se ajusta al pasado.
  - Riesgos: cada activo pesa en proporción inversa a su volatilidad, la cartera
    entera apunta a una volatilidad objetivo y ningún activo pasa del tope.
  - Lo que no se invierte va al activo de liquidez (fondo monetario).
Todo es lógica pura con pandas, sin conexión a nada, para poder probarlo.
"""
import numpy as np
import pandas as pd

PARAMS = {
    "media": 200,            # sesiones de la media larga
    "horizontes": (63, 126, 252),  # 3, 6 y 12 meses de momentum
    "vol_ventana": 63,       # sesiones para estimar volatilidad y correlaciones
    "vol_objetivo": 0.12,    # volatilidad anual objetivo de toda la cartera
    "tope_activo": 0.40,     # peso máximo por activo
    "umbral": 0.03,          # no se rebalancea un activo si cambia menos que esto
}


def notas(precios: pd.DataFrame, p=PARAMS) -> pd.DataFrame:
    """Nota de tendencia 0..1 por activo y fecha (usa solo datos hasta esa fecha)."""
    señales = [(precios > precios.rolling(p["media"]).mean()).astype(float)]
    for h in p["horizontes"]:
        señales.append((precios / precios.shift(h) - 1 > 0).astype(float))
    nota = sum(señales) / len(señales)
    return nota.where(precios.rolling(max(p["media"], max(p["horizontes"]))).count() >= max(p["media"], max(p["horizontes"])))


def pesos_en(precios: pd.DataFrame, fecha, p=PARAMS) -> dict:
    """Pesos objetivo para una fecha concreta (solo mira el pasado)."""
    hist = precios.loc[:fecha].dropna(how="all")
    nota = notas(hist, p).iloc[-1].fillna(0)
    rets = np.log(hist).diff().iloc[-p["vol_ventana"]:]
    vol = rets.std() * np.sqrt(252)
    vol = vol.where(vol > 0)  # sin datos recientes: fuera
    vivos = [a for a in precios.columns if nota[a] > 0 and vol[a] > 0]
    if not vivos:
        return {}
    bruto = pd.Series({a: nota[a] / vol[a] for a in vivos})
    # cada activo con nota completa aporta el mismo riesgo
    w = bruto / (pd.Series({a: 1 / vol[a] for a in precios.columns if vol[a] > 0}).sum())
    w = w.clip(upper=p["tope_activo"])
    # escalar a la volatilidad objetivo con la matriz de covarianzas
    cov = rets[vivos].cov() * 252
    vol_cartera = float(np.sqrt(w[vivos].values @ cov.values @ w[vivos].values))
    if vol_cartera > 0:
        w = w * min(1 / max(w.sum(), 1e-9), p["vol_objetivo"] / vol_cartera)
    w = w.clip(upper=p["tope_activo"])
    if w.sum() > 1:
        w = w / w.sum()
    return {a: round(float(x), 4) for a, x in w.items() if x > 0.005}


def explicar(precios: pd.DataFrame, fecha, p=PARAMS) -> list:
    """Frases para la oficina: qué ve cada activo."""
    hist = precios.loc[:fecha]
    nota = notas(hist, p).iloc[-1]
    vol = np.log(hist).diff().iloc[-p["vol_ventana"]:].std() * np.sqrt(252)
    frases = []
    for a in precios.columns:
        if pd.isna(nota[a]):
            frases.append(f"{a}: aún sin historia suficiente.")
            continue
        estado = "tendencia alcista clara" if nota[a] == 1 else "sin tendencia" if nota[a] == 0 else f"tendencia mixta ({int(nota[a] * 4)}/4 señales)"
        frases.append(f"{a}: {estado}, volatilidad {vol[a] * 100:.0f} %.")
    return frases


def backtest(precios: pd.DataFrame, liquidez: pd.Series | None = None, p=PARAMS,
             coste=0.001, cada=5, desde=None):
    """
    Simula la estrategia: decide al cierre del viernes (cada `cada` sesiones) y
    ejecuta al cierre siguiente. `liquidez` = rentabilidad diaria del dinero no
    invertido (si es None, 0 %). Devuelve (rentabilidades diarias, pesos).
    """
    rets = precios.pct_change().fillna(0)
    rf = liquidez.reindex(precios.index).fillna(0) if liquidez is not None else pd.Series(0.0, index=precios.index)
    fechas = precios.index
    inicio = max(p["media"], max(p["horizontes"])) + 5
    if desde is not None:
        inicio = max(inicio, fechas.searchsorted(pd.Timestamp(desde)))
    w = pd.Series(0.0, index=precios.columns)
    out, pesos = [], []
    for i in range(inicio, len(fechas) - 1):
        if (i - inicio) % cada == 0:
            obj = pd.Series(pesos_en(precios.iloc[: i + 1], fechas[i], p)).reindex(precios.columns).fillna(0)
            cambio = (obj - w).abs()
            nuevo = w.where(cambio < p["umbral"], obj)
            gasto = (nuevo - w).abs().sum() * coste
            w = nuevo
        else:
            gasto = 0.0
        r = float((w * rets.iloc[i + 1]).sum() + (1 - w.sum()) * rf.iloc[i + 1] - gasto)
        out.append((fechas[i + 1], r))
        pesos.append((fechas[i + 1], w.copy()))
        # los pesos derivan con el mercado hasta el siguiente rebalanceo
        crec = w * (1 + rets.iloc[i + 1])
        tot = crec.sum() + (1 - w.sum()) * (1 + rf.iloc[i + 1])
        w = crec / tot if tot > 0 else w
    r = pd.Series([x for _, x in out], index=pd.DatetimeIndex([f for f, _ in out]), dtype=float)
    return r, pd.DataFrame([x for _, x in pesos], index=pd.DatetimeIndex([f for f, _ in pesos]), columns=precios.columns)


def resumen(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 20:
        return {}
    eq = (1 + r).cumprod()
    años = len(r) / 252
    return {
        "rent_anual_%": round((eq.iloc[-1] ** (1 / años) - 1) * 100, 1),
        "volatilidad_%": round(r.std() * np.sqrt(252) * 100, 1),
        "sharpe": round(r.mean() / r.std() * np.sqrt(252), 2) if r.std() > 0 else 0,
        "caida_max_%": round((1 - eq / eq.cummax()).max() * 100, 1),
        "peor_año_%": round(((1 + r).groupby(r.index.year).prod() - 1).min() * 100, 1),
    }
