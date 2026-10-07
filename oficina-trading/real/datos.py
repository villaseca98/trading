"""Analista de datos: descarga precios diarios ajustados (dividendos incluidos) de Yahoo."""
from pathlib import Path
import pandas as pd

CACHE = Path(__file__).resolve().parent / "datos" / "precios.csv"


def descargar(tickers: dict, años: int = 16) -> pd.DataFrame:
    """tickers = {simbolo_ibkr: ticker_yahoo}. Devuelve cierres ajustados por columna."""
    try:
        import yfinance as yf
        bruto = yf.download(list(tickers.values()), period=f"{años}y", interval="1d",
                            auto_adjust=True, progress=False, threads=False)
        cierres = bruto["Close"] if isinstance(bruto.columns, pd.MultiIndex) else bruto[["Close"]]
        inverso = {v: k for k, v in tickers.items()}
        cierres = cierres.rename(columns=inverso)[list(tickers)]
        cierres = cierres.dropna(how="all").ffill()
        if cierres.empty:
            raise RuntimeError("Yahoo no devolvió datos")
        CACHE.parent.mkdir(exist_ok=True)
        cierres.to_csv(CACHE)
        return cierres
    except Exception as e:  # sin internet o Yahoo caído: usamos la última copia
        if CACHE.exists():
            print(f"Aviso: no pude descargar ({e}). Uso la copia guardada.")
            return pd.read_csv(CACHE, index_col=0, parse_dates=True)
        raise
