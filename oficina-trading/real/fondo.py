"""
Fondo real automatizado: una pasada completa de la oficina. Pensado para cada día laborable
a media mañana, con Xetra abierta. La cartera principal se rebalancea una vez por semana;
el cazador de tendencias revisa entradas y stops todos los días.

  python fondo.py              → cuenta demo de IBKR (IB Gateway abierto en Paper Trading)
  python fondo.py --virtual    → cartera de papel propia, sin IBKR, con precios reales
  python fondo.py --reabrir    → quita el kill switch tras revisarlo
  python fondo.py --forzar     → rebalancea aunque ya se haya hecho esta semana

Orden de trabajo de la oficina:
  1. Analista: descarga precios.        2. Macro y traders: nota de tendencia por activo.
  3. Riesgos: pesos por volatilidad.    4. Kill switch: caída desde máximos.
  5. Comité: revisa la incubadora.      6. Ejecución: órdenes a IBKR o a la cartera virtual.
  7. Informe: estado.json, registro.csv, informe.md y datos para la oficina visual.
"""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import config as C
import datos
import estrategia as E
import cazador as K
import futuros as FUT
import incubadora
from ejecucion import BrokerAlpaca, BrokerIBKR, BrokerVirtual, planificar

AQUI = Path(__file__).resolve().parent
ESTADO = AQUI / "estado.json"
REGISTRO = AQUI / "registro.csv"
INFORME = AQUI / "informe.md"
OFICINA = AQUI.parent / "datos" / "estado_real.js"


