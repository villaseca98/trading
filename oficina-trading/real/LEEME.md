# Fondo real automatizado

La oficina, pero de verdad: cada día laborable descarga precios reales, decide y manda las órdenes a tu **cuenta demo de Interactive Brokers**. Tiene dos partes: la **cartera principal** (80 %, se rebalancea una vez por semana) y el **cazador de tendencias** (hasta el 20 %, revisa entradas y stops a diario). Mientras `SOLO_DEMO = True` se niega a tocar una cuenta real. El paso a dinero real lo decides tú cuando la demo lleve meses funcionando.

## Qué hace cada día
| Bot | Tarea |
|---|---|
| Analista | Descarga cierres ajustados de 6 ETF UCITS de Xetra (bolsa mundial, S&P 500, Nasdaq-100, emergentes, oro y bonos euro) y un monetario. |
| Traders de tendencia | Dan a cada activo una nota de 0 a 4: precio sobre su media de 200 sesiones y rentabilidad positiva a 3, 6 y 12 meses. |
| Riesgos | Reparte el peso por volatilidad, apunta a una volatilidad anual del 12 % (perfil equilibrado) y no deja que un activo pase del 40 %. |
| Macro | Resume el régimen: favorable, mixto o defensivo. |
| Kill switch | Si la cuenta cae un 15 % desde su máximo, lo pasa todo a liquidez y para hasta que tú lo rearmes. |
| Ejecución | Calcula participaciones enteras, vende primero, compra después, órdenes limitadas al ±0,4 %. Lo que no se invierte va al monetario XEON, que paga el tipo del BCE. |
| Analista (cazador) | Cada día revisa 13 ETF/ETN de sectores, países y temas (semiconductores, IA, defensa, bancos, India, bitcoin…) y apunta los que están en tendencia alcista clara: precio sobre la media 50, media 50 sobre la 200, subiendo a 3 y 6 meses y cerca de máximos de un año. |
| Previsión | Para cada candidato mira qué pasó en su historial las otras veces que estuvo igual: si en las 20 sesiones siguientes acertó menos del 55 % o de media perdió, lo descarta. |
| Riesgos (cazador) | Cada posición arriesga como mucho el 1 % del capital hasta su stop (5 movimientos diarios medios por debajo), ninguna pasa del 10 % y el cazador entero no pasa del 20 %. El stop sube con el precio y nunca baja. |
| Comité | Sigue en la sombra 5 estrategias candidatas desde el día que entran. Si alguna gana a la principal tras un año de datos nuevos, te propone ascenderla. |

## Por qué esta estrategia y no las de la oficina simulada
La probé con 20 años de datos reales del S&P 500 y el Nasdaq-100 (1999-2018, incluye las crisis de 2000 y 2008), con dividendos, intereses de la liquidez y comisiones:

| | Rent. anual | Caída máxima | Sharpe |
|---|---|---|---|
| Comprar y mantener | 4,4 % | −64 % | 0,31 |
| Esta estrategia (10 % de volatilidad) | 5,9 % | −15 % | 0,69 |
| Esta estrategia (15 % de volatilidad) | 7,4 % | −24 % | 0,64 |

El cazador lo probé con S&P 500, Nasdaq y petróleo (1999-2018): con stop amplio sus operaciones ganaron de media un +0,5 % con un 49 % de acierto. Es una ventaja pequeña: las ganancias vienen de pocas operaciones grandes, por eso arriesga poco en cada una y solo una parte del capital. Con los 13 ETF reales mídelo tú con la demo antes de subir el tope.

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

## Programarlo cada día laborable a las 10:30
- **Mac/Linux**: `crontab -e` y añade
  `30 10 * * 1-5 cd /ruta/oficina-trading/real && python3 fondo.py >> fondo.log 2>&1`
- **Windows**: Programador de tareas > Crear tarea básica > Semanal, marca de lunes a viernes, 10:30 > programa `python`, argumentos `fondo.py`, iniciar en esta carpeta.
- Las señales usan el cierre del día anterior y las órdenes salen con Xetra abierta.
- IB Gateway tiene que estar abierto con sesión iniciada. Si se cae, el fondo no envía nada y lo dirá en el log.

## Ajustes (config.py)
| Ajuste | Para qué |
|---|---|
| `CAZADOR_TOPE` | Parte del capital que puede usar el cazador (0,20 = 20 %) |
| `CAZADOR` | Lista de ETF que vigila el cazador. Puedes añadir más con su ticker de Yahoo |
| `PERFIL` | `prudente` (8 %), `equilibrado` (12 %) o `dinamico` (15 %) de volatilidad anual |
| `KILL_DD` | Caída que dispara el kill switch. Tras revisarlo: `python fondo.py --reabrir` |
| `MODO_PRUEBA` | `False` para enviar órdenes a la demo |
| `SOLO_DEMO` | Dejar en `True`. Pasar a real es una decisión tuya, después de meses de demo |
| `MIN_ORDEN_EUR` | Ajustes más pequeños no se ejecutan. Con menos de unos 3.000 € las comisiones mínimas (unos 3 € por orden) pesan mucho |

## Pasar a dinero real
Solo cuando la demo lleve meses funcionando y el registro te convenza:
1. En IBKR, cuenta real abierta y con dinero, y los **datos de mercado de Xetra** contratados (unos pocos euros al mes; sin ellos las órdenes salen a ciegas).
2. IB Gateway iniciado en modo **Live** (no Paper). En `config.py`: `PUERTO = 4001`, `SOLO_DEMO = False` y `MODO_PRUEBA = False`.
3. Crea en esta carpeta un archivo `CONFIRMO_DINERO_REAL.txt` con la frase `Acepto el riesgo`. Sin las tres cosas el fondo se niega a operar en una cuenta real.
4. En real hay un tope de compras por día (`LIMITE_COMPRAS_DIA_REAL`, 2.000 € por defecto). Empieza con poco dinero y súbelo poco a poco.
5. IB Gateway pide volver a iniciar sesión cada semana (y la verificación en el móvil). Si no lo haces, el fondo no puede operar y lo verás en `fondo.log`.

## Lo que no hace
- No promete rentabilidad. Busca ganar parecido a la bolsa con mucha menos caída en las crisis.
- No opera en corto ni con apalancamiento. La parte principal se mueve una vez por semana para gastar poco en comisiones.
- Impuestos en España: cada venta con ganancia tributa en la base del ahorro. Un fondo de inversión no tributa al traspasar; estos ETF sí al vender.
