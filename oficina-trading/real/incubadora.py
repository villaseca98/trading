"""
Incubadora del fondo real: estrategias candidatas que NO mueven dinero.
Cada una se sigue en la sombra desde el día en que entró (fecha de alta), así que
su resultado es siempre fuera de muestra: nadie la ajustó mirando esos datos.
El comité propone ascender a la que, tras al menos un año, supere a la principal.
"""
import numpy as np
import pandas as pd

import config as C
import estrategia as E


def _rsi(c, n):
    d = c.diff()
    g = d.clip(lower=0).rolling(n).mean()
    p = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + g / p)


def rsi2_sp500(P, L):
    """Connors: compra el S&P 500 tras 1-3 días de caída fuerte en tendencia alcista."""
    c = P[C.ROLES["sp500"]]; r = _rsi(c, 2); f = c > c.rolling(200).mean(); ma5 = c.rolling(5).mean()
    pos, dentro = [], False
    for i in range(len(c)):
        if dentro and c.iloc[i] > ma5.iloc[i]:
            dentro = False
        elif not dentro and r.iloc[i] < 10 and f.iloc[i]:
            dentro = True
        pos.append(1.0 if dentro else 0.0)
    return pd.DataFrame({C.ROLES["sp500"]: pos}, index=c.index), 1


def doble_momentum(P, L):
    """Antonacci: cada mes, la bolsa (EE. UU. o emergentes) que más ha subido en 12 meses
    si gana al monetario; si no, bonos."""
    m12 = P / P.shift(252) - 1
    l12 = L / L.shift(252) - 1
    w = pd.DataFrame(0.0, index=P.index, columns=P.columns)
    mejor = m12[[C.ROLES["sp500"], C.ROLES["emerg"]]].fillna(-9).idxmax(axis=1)
    for f in P.index:
        b = mejor.get(f)
        if isinstance(b, str) and m12.at[f, b] > l12.get(f, 0):
            w.at[f, b] = 1.0
        elif not np.isnan(m12.at[f, C.ROLES["bonos"]]):
            w.at[f, C.ROLES["bonos"]] = 1.0
    return w, 21


def cartera_permanente(P, L):
    """Browne: 25 % bolsa, 25 % bonos, 25 % oro, 25 % liquidez. Rebalanceo mensual."""
    w = pd.DataFrame(0.0, index=P.index, columns=P.columns)
    w[C.ROLES["mundo"]] = 0.25; w[C.ROLES["bonos"]] = 0.25; w[C.ROLES["oro"]] = 0.25
    return w, 21


def bolsa_mundial(P, L):
    """Referencia: comprar y mantener bolsa mundial (como el plan de ahorro)."""
    w = pd.DataFrame(0.0, index=P.index, columns=P.columns)
    w[C.ROLES["mundo"]] = 1.0
    return w, 21


def principal_dinamica(P, L):
    """La estrategia principal con perfil dinámico (más riesgo)."""
    return "principal", 0.15


CANDIDATAS = {
    "RSI-2 S&P 500 (Connors)": rsi2_sp500,
    "Doble momentum (Antonacci)": doble_momentum,
    "Cartera permanente (Browne)": cartera_permanente,
    "Bolsa mundial y mantener": bolsa_mundial,
    "Principal en perfil dinámico": principal_dinamica,
}


def simular(w: pd.DataFrame, cada: int, P: pd.DataFrame, L: pd.Series, coste=0.001):
    """Rebalancea a los pesos w cada `cada` sesiones (decide al cierre, aplica al día siguiente)."""
    rets = P.pct_change().fillna(0); rl = L.pct_change().fillna(0)
    cur = pd.Series(0.0, index=P.columns); out = {}
    for i in range(len(P) - 1):
        if i % cada == 0 or cada == 1:
            obj = w.iloc[i].fillna(0)
            gasto = (obj - cur).abs().sum() * coste
            cur = obj.copy()
        else:
            gasto = 0.0
        r = float((cur * rets.iloc[i + 1]).sum() + (1 - cur.sum()) * rl.iloc[i + 1] - gasto)
        out[P.index[i + 1]] = r
        crec = cur * (1 + rets.iloc[i + 1]); tot = crec.sum() + (1 - cur.sum()) * (1 + rl.iloc[i + 1])
        cur = crec / tot if tot > 0 else cur
    return pd.Series(list(out.values()), index=pd.DatetimeIndex(list(out.keys())), dtype=float)


def evaluar(P: pd.DataFrame, L: pd.Series, altas: dict, params: dict, r_principal: pd.Series):
    """Resultado de cada candidata desde su alta (fuera de muestra) y propuesta del comité."""
    hoy = P.index[-1]; filas = []
    for nombre, fn in CANDIDATAS.items():
        alta = pd.Timestamp(altas.setdefault(nombre, str(hoy.date())))
        try:
            x, cada = fn(P, L)
            if isinstance(x, str):
                p = dict(params); p["vol_objetivo"] = cada
                r, _ = E.backtest(P, L.pct_change().fillna(0), p=p)
            else:
                r = simular(x, cada, P, L)
        except Exception as e:  # una candidata rota no para el fondo
            print(f"Aviso: la candidata {nombre} falló: {e}")
            continue
        historico = E.resumen(r[r.index <= alta])  # antes del alta: solo orientativo
        r = r[r.index > alta]
        rp = r_principal[r_principal.index > alta]
        dias = len(r)
        res = E.resumen(r) if dias >= 20 else {}
        resp = E.resumen(rp) if len(rp) >= 20 else {}
        propuesta = bool(dias >= 252 and res and resp and res["sharpe"] > resp["sharpe"] + 0.2
                         and res["caida_max_%"] <= resp["caida_max_%"] * 1.2)
        filas.append({"nombre": nombre, "alta": str(alta.date()), "sesiones": dias,
                      "resultado_%": round(((1 + r).prod() - 1) * 100, 2) if dias else 0.0,
                      **res, "historico": historico, "propuesta_ascenso": propuesta, "descripcion": fn.__doc__.strip()})
    return filas