def leer_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text())
    return {"pico": None, "kill": False, "historia": [], "altas_incubadora": {}, "ultimo_rebalanceo": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--virtual", action="store_true")
    ap.add_argument("--reabrir", action="store_true")
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()

    estado = leer_estado()
    voz = []  # (quién, qué dice) para el informe y la oficina
    decir = lambda quien, texto: (voz.append({"quien": quien, "texto": texto}), print(f"[{quien}] {texto}"))

    if a.reabrir:
        estado["kill"] = False; estado["pico"] = None
        decir("kill", "Kill switch rearmado. El fondo vuelve a operar.")

    # 1. Analista de datos
    tickers = {s: y for s, (y, _) in C.ACTIVOS.items()}
    tickers[C.LIQUIDEZ[0]] = C.LIQUIDEZ[1]
    tickers.update({s: y for s, (y, _) in C.CAZADOR.items()})
    tickers.update({y: y for (y, _, _) in C.FUTUROS.values()})
    tickers["EURUSD"] = "EURUSD=X"
    todo = datos.descargar(tickers)
    P = todo[list(C.ACTIVOS)].dropna(how="all")
    L = todo[C.LIQUIDEZ[0]].ffill()
    fecha = P.index[-1]
    precios = {s: float(todo[s].dropna().iloc[-1]) for s in tickers if todo[s].notna().any()}
    decir("analista", f"Precios al cierre del {fecha.date()} descargados ({len(P.columns)} activos).")

    # 2-3. Macro, traders y riesgos
    p = dict(E.PARAMS); p["vol_objetivo"] = C.PERFILES[C.PERFIL]
    P_ok = P.dropna(axis=1, thresh=300)
    pesos = E.pesos_en(P_ok, fecha, p)
    notas = E.notas(P_ok, p).iloc[-1]
    alcistas = int((notas == 1).sum()); total = int(notas.notna().sum())
    regimen = "favorable" if alcistas >= total * 0.6 else "mixto" if alcistas >= total * 0.3 else "defensivo"
    decir("macro", f"Régimen {regimen}: {alcistas} de {total} activos en tendencia alcista clara.")
    for f in E.explicar(P_ok, fecha, p):
        decir("trader", f)
    invertido = sum(pesos.values())
    decir("riesgos", f"Perfil {C.PERFIL}: {invertido * 100:.0f} % de la parte principal invertido, {max(0, 100 - invertido * 100):.0f} % en liquidez.")

    # 4. Broker y kill switch
    broker = BrokerVirtual(estado) if a.virtual else (BrokerAlpaca() if C.BROKER == "alpaca" else BrokerIBKR())
    try:
        valor = broker.valor(precios)
        estado["pico"] = max(estado["pico"] or valor, valor)
        caida = 1 - valor / estado["pico"]
        if not estado["kill"] and caida > C.KILL_DD:
            estado["kill"] = True
            decir("kill", f"¡KILL SWITCH! La cuenta cae un {caida * 100:.1f} % desde su máximo. Todo a liquidez hasta que alguien revise y ejecute --reabrir.")
        if estado["kill"]:
            pesos = {}
            decir("kill", "Kill switch activo: no se compra nada de riesgo.")

        # la cartera principal usa el capital que no reserva el cazador
        base = 1 - C.CAZADOR_TOPE - C.COLCHON_LIQUIDEZ
        objetivo = {s: round(w * base, 4) for s, w in pesos.items()}
        objetivo[C.LIQUIDEZ[0]] = round(max(0.0, base - sum(objetivo.values())), 4)
        propios = set(C.ACTIVOS) | {C.LIQUIDEZ[0]}

        # 6. Ejecución (una vez por semana salvo kill switch o --forzar)
        semana = f"{fecha.isocalendar().year}-{fecha.isocalendar().week}"
        toca = a.forzar or estado.get("ultimo_rebalanceo") != semana or estado["kill"]
        posiciones = {k: v for k, v in broker.posiciones().items() if k in propios}
        ordenes = planificar(objetivo, valor, posiciones, precios) if toca else []
        hechas = broker.ejecutar(ordenes, precios) if ordenes else []
        if toca:
            estado["ultimo_rebalanceo"] = semana
        if hechas:
            for o in hechas:
                decir("ejecucion", f"{'Compro' if o['lado'] == 'BUY' else 'Vendo'} {o['cantidad']} {o['simbolo']} (límite {o['limite']} €): {o['estado']}.")
        else:
            decir("ejecucion", "Cartera principal: sin órdenes, ya está donde debe." if toca else "Cartera principal: ya se rebalanceó esta semana.")

        # 6b. Cazador diario de tendencias (parte satélite)
        cartera = estado.setdefault("cazador", {})
        reales = broker.posiciones()
        for sim in list(cartera):  # lo que el bróker no tiene, fuera
            if reales.get(sim, 0) <= 0:
                cartera.pop(sim)
            else:
                cartera[sim]["cantidad"] = reales[sim]
        Pc = todo[[s for s in C.CAZADOR if s in todo and todo[s].notna().sum() > 260]]
        if estado["kill"]:
            ventas = [{"simbolo": sim, "cantidad": pos["cantidad"], "precio": precios[sim], "motivo": "kill switch", "resultado_%": None} for sim, pos in cartera.items()]
            compras, candidatos, notas_caz = [], [], []
            cartera.clear()
        else:
            previo = estado["historia"][-1]["valor"] if estado["historia"] else None
            freno = bool(previo) and valor < previo * (1 - C.LIMITE_PERDIDA_DIA)
            if freno:
                decir("riesgos", f"Límite diario: la cuenta cae {(1 - valor / previo) * 100:.1f} % desde ayer. Hoy no se abren posiciones nuevas.")
            ventas, compras, candidatos, notas_caz = K.gestionar(Pc, cartera, valor, C.CAZADOR_TOPE, entero=not C.FRACCIONES, sin_compras=freno, subtopes={"cripto": (set(C.CRIPTO), C.CRIPTO_TOPE), "baja": (set(C.INVERSOS), C.INVERSOS_TOPE)})
        ordenes_caz = [{"simbolo": v["simbolo"], "lado": "SELL", "cantidad": v["cantidad"], "limite": round(v["precio"] * (1 - C.MARGEN_LIMITE), 2), "importe": round(v["cantidad"] * v["precio"], 2)} for v in ventas] + \
                      [{"simbolo": c["simbolo"], "lado": "BUY", "cantidad": c["cantidad"], "limite": round(c["precio"] * (1 + C.MARGEN_LIMITE), 2), "importe": round(c["cantidad"] * c["precio"], 2)} for c in compras]
        hechas_caz = broker.ejecutar(ordenes_caz, precios) if ordenes_caz else []
        for o in hechas_caz:
            if o["lado"] == "BUY" and ("sin efectivo" in o["estado"] or o["estado"].startswith("error")):
                cartera.pop(o["simbolo"], None)
        n_tend = len(candidatos)
        decir("analista", f"Cazador: {len(Pc.columns)} ETF revisados, {n_tend} en tendencia alcista clara" + (f" (el mejor, {candidatos[0]['simbolo']}: {C.CAZADOR[candidatos[0]['simbolo']][1]}, +{candidatos[0]['momentum_6m_%']} % en 6 meses)." if candidatos else "."))
        for v in ventas:
            decir("riesgos", f"Cazador vende {v['simbolo']}: {v['motivo']}" + (f" ({v['resultado_%']:+.1f} %)." if v["resultado_%"] is not None else "."))
        for c in compras:
            decir("prevision", f"Cazador compra {c['cantidad']} {c['simbolo']} ({C.CAZADOR[c['simbolo']][1]}): {c['motivo']}. Stop en {c['stop']:.2f} €.")
        for n in notas_caz[:3]:
            decir("prevision", n)
        if not ventas and not compras:
            decir("prevision", f"Cazador: sin cambios hoy. Posiciones abiertas: {', '.join(cartera) or 'ninguna'}.")
        hechas = hechas + hechas_caz
        # 6c. Mesa de futuros (solo plan)
        try:
            fx = float(todo["EURUSD"].dropna().iloc[-1]) if "EURUSD" in todo and todo["EURUSD"].notna().any() else 1.1
            plan_fut = FUT.plan(todo, valor, fx)
            activos_fut = [f for f in plan_fut if f["lado"] in ("LARGO", "CORTO") and f["contratos"] > 0]
            decir("macro", "Futuros (solo plan): " + (", ".join(f"{f['simbolo']} {f['lado'].lower()} {f['contratos']}" for f in activos_fut) if activos_fut else "nada cabe con el riesgo permitido o no hay tendencia clara") + ".")
        except Exception as e:
            plan_fut = []; print(f"Aviso: la mesa de futuros falló ({e}).")
        valor_fin = broker.valor(precios)
        posiciones = broker.posiciones()
    finally:
        broker.cerrar()
        ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False))  # guardar ya, pase lo que pase después

    # 5. Comité: incubadora (fuera de muestra) contra la principal
    try:
        r_principal, _ = E.backtest(P_ok, L.pct_change().fillna(0), p=p, desde=P_ok.index[-1] - pd.Timedelta(days=800))
        filas = incubadora.evaluar(P_ok, L, estado["altas_incubadora"], p, r_principal)
    except Exception as e:
        print(f"Aviso: la revisión de la incubadora falló ({e}); el resto del fondo sigue.")
        filas = []
    propuestas = [f["nombre"] for f in filas if f["propuesta_ascenso"]]
    decir("comite", ("Propongo ascender: " + ", ".join(propuestas) + ". Revísalo antes de cambiar nada.") if propuestas
          else f"Incubadora: {len(filas)} candidatas en observación. Ninguna supera aún a la principal con un año de datos nuevos.")

    # 7. Informe
    estado["historia"].append({"fecha": str(fecha.date()), "valor": round(valor_fin, 2)})
    estado["historia"] = estado["historia"][-600:]
    ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False))
    nuevo = not REGISTRO.exists()
    with REGISTRO.open("a", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["fecha", "cuenta", "simbolo", "lado", "cantidad", "limite", "importe", "estado"])
        for o in hechas:
            w.writerow([datetime.now().isoformat(timespec="seconds"), broker.cuenta, o["simbolo"], o["lado"], o["cantidad"], o["limite"], o["importe"], o["estado"]])

    resumen = {
        "fecha": str(fecha.date()), "generado": datetime.now().isoformat(timespec="seconds"),
        "modo": "virtual" if a.virtual else (f"{C.BROKER.upper()} demo · prueba" if C.MODO_PRUEBA else f"{C.BROKER.upper()} demo"),
        "cuenta": broker.cuenta, "perfil": C.PERFIL, "valor": round(valor_fin, 2),
        "pico": round(estado["pico"], 2), "kill": estado["kill"], "regimen": regimen,
        "pesos": objetivo, "posiciones": posiciones, "ordenes": hechas, "voz": voz,
        "incubadora": filas, "historia": estado["historia"],
        "futuros": plan_fut, "grupos": {"cripto": list(C.CRIPTO), "baja": list(C.INVERSOS)},
        "limites": {"cripto": C.CRIPTO_TOPE, "baja": C.INVERSOS_TOPE, "dia": C.LIMITE_PERDIDA_DIA, "kill": C.KILL_DD, "toma": K.PARAMS.get("toma_beneficio")},
        "cazador": {"cartera": estado.get("cazador", {}), "candidatos": candidatos[:8], "tope": C.CAZADOR_TOPE},
        "nombres": {s: d for s, (_, d) in C.ACTIVOS.items()} | {s: d for s, (_, d) in C.CAZADOR.items()} | {C.LIQUIDEZ[0]: C.LIQUIDEZ[2]},
    }
    OFICINA.parent.mkdir(exist_ok=True)
    OFICINA.write_text("window.ESTADO_REAL = " + json.dumps(resumen, ensure_ascii=False, default=str) + ";\n")
    lineas = [f"# Informe del fondo · {fecha.date()}", "",
              f"- Modo: {resumen['modo']} · cuenta {broker.cuenta} · perfil {C.PERFIL}",
              f"- Valor: {valor_fin:,.2f} € · máximo {estado['pico']:,.2f} € · kill switch {'ACTIVO' if estado['kill'] else 'no'}", "",
              "## Pesos objetivo", ""] + [f"- {s} ({resumen['nombres'].get(s, '')}): {w * 100:.1f} %" for s, w in objetivo.items()] + \
             ["", "## La oficina dice", ""] + [f"- **{v['quien']}**: {v['texto']}" for v in voz] + \
             ["", "## Incubadora (desde su alta, fuera de muestra)", "",
              "| Estrategia | Alta | Sesiones | Resultado | Sharpe | Caída máx. | Sharpe histórico* |", "|---|---|---|---|---|---|---|"] + \
             [f"| {f['nombre']} | {f['alta']} | {f['sesiones']} | {f['resultado_%']} % | {f.get('sharpe', '–')} | {f.get('caida_max_%', '–')} % | {f['historico'].get('sharpe', '–')} |" for f in filas] + \
             ["", "*Histórico = antes de entrar en la incubadora. Orientativo: para ascender solo cuenta lo de después.",
              "", f"## Cazador de tendencias (tope {C.CAZADOR_TOPE * 100:.0f} % del capital)", ""] + \
             [f"- {sim}: {pos['cantidad']} desde {pos['fecha']} a {pos['entrada']:.2f} €, stop {pos['stop']:.2f} €" for sim, pos in estado.get("cazador", {}).items()] + \
             (["", "Candidatos de hoy: " + ", ".join(f"{c['simbolo']} (+{c['momentum_6m_%']} % 6m)" for c in candidatos[:8])] if candidatos else [])
    INFORME.write_text("\n".join(lineas) + "\n")
    print(f"\nListo. Informe en {INFORME.name}; la oficina visual lo mostrará en la pestaña Real.")


if __name__ == "__main__":
    main()
