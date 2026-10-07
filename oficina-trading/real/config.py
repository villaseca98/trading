"""Ajustes del fondo real. Lo normal es tocar solo PERFIL y, cuando toque, MODO_PRUEBA."""

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
    "DFNS": ("DFNS.DE", "Defensa"),
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
    "VSOL": ("VSOL.DE", "Solana (VanEck, ETN físico)"),
}
CRIPTO_TOPE = 0.10      # máximo del capital total en cripto (10 %), dentro del tope del cazador
CAZADOR.update(CRIPTO)

# ── Perfil de riesgo: volatilidad anual objetivo de la cartera
PERFILES = {"prudente": 0.08, "equilibrado": 0.12, "dinamico": 0.15}
PERFIL = "equilibrado"

# ── Riesgos
KILL_DD = 0.15          # si la cuenta cae un 15 % desde su máximo: todo a liquidez y se para
MAX_ORDEN_EUR = 25000.0 # tope de seguridad por orden (si una orden lo supera, se recorta)
MIN_ORDEN_EUR = 150.0   # no merece la pena mover menos (comisiones)
COLCHON_LIQUIDEZ = 0.02 # 2 % siempre en efectivo para comisiones
MARGEN_LIMITE = 0.004   # órdenes limitadas a ±0,4 % del último precio

# ── Conexión IBKR (IB Gateway en modo Paper Trading)
HOST = "127.0.0.1"
PUERTO = 4002           # IB Gateway demo = 4002 · TWS demo = 7497
CLIENT_ID = 23
MODO_PRUEBA = True      # True = calcula y apunta las órdenes pero no las envía
SOLO_DEMO = True        # True = se niega a operar si la cuenta no empieza por "DU"

# ── Dinero real. No tocar hasta llevar meses en la demo. Hacen falta LAS TRES cosas:
#   1. SOLO_DEMO = False
#   2. PUERTO = 4001 (IB Gateway iniciado en modo Live) o 7496 (TWS real)
#   3. Un archivo CONFIRMO_DINERO_REAL.txt en esta carpeta con la frase: Acepto el riesgo
LIMITE_COMPRAS_DIA_REAL = 2000.0  # en cuenta real, tope de compras por día (euros)

# ── Sin IBKR (python fondo.py --sin-ibkr): capital ficticio para ver qué haría
CAPITAL_FICTICIO = 10000.0
