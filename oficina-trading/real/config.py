"""Ajustes del fondo real. Lo normal es tocar solo BROKER, PERFIL y, cuando toque, MODO_PRUEBA."""

from pathlib import Path as _P
_f = _P(__file__).resolve().parent / "broker.txt"  # archivo local (no se sube) para elegir bróker sin tocar este fichero
ESTRATEGIA = "tr_binance"   # "tr_binance" = vigía Trade Republic + cripto Binance · "dca" = Alpaca · "fondo" = sistema completo
BROKER = _f.read_text().strip() if _f.exists() else "ibkr"   # "ibkr" (ETF europeos en Xetra, euros) o "alpaca" (EE. UU., dólares, sin comisión, con fracciones)
FRACCIONES = False  # Alpaca permite comprar fracciones de acción; se activa solo abajo

# ── Activos (ETF UCITS que se pueden comprar desde España, en Xetra y en euros)
# simbolo IBKR: (ticker de Yahoo para los datos, descripción)
ACTIVOS = {
    "EUNL": ("EUNL.DE", "Bolsa mundial desarrollada (MSCI World)"),
    "SXR8": ("SXR8.DE", "Bolsa EE. UU. (S&P 500)"),
    "EQQQ": ("EQQQ.DE", "Tecnológicas EE. UU. (Nasdaq-100)"),
    "IS3N": ("IS3N.DE", "Bolsa emergente (MSCI EM IMI)"),
    "4GLD": ("4GLD.DE", "Oro físico (Xetra-Gold)"),
    "EUNH": ("EUNH.DE", "Bonos de gobiernos de la zona euro"),
}
ROLES = {"sp500": "SXR8", "emerg": "IS3N", "mundo": "EUNL", "bonos": "EUNH", "oro": "4GLD"}  # para la incubadora
LIQUIDEZ = ("XEON", "XEON.DE", "Monetario en euros (€STR)")  # donde se aparca lo no invertido
BOLSA = "IBIS"       # Xetra
DIVISA = "EUR"

# ── Cazador diario de tendencias: ETF/ETN de sectores, países y temas (Xetra, euros)
CAZADOR = {
    "SXRV": ("SXRV.DE", "Nasdaq-100"),
    "QDVE": ("QDVE.DE", "Tecnología EE. UU. (S&P 500 IT)"),
    "VVSM": ("VVSM.DE", "Semiconductores"),
    "XAIX": ("XAIX.DE", "Inteligencia artificial y big data"),
    "EXV3": ("EXV3.DE", "Tecnología europea"),
    "EXV1": ("EXV1.DE", "Bancos europeos"),
    "EXH1": ("EXH1.DE", "Petróleo y gas europeo"),
    "IQQH": ("IQQH.DE", "Energía limpia"),
    "G2X": ("G2X.DE", "Mineras de oro"),
    "QDV5": ("QDV5.DE", "India"),
    "EUNK": ("EUNK.DE", "Bolsa europea"),
}
CAZADOR_TOPE = 0.20     # parte del capital que puede usar el cazador (20 %)

# ── Cripto: ETN con respaldo físico en Xetra (se compran como un ETF desde IBKR España).
# Entran en el cazador: solo se compran en tendencia alcista, con stop y arriesgando 1 % por posición.
# Comprobar cada ticker en IBKR antes de la primera orden real.
CRIPTO = {
    "VBTC": ("VBTC.DE", "Bitcoin (VanEck, ETN físico)"),
    "VETH": ("VETH.DE", "Ethereum (VanEck, ETN físico)"),
}
CRIPTO_TOPE = 0.10      # máximo del capital total en cripto (10 %), dentro del tope del cazador
CAZADOR.update(CRIPTO)

# ── A la baja: ETF inversos (suben cuando el índice baja). Sin margen ni cortos: como mucho se pierde lo invertido.
# El cazador los compra solo cuando ESTÁN en tendencia alcista, es decir, cuando el índice lleva tiempo cayendo.
# Son diarios: en mercados laterales pierden valor, por eso tienen stop y tope propio. Verificar tickers en IBKR.
INVERSOS = {
    "DXSN": ("DXSN.DE", "DAX a la baja (Xtrackers ShortDAX)"),
    "DXS3": ("DXS3.DE", "S&P 500 a la baja (Xtrackers S&P 500 Inverse)"),
}
INVERSOS_TOPE = 0.10    # máximo del capital total en apuestas a la baja
CAZADOR.update(INVERSOS)

LIMITE_PERDIDA_DIA = 0.02  # si la cuenta cae más de un 2 % desde la última pasada, ese día no se compra nada nuevo

