#!/bin/bash
# Instala el fondo en el Mac y lo programa de lunes a viernes a las 10:30.
# Uso (en Terminal): curl -fsSL https://raw.githubusercontent.com/villaseca98/trading/main/instalar_mac.sh | bash
set -e
DIR="$HOME/trading"
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull -q; else git clone -q https://github.com/villaseca98/trading.git "$DIR"; fi
cd "$DIR/oficina-trading/real"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
PLIST="$HOME/Library/LaunchAgents/com.loco.fondo.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.loco.fondo</string>
<key>WorkingDirectory</key><string>$DIR/oficina-trading/real</string>
<key>ProgramArguments</key><array><string>$DIR/oficina-trading/real/.venv/bin/python</string><string>fondo.py</string></array>
<key>StartCalendarInterval</key><array>
$(for d in 1 2 3 4 5; do echo "<dict><key>Weekday</key><integer>$d</integer><key>Hour</key><integer>10</integer><key>Minute</key><integer>30</integer></dict>"; done)
</array>
<key>StandardOutPath</key><string>$DIR/oficina-trading/real/fondo.log</string>
<key>StandardErrorPath</key><string>$DIR/oficina-trading/real/fondo.log</string>
</dict></plist>
P
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
# mesa rápida de cripto: cada hora (solo hace algo si el bróker es Alpaca)
PR="$HOME/Library/LaunchAgents/com.loco.rapido.plist"
cat > "$PR" <<Q
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.loco.rapido</string>
<key>WorkingDirectory</key><string>$DIR/oficina-trading/real</string>
<key>ProgramArguments</key><array><string>/bin/sh</string><string>-c</string><string>[ "\$(cat broker.txt 2>/dev/null)" = alpaca ] &amp;&amp; .venv/bin/python rapido.py</string></array>
<key>StartInterval</key><integer>3600</integer>
<key>StandardOutPath</key><string>$DIR/oficina-trading/real/rapido.log</string>
<key>StandardErrorPath</key><string>$DIR/oficina-trading/real/rapido.log</string>
</dict></plist>
Q
launchctl unload "$PR" 2>/dev/null || true
launchctl load "$PR"
echo "Probando sin IBKR..."
[ -f broker.txt ] || .venv/bin/python fondo.py --virtual || true
echo "Listo. El fondo correrá de lunes a viernes a las 10:30 (con IB Gateway abierto en modo Paper)."
