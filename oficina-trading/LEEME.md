# Oficina de trading (Loco Capital)

Un fondo de **dinero simulado** (100.000 $) llevado entero por bots, cada uno con un papel. Nada de esto envía órdenes a ningún bróker.

## Abrirlo
- Doble clic en **oficina.html** (funciona sin internet salvo las fuentes).
- Por defecto usa un **mercado simulado** (regímenes alcista, lateral, bajista y crisis). Cada número de "Mercado simulado" en *Control* es un mercado distinto.

## Con precios reales
Necesitas Node 18 o superior (nodejs.org). En una terminal, dentro de esta carpeta:
```
node descargar.js
```
Descarga ~7 años de precios diarios de Yahoo y crea `datos/precios.js`. Al volver a abrir `oficina.html` la oficina reproduce los últimos ~2 años reales.

Para un informe rápido sin pantalla:
```
node correr.js                  # 3 años simulados
node correr.js --reales         # todo el histórico real
node correr.js --semilla 11     # otro mercado simulado
```

## Quién hace qué
| Sala | Bot | Tarea |
|---|---|---|
| Sala de trading | Traders | Cada uno sigue una estrategia conocida: cruce de medias, filtro 200 (Faber), RSI-2 (Connors), Bollinger, Donchian (Tortugas), momentum, MACD, IBS, ruptura de volatilidad (Williams) |
| Arbitraje | Traders de pares | Oro/plata, BTC/ETH, S&P/Nasdaq…: si se separan, compran el barato y venden el caro |
| Coberturas | Cobertura | En régimen bajista, cortos en S&P 500 por la mitad de la exposición a bolsa |
| Minería | Mineros | Prueban combinaciones al azar contra el histórico; pasan las de Sharpe > 0,7 |
| Mesa de pruebas | Incubadora | Las nuevas operan con dinero virtual; no cuenta en el fondo |
| Comité | 3 miembros | Cada 21 sesiones: asciende, degrada, despide y reparte capital |
| Riesgos | 2 | Tamaño por volatilidad, tope de exposición bruta, stop por operación |
| Macroeconomía | Economista | Régimen de mercado → cuánto se arriesga (100 % a 40 %) |
| Kill switch | Guardián | Si el fondo cae más del 10 % desde máximos, todo a liquidez |
| Equipo quant | Analista y ejecución | Informe semanal; órdenes en la apertura siguiente con comisión y deslizamiento |

## Archivos
- `engine.js`: el motor (estrategias, bots, fondo). Funciona en navegador y en Node.
- `index.html`: la oficina visual. `oficina.html` se genera con `node construir.js`.
- `descargar.js`, `correr.js`: datos reales e informe por terminal.

## Ojo
- El backtest de la minería busca entre muchas combinaciones, así que muchas "ganadoras" lo son por suerte. Por eso existe la incubadora: solo ascienden las que siguen funcionando con datos que no vieron.
- Resultados simulados no garantizan nada. Para pasar a una cuenta demo de IBKR, el siguiente paso sería conectar la "Ejecución" al bot de `../bot-ibkr`.