# ── Futuros micro (CME, en dólares). SOLO PLAN: calcula qué haría (largo o corto) y lo muestra,
# pero no envía ninguna orden. Activarlos de verdad exige cuenta de margen, permisos de futuros y meses de demo.
FUTUROS = {
    "MES": ("ES=F", 5.0, "S&P 500 micro"),
    "MNQ": ("NQ=F", 2.0, "Nasdaq-100 micro"),
    "MGC": ("GC=F", 10.0, "Oro micro"),
    "MBT": ("BTC=F", 0.1, "Bitcoin micro"),
}
FUTUROS_RIESGO = 0.01   # 1 % del capital en riesgo por contrato planificado

# ── Mesa rápida (rapido.py): compraventa de cripto cada hora en Alpaca
RAPIDO_TOPE = 0.10      # máximo del capital en la mesa rápida (subir si demuestra que gana en Paper)
RAPIDO_RIESGO = 0.005   # 0,5 % del capital en riesgo por operación

# ── Perfil de riesgo: volatilidad anual objetivo de la cartera
PERFILES = {"prudente": 0.08, "equilibrado": 0.12, "dinamico": 0.15}
PERFIL = "equilibrado"

# ── Riesgos
KILL_DD = 0.15          # si la cuenta cae un 15 % desde su máximo: todo a liquidez y se para
MAX_ORDEN_EUR = 25000.0 # tope de seguridad por orden (si una orden lo supera, se recorta)
MIN_ORDEN_EUR = 50.0   # no merece la pena mover menos (comisiones)
COLCHON_LIQUIDEZ = 0.02 # 2 % siempre en efectivo para comisiones
MARGEN_LIMITE = 0.004   # órdenes limitadas a ±0,4 % del último precio

# ── Conexión IBKR (IB Gateway en modo Paper Trading)
HOST = "127.0.0.1"
PUERTO = 4002           # IB Gateway demo = 4002 · TWS demo = 7497
CLIENT_ID = 23
MODO_PRUEBA = not (_P(__file__).resolve().parent / "enviar_ordenes.txt").exists()  # True = calcula y apunta las órdenes pero no las envía
SOLO_DEMO = True        # True = se niega a operar si la cuenta no empieza por "DU"

# ── Dinero real. No tocar hasta llevar meses en la demo. Hacen falta LAS TRES cosas:
#   1. SOLO_DEMO = False
#   2. PUERTO = 4001 (IB Gateway iniciado en modo Live) o 7496 (TWS real)
#   3. Un archivo CONFIRMO_DINERO_REAL.txt en esta carpeta con la frase: Acepto el riesgo
LIMITE_COMPRAS_DIA_REAL = 2000.0  # en cuenta real, tope de compras por día (euros)

# ── Sin IBKR (python fondo.py --sin-ibkr): capital ficticio para ver qué haría
CAPITAL_FICTICIO = 10000.0


# ── Universo para Alpaca (EE. UU., en dólares). Sustituye al de Xetra si BROKER = "alpaca".
if BROKER == "alpaca":
    DIVISA = "USD"; FRACCIONES = True
    ACTIVOS = {
        "URTH": ("URTH", "Bolsa mundial desarrollada (MSCI World)"),
        "SPY": ("SPY", "Bolsa EE. UU. (S&P 500)"),
        "QQQ": ("QQQ", "Tecnológicas EE. UU. (Nasdaq-100)"),
        "IEMG": ("IEMG", "Bolsa emergente"),
        "GLD": ("GLD", "Oro"),
        "IEF": ("IEF", "Bonos del Tesoro EE. UU. 7-10 años"),
    }
    ROLES = {"sp500": "SPY", "emerg": "IEMG", "mundo": "URTH", "bonos": "IEF", "oro": "GLD"}
    LIQUIDEZ = ("BIL", "BIL", "Letras del Tesoro EE. UU. 1-3 meses")
    CAZADOR = {
        "XLK": ("XLK", "Tecnología EE. UU."), "SMH": ("SMH", "Semiconductores"),
        "XLF": ("XLF", "Bancos y finanzas EE. UU."), "XLE": ("XLE", "Petróleo y gas EE. UU."),
        "ITA": ("ITA", "Defensa y aeroespacial"), "ICLN": ("ICLN", "Energía limpia"),
        "GDX": ("GDX", "Mineras de oro"), "INDA": ("INDA", "India"), "VGK": ("VGK", "Bolsa europea"),
        "XLV": ("XLV", "Salud EE. UU."), "XLI": ("XLI", "Industria EE. UU."),
    }
    CRIPTO = {"IBIT": ("IBIT", "Bitcoin (ETF spot)"), "ETHA": ("ETHA", "Ethereum (ETF spot)")}
    INVERSOS = {"SH": ("SH", "S&P 500 a la baja"), "PSQ": ("PSQ", "Nasdaq-100 a la baja")}
    CAZADOR.update(CRIPTO); CAZADOR.update(INVERSOS)
    MIN_ORDEN_EUR = 5.0   # sin comisión: se pueden mover importes pequeños
