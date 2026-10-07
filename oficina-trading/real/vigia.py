"""
Vigía de Trade Republic: Trade Republic no deja que un programa compre, así que la oficina
vigila tu lista de ETF y acciones y te AVISA cuando hay una oportunidad. Tú compras con un toque.

Avisa cuando:
  - Un ETF índice cae un 10, 20 o 30 % desde su máximo del último año (compra extra de acumulación).
  - Una acción de calidad cae un 15, 25 o 35 % (las acciones solas se mueven más) y su media
    de 200 sesiones sigue subiendo (caída dentro de una tendencia sana, no un derrumbe).
  - Cada nivel avisa una sola vez; se rearma cuando el activo recupera su máximo.
Recordatorio: los planes de inversión de Trade Republic son gratis; una orden suelta cuesta 1 €.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import datos

AQUI = Path(__file__).resolve().parent
ESTADO = AQUI / "estado_vigia.json"
OFICINA = AQUI.parent / "datos" / "vigia.js"

# símbolo en Yahoo: (nombre, tipo)
LISTA = {
    "SXR8.DE": ("Core S&P 500 (Acc)", "ETF"),
    "SXRV.DE": ("Nasdaq-100 (Acc)", "ETF"),
    "EUNL.DE": ("Core MSCI World (Acc)", "ETF"),
    "IS3N.DE": ("Core MSCI EM IMI (Acc)", "ETF"),
    "NVDA": ("NVIDIA", "Acción"), "AVGO": ("Broadcom", "Acción"), "TSM": ("TSMC", "Acción"),
    "ASML": ("ASML", "Acción"), "AMAT": ("Applied Materials", "Acción"), "META": ("Meta Platforms", "Acción"),
    "NOW": ("ServiceNow", "Acción"), "SAP": ("SAP", "Acción"), "MA": ("Mastercard", "Acción"),
    "COST": ("Costco", "Acción"), "PG": ("Procter & Gamble", "Acción"), "LLY": ("Eli Lilly", "Acción"),
    "SU.PA": ("Schneider Electric", "Acción"), "SE": ("Sea", "Acción"), "WIX": ("Wix", "Acción"),
    "AAPL": ("Apple", "Acción"),
}
NIVELES = {"ETF": (0.10, 0.20, 0.30), "Acción": (0.15, 0.25, 0.35)}


def avisar(titulo, texto):
    """Notificación en el Mac (si no es un Mac, solo imprime)."""
    print(f"🔔 {titulo}: {texto}")
    if sys.platform == "darwin":
        t = texto.replace('"', "'"); ti = titulo.replace('"', "'")
        subprocess.run(["osascript", "-e", f'display notification "{t}" with title "{ti}" sound name "Glass"'], check=False)


def revisar(P, avisados):
    filas, nuevos = [], []
    for s, (nombre, tipo) in LISTA.items():
        if s not in P or P[s].dropna().size < 260:
            continue
        c = P[s].dropna()
        px = float(c.iloc[-1]); maximo = float(c.iloc[-252:].max())
        m200 = c.rolling(200).mean()
        sana = bool(m200.iloc[-1] > m200.iloc[-21])  # la media de 200 sube en el último mes
        caida = 1 - px / maximo
        nivel = sum(caida >= n for n in NIVELES[tipo])
        if caida < 0.03:
            avisados[s] = 0
        estado = "en máximos" if caida < 0.03 else f"−{caida * 100:.0f} % desde máximo"
        if nivel > avisados.get(s, 0) and (tipo == "ETF" or sana):
            fuerza = ["", "compra extra pequeña", "compra extra mediana", "compra extra grande"][nivel]
            nuevos.append({"simbolo": s, "nombre": nombre, "texto": f"{nombre} cae un {caida * 100:.0f} % desde su máximo del año. Oportunidad: {fuerza}."})
            avisados[s] = nivel
        elif nivel and tipo == "Acción" and not sana:
            estado += " · tendencia rota, no avisa"
        filas.append({"simbolo": s, "nombre": nombre, "tipo": tipo, "precio": round(px, 2), "caida": round(caida * 100, 1), "estado": estado, "nivel": nivel})
    return filas, nuevos


def main():
    est = json.loads(ESTADO.read_text()) if ESTADO.exists() else {"avisados": {}, "log": []}
    P = datos.descargar({s: s for s in LISTA}, años=2)
    filas, nuevos = revisar(P, est["avisados"])
    hoy = f"{datetime.now():%Y-%m-%d %H:%M}"
    for n in nuevos:
        avisar("Oportunidad en Trade Republic", n["texto"])
        est["log"].append(f"{hoy} {n['texto']}")
    if not nuevos:
        print("Vigía: sin oportunidades nuevas hoy.")
    est["log"] = est["log"][-200:]
    ESTADO.write_text(json.dumps(est, indent=2, ensure_ascii=False))
    OFICINA.parent.mkdir(exist_ok=True)
    OFICINA.write_text("window.VIGIA = " + json.dumps({"fecha": hoy, "filas": sorted(filas, key=lambda f: -f["caida"]), "log": est["log"][-30:]}, ensure_ascii=False) + ";\n")


if __name__ == "__main__":
    main()
