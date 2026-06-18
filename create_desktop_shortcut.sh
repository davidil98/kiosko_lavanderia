#!/bin/bash

# Script para lanzar el kiosko EcoLuna en modo dual-pantalla.
# Pantalla 1 (cliente/touch): http://localhost:8000
# Pantalla 2 (admin/mostrador): http://localhost:8000/admin
#
# Uso:
#   ./create_desktop_shortcut.sh
#   Luego hacer doble clic en "Kiosko EcoLuna" del escritorio.

set -e

# ──────────────────────────────────────────────
#  CONFIGURACIÓN
# ──────────────────────────────────────────────
# Puedes sobreescribir estas variables en un archivo .kiosko_display_env
# o directamente aquí si xrandr no detecta bien tus pantallas.
#
# Formato: X,Y,W,H  (posición x, posición y, ancho, alto)
# CLIENT_DISPLAY="0,0,1024,768"
# ADMIN_DISPLAY="1024,0,1440,900"
# ──────────────────────────────────────────────

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
ENV_FILE="$PROJECT_DIR/.kiosko_display_env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

# ──────────────────────────────────────────────
#  DETECTAR PANTALLAS CON XRANDR
# ──────────────────────────────────────────────
detect_displays() {
    if ! command -v xrandr &> /dev/null; then
        echo "[WARN] xrandr no disponible. Usando valores por defecto."
        return 1
    fi

    # Obtener líneas activas con resolución y posición. Ejemplo:
    # HDMI-1 connected primary 1024x768+0+0
    # HDMI-2 connected 1024x768+1024+0
    mapfile -t displays < <(xrandr | grep ' connected ' | sort)

    local count=${#displays[@]}
    if [ "$count" -lt 2 ]; then
        echo "[WARN] Solo se detectó $count pantalla(s). Usando valores por defecto."
        return 1
    fi

    # Parsear primera pantalla (cliente)
    local d1="${displays[0]}"
    # Parsear segunda pantalla (admin)
    local d2="${displays[1]}"

    # Extraer W,H+X+Y con regex
    if [[ $d1 =~ ([0-9]+x[0-9]+\+[0-9]+\+[0-9]+) ]] && [[ $d2 =~ ([0-9]+x[0-9]+\+[0-9]+\+[0-9]+) ]]; then
        local geom1="${BASH_REMATCH[1]}"
        local geom2="${BASH_REMATCH[2]}"

        # geom1: 1024x768+0+0
        local w1=${geom1%x*}
        local rest1=${geom1#*x}
        local h1=${rest1%+*}
        local x1=${rest1#*+}
        x1=${x1%+*}
        local y1=${rest1##*+}

        local w2=${geom2%x*}
        local rest2=${geom2#*x}
        local h2=${rest2%+*}
        local x2=${rest2#*+}
        x2=${x2%+*}
        local y2=${rest2##*+}

        CLIENT_DISPLAY="${x1},${y1},${w1},${h1}"
        ADMIN_DISPLAY="${x2},${y2},${w2},${h2}"
        echo "[INFO] Pantalla cliente detectada: ${CLIENT_DISPLAY}"
        echo "[INFO] Pantalla admin detectada:   ${ADMIN_DISPLAY}"
        return 0
    fi

    return 1
}

# Si no están definidas, intentar detectar; si falla, usar defaults
if [ -z "$CLIENT_DISPLAY" ] || [ -z "$ADMIN_DISPLAY" ]; then
    detect_displays || {
        CLIENT_DISPLAY="0,0,1024,768"
        ADMIN_DISPLAY="1024,0,1440,900"
        echo "[INFO] Usando configuración por defecto:"
        echo "       Cliente: $CLIENT_DISPLAY"
        echo "       Admin:   $ADMIN_DISPLAY"
    }
fi

# Parsear displays
CLIENT_X=${CLIENT_DISPLAY%,*}
CLIENT_X=${CLIENT_X%%,*}
CLIENT_Y=${CLIENT_DISPLAY%,*}
CLIENT_Y=${CLIENT_Y##*,}
CLIENT_W=${CLIENT_DISPLAY#*,}
CLIENT_W=${CLIENT_W%%,*}
CLIENT_H=${CLIENT_DISPLAY##*,}

ADMIN_X=${ADMIN_DISPLAY%,*}
ADMIN_X=${ADMIN_X%%,*}
ADMIN_Y=${ADMIN_DISPLAY%,*}
ADMIN_Y=${ADMIN_Y##*,}
ADMIN_W=${ADMIN_DISPLAY#*,}
ADMIN_W=${ADMIN_W%%,*}
ADMIN_H=${ADMIN_DISPLAY##*,}

# ──────────────────────────────────────────────
#  CREAR SCRIPT LANZADOR
# ──────────────────────────────────────────────
DESKTOP_FILE="$HOME/Desktop/KioskoEcoLuna.desktop"
LAUNCHER_SCRIPT="$PROJECT_DIR/iniciar_kiosko.sh"

cat > "$LAUNCHER_SCRIPT" << EOF
#!/bin/bash

# Configuración detectada/generada
cd "$PROJECT_DIR"
source .venv/bin/activate

# Si existe entorno local, cargarlo
[ -f "$ENV_FILE" ] && source "$ENV_FILE"

# Arrancar NiceGUI en segundo plano
python3 src/web_app/main.py &
PYTHON_PID=\$!

# Esperar a que el servidor despierte
sleep 4

echo "[INFO] Abriendo ventana cliente en ${CLIENT_DISPLAY}"
chromium \\
    --user-data-dir="/tmp/chromium-ecoluna-client" \\
    --window-position=${CLIENT_X},${CLIENT_Y} \\
    --window-size=${CLIENT_W},${CLIENT_H} \\
    --kiosk \\
    --noerrdialogs \\
    --disable-infobars \\
    --no-first-run \\
    --incognito \\
    --disable-features=TranslateUI \\
    --app=http://localhost:8000 &
CLIENT_PID=\$!

sleep 2

echo "[INFO] Abriendo ventana admin en ${ADMIN_DISPLAY}"
chromium \\
    --user-data-dir="/tmp/chromium-ecoluna-admin" \\
    --window-position=${ADMIN_X},${ADMIN_Y} \\
    --window-size=${ADMIN_W},${ADMIN_H} \\
    --kiosk \\
    --noerrdialogs \\
    --disable-infobars \\
    --no-first-run \\
    --incognito \\
    --disable-features=TranslateUI \\
    --app=http://localhost:8000/admin &
ADMIN_PID=\$!

# Esperar a que CUALQUIERA de las dos ventanas se cierre para limpiar todo
wait \$CLIENT_PID
wait \$ADMIN_PID

echo "[INFO] Cerrando servidor NiceGUI..."
kill \$PYTHON_PID 2>/dev/null || true
EOF

chmod +x "$LAUNCHER_SCRIPT"

# ──────────────────────────────────────────────
#  CREAR ACCESO DIRECTO
# ──────────────────────────────────────────────
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Kiosko EcoLuna
Comment=Inicia el servidor NiceGUI y abre Chromium en modo kiosko dual-pantalla
Exec=bash "$LAUNCHER_SCRIPT"
Terminal=false
Icon=$PROJECT_DIR/media/logo_slogan.png
Categories=Utility;Application;
EOF

chmod +x "$DESKTOP_FILE"

echo ""
echo "✅ Script lanzador creado en: $LAUNCHER_SCRIPT"
echo "✅ Acceso directo creado en:  $DESKTOP_FILE"
echo ""
echo "Pantallas configuradas:"
echo "  Cliente (touch): $CLIENT_DISPLAY → http://localhost:8000"
echo "  Admin (mostrador):  $ADMIN_DISPLAY → http://localhost:8000/admin"
echo ""
echo "Si las ventanas no aparecen en la pantalla correcta, crea el archivo:"
echo "  $ENV_FILE"
echo "con el contenido:"
echo "  CLIENT_DISPLAY=0,0,1024,768"
echo "  ADMIN_DISPLAY=1024,0,1440,900"
echo ""
echo "Ajusta los valores según la resolución y posición de tus monitores."
