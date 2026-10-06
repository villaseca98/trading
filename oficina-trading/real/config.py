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

# ── Sin IBKR (python fondo.py --sin-ibkr): capital ficticio para ver qué haría
CAPITAL_FICTICIO = 10000.0
