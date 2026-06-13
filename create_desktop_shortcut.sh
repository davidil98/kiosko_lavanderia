#!/bin/bash

# Obtener la ruta absoluta del directorio del proyecto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

# Rutas de los archivos a crear
DESKTOP_FILE="$HOME/Desktop/KioskoEcoLuna.desktop"
LAUNCHER_SCRIPT="$PROJECT_DIR/iniciar_kiosko.sh"

# 1. CREAR EL SCRIPT LANZADOR (El motor)
# Usamos \$! y \$PYTHON_PID para que las variables se guarden literal en el nuevo archivo
cat > "$LAUNCHER_SCRIPT" << EOF
#!/bin/bash

# Moverse al proyecto y activar entorno
cd "$PROJECT_DIR"
source .venv/bin/activate

# Arrancar NiceGUI en segundo plano y guardar su ID de proceso (PID)
python3 src/web_app/main.py &
PYTHON_PID=\$!

# Dar tiempo a que el servidor web despierte
sleep 4

# Arrancar Chromium (El script se quedará "pausado" aquí mientras Chromium esté abierto)
chromium-browser --kiosk --window-position=0,0 --noerrdialogs --disable-infobars --no-first-run --incognito http://localhost:8000 --new-window --window-position=1024,0 http://localhost:8000/admin

# Limpieza: Si alguien cierra Chromium (ej. Alt+F4), el script avanza y mata a Python
# Esto evita que queden procesos "fantasma" consumiendo RAM en la Raspberry
kill \$PYTHON_PID
EOF

# Dar permisos al lanzador
chmod +x "$LAUNCHER_SCRIPT"


# 2. CREAR EL ARCHIVO .DESKTOP (El botón visual)
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Kiosko EcoLuna
Comment=Inicia el servidor NiceGUI y abre Chromium en modo kiosko
Exec=bash "$LAUNCHER_SCRIPT"
Terminal=false
Icon=$PROJECT_DIR/media/logo_slogan.png
Categories=Utility;Application;
EOF

# Dar permisos de ejecución al archivo .desktop
chmod +x "$DESKTOP_FILE"

echo "-- Script lanzador creado en: $LAUNCHER_SCRIPT"
echo "-- Acceso directo creado en: $DESKTOP_FILE"
echo "Todo listo. El sistema ahora correrá de forma nativa sin que se cierre Python."