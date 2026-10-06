// Genera oficina.html (página completa para abrir con doble clic) a partir de index.html.
const fs = require('fs'), path = require('path');
const dir = __dirname, cuerpo = fs.readFileSync(path.join(dir, 'index.html'), 'utf8');
fs.writeFileSync(path.join(dir, 'oficina.html'),
  '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n</head>\n<body>\n' + cuerpo + '\n</body>\n</html>\n');
console.log('oficina.html listo');
