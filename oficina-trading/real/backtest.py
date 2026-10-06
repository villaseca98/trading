"""
Prueba la estrategia principal con los precios reales de los ETF (tantos años como haya)
y la compara con referencias sencillas. Ejecútalo antes de fiarte de nada:
  python backtest.py
"""
import pandas as pd
import config as C
import datos
import estrategia as E
import incubadora

tickers = {s: y for s, (y, _) in C.ACTIVOS.items()}
tickers[C.LIQUIDEZ[0]] = C.LIQUIDEZ[1]
todo = datos.descargar(tickers)
L = todo[C.LIQUIDEZ[0]].ffill()
P = todo[list(C.ACTIVOS)].dropna(axis=1, thresh=300)
P = P.loc[P.dropna().index[0]:]  # desde que todos los activos cotizan
rl = L.pct_change().reindex(P.index).fillna(0)
print(f"Datos reales de {P.index[0].date()} a {P.index[-1].date()} · activos: {', '.join(P.columns)}\n")

filas = {}
for perfil, vo in C.PERFILES.items():
    p = dict(E.PARAMS); p["vol_objetivo"] = vo
    r, w = E.backtest(P, rl, p=p)
    filas[f"Principal ({perfil})"] = E.resumen(r) | {"invertido_medio_%": round(w.sum(axis=1).mean() * 100)}
inicio = r.index[0]
for nombre in ["Bolsa mundial y mantener", "Cartera permanente (Browne)", "Doble momentum (Antonacci)"]:
    x, cada = incubadora.CANDIDATAS[nombre](P, L.reindex(P.index).ffill())
    rr = incubadora.simular(x, cada, P, L.reindex(P.index).ffill())
    filas[nombre] = E.resumen(rr[rr.index >= inicio])
t = pd.DataFrame(filas).T
pd.set_option("display.width", 160)
print(t.to_string())
print("\nRentabilidades pasadas no garantizan las futuras. Lo importante es comparar la caída")
print("máxima y el Sharpe (rentabilidad por unidad de riesgo), no solo la rentabilidad.")
