# Fondo real automatizado

La oficina, pero de verdad: cada semana descarga precios reales, decide la cartera y manda las órdenes a tu **cuenta demo de Interactive Brokers**. Mientras `SOLO_DEMO = True` se niega a tocar una cuenta real. El paso a dinero real lo decides tú cuando la demo lleve meses funcionando.

## Qué hace cada lunes
| Bot | Tarea |
|---|---|
| Analista | Descarga cierres ajustados de 6 ETF UCITS de Xetra (bolsa mundial, S&P 500, Nasdaq-100, emergentes, oro y bonos euro) y un monetario. |
| Traders de tendencia | Dan a cada activo una nota de 0 a 4: precio sobre su media de 200 sesiones y rentabilidad positiva a 3, 6 y 12 meses. |
| Riesgos | Reparte el peso por volatilidad, apunta a una volatilidad anual del 12 % (perfil equilibrado) y no deja que un activo pase del 40 %. |
| Macro | Resume el régimen: favorable, mixto o defensivo. |
| Kill switch | Si la cuenta cae un 15 % desde su máximo, lo pasa todo a liquidez y para hasta que tú lo rearmes. |
| Ejecución | Calcula participaciones enteras, vende primero, compra después, órdenes limitadas al ±0,4 %. Lo que no se invierte va al monetario XEON, que paga el tipo del BCE. |
| Comité | Sigue en la sombra 5 estrategias candidatas desde el día que entran. Si alguna gana a la principal tras un año de datos nuevos, te propone ascenderla. |

## Por qué esta estrategia y no las de la oficina simulada
La probé con 20 años de datos reales del S&P 500 y el Nasdaq-100 (1999-2018, incluye las crisis de 2000 y 2008), con dividendos, intereses de la liquidez y comisiones:

| | Rent. anual | Caída máxima | Sharpe |
|---|---|---|---|
| Comprar y mantener | 4,4 % | −64 % | 0,31 |
| Esta estrategia (10 % de volatilidad) | 5,9 % | −15 % | 0,69 |
| Esta estrategia (15 % de volatilidad) | 7,4 % | −24 % | 0,64 |

En la década alcista 2009-2018 ganó menos que comprar y mantener (8,5 % frente a 14,7 % al año): es el precio del seguro. RSI-2 e IBS, en cambio, perdieron casi toda su ventaja después de 2009, así que se quedan en la incubadora y no mueven dinero.

## Puesta en marcha
1. Ten la cuenta de IBKR con la demo activada e **IB Gateway** abierto en *Paper Trading*, puerto 4002 (igual que en `../../bot-ibkr/LEEME.md`).
2. Instala Python 3.10 o superior y, en esta carpeta:
   ```
   pip install -r requirements.txt
   ```
3. Antes de nada, mira el backtest con los precios reales de los ETF:
   ```
   python backtest.py
   ```
4. Primera pasada sin bróker (cartera virtual de 10.000 € con precios reales):
   ```
   python fondo.py --virtual
   ```
5. Con IB Gateway abierto: `python fondo.py`. Con `MODO_PRUEBA = True` solo apunta las órdenes. Cuando lo veas bien, pon `MODO_PRUEBA = False` en `config.py` y enviará órdenes a la demo.

Cada pasada deja `informe.md`, `registro.csv` y actualiza la pestaña **Real** de `../oficina.html`.

## Programarlo cada lunes a las 10:00
- **Mac/Linux**: `crontab -e` y añade
  `0 10 * * 1 cd /ruta/oficina-trading/real && python3 fondo.py >> fondo.log 2>&1`
- **Windows**: Programador de tareas > Crear tarea básica > Semanal, lunes 10:00 > programa `python`, argumentos `fondo.py`, iniciar en esta carpeta.
- IB Gateway tiene que estar abierto con sesión iniciada. Si se cae, el fondo no envía nada y lo dirá en el log.

## Ajustes (config.py)
| Ajuste | Para qué |
|---|---|
| `PERFIL` | `prudente` (8 %), `equilibrado` (12 %) o `dinamico` (15 %) de volatilidad anual |
| `KILL_DD` | Caída que dispara el kill switch. Tras revisarlo: `python fondo.py --reabrir` |
| `MODO_PRUEBA` | `False` para enviar órdenes a la demo |
| `SOLO_DEMO` | Dejar en `True`. Pasar a real es una decisión tuya, después de meses de demo |
| `MIN_ORDEN_EUR` | Ajustes más pequeños no se ejecutan. Con menos de unos 3.000 € las comisiones mínimas (unos 3 € por orden) pesan mucho |

## Lo que no hace
- No promete rentabilidad. Busca ganar parecido a la bolsa con mucha menos caída en las crisis.
- No opera a diario ni en corto: menos comisiones, menos impuestos y nada de apalancamiento.
- Impuestos en España: cada venta con ganancia tributa en la base del ahorro. Un fondo de inversión no tributa al traspasar; estos ETF sí al vender.
