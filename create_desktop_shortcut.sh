#!/bin/bash

# Obtener la ruta absoluta del directorio del proyecto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

# Ruta al escritorio del usuario
DESKTOP_FILE="$HOME/Desktop/KioskoEcoLuna.desktop"

# Crear el contenido del archivo .desktop
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Kiosko EcoLuna
Comment=Inicia el servidor NiceGUI y abre Chromium en modo kiosko
Exec=bash -c "cd $PROJECT_DIR && python3 src/web_app/main.py & sleep 4 && chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run --incognito http://localhost:8000"
Terminal=true
Icon=$PROJECT_DIR/media/logo_slogan.png
Categories=Utility;Application;
EOF

# Dar permisos de ejecución al archivo .desktop
chmod +x "$DESKTOP_FILE"

echo "-- Acceso directo creado en: $DESKTOP_FILE"
echo "Puedes darle doble clic para iniciar todo el sistema."
