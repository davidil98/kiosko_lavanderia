#!/bin/bash

# Obtener la ruta absoluta del directorio del proyecto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

# Ruta al escritorio del usuario
DESKTOP_FILE="$HOME/Desktop/KioskoEcoLuna.desktop"

VENV_DIR=".venv"
# Crear el contenido del archivo .desktop
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Kiosko EcoLuna
Comment=Inicia el servidor NiceGUI y abre Chromium en modo kiosko
Exec=bash -c "cd $PROJECT_DIR && source $VENV_DIR/bin/activate && python3 src/web_app/main.py & sleep 4 && chromium-browser --kiosk --window-position=0,0 --noerrdialogs --disable-infobars --no-first-run --incognito http://localhost:8000 --new-window --window-position=1024,0 http://localhost:8000/admin"
Terminal=true
Icon=$PROJECT_DIR/media/logo_slogan.png
Categories=Utility;Application;
EOF

# Dar permisos de ejecución al archivo .desktop
chmod +x "$DESKTOP_FILE"

echo "-- Acceso directo creado en: $DESKTOP_FILE"
echo "Puedes darle doble clic para iniciar todo el sistema."
