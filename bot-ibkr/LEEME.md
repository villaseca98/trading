# Bot IBKR: aportación semanal con filtro de 200 días

## Qué hace
Cada semana suma 50 € a un bote. Si VWCE (ETF mundial, Xetra) cotiza por encima de su media de 200 sesiones, compra participaciones enteras con ese bote. Si cotiza por debajo, espera y acumula. Nunca vende.

Por defecto está en **modo prueba** (no envía órdenes, solo apunta lo que haría) y **solo funciona en cuenta demo**.

## Puesta en marcha (una vez)
1. Abre cuenta en Interactive Brokers. Cuando esté aprobada, en *Configuración > Cuenta > Paper Trading* activa la cuenta demo (su número empieza por `DU`).
2. Descarga e instala **IB Gateway** (versión "stable") desde la web de IBKR e inicia sesión eligiendo **Paper Trading**.
3. En IB Gateway: *Configure > Settings > API > Settings*: marca "Enable ActiveX and Socket Clients", deja el puerto en **4002** y añade `127.0.0.1` a "Trusted IPs".
4. Instala Python 3.10 o superior y luego, en una terminal:
   ```
   pip install ib_async
   ```
5. Prueba: `python bot.py`. Verás en pantalla lo que haría y se crearán `registro.csv` y `estado.json`.

## Ejecutarlo cada semana
- **Mac/Linux**: `crontab -e` y añade `0 16 * * 1 cd /ruta/bot-ibkr && python3 bot.py` (lunes a las 16:00, con Xetra abierta).
- **Windows**: Programador de tareas > Crear tarea básica > Semanal > programa `python`, argumento `bot.py`, iniciar en la carpeta del bot.
- IB Gateway tiene que estar abierto y con sesión iniciada a esa hora.

## Ajustes (arriba del todo en bot.py)
| Ajuste | Para qué |
|---|---|
| `APORTACION_SEMANAL` | Euros por semana |
| `MAX_ORDEN_EUR` | Tope por orden |
| `MODO_PRUEBA` | `False` para que envíe órdenes de verdad a la demo |
| `SOLO_DEMO` | Dejar en `True` hasta decidir pasar a dinero real |
| `SIMBOLO` / `BOLSA` | Cambiar de ETF (p. ej. `IWDA` en `AEB`) |

## Plan sugerido
1. Semanas 1-2: `MODO_PRUEBA = True`, comprobar que el registro tiene sentido.
2. Semanas 3-8: `MODO_PRUEBA = False` en la demo, ver órdenes reales simuladas.
3. Revisar juntos `registro.csv` antes de tocar dinero real.

## Notas
- Si no llegan precios, la demo puede necesitar datos de mercado de Xetra (suscripción de pocos euros al mes) o usar datos diferidos.
- Ninguna estrategia garantiza ganancias. Esta solo busca invertir con disciplina y evitar comprar en plena caída.
