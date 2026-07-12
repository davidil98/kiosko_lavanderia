from nicegui import ui, app
import os
import base64
from dotenv import load_dotenv

load_dotenv()

import database_web
import hardware
from services.hardware_hooks import lector_monedas
from services.db_lifecycle import _recuperar_maquinas_sostenidas
from services.point_polling import iniciar_polling, detener_polling

# Configuración de archivos estáticos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEDIA_DIR = os.path.join(BASE_DIR, "media")


def _favicon_data_url() -> str:
    """Convierte el logo a data URL para que NiceGUI lo use como favicon."""
    logo_path = os.path.join(MEDIA_DIR, "logo_slogan.png")
    if not os.path.exists(logo_path):
        return "🌙"
    with open(logo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"


STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app.add_static_files("/media", MEDIA_DIR)
app.add_static_files("/static", STATIC_DIR)

# Inicialización
database_web.init_db()
app.on_startup(lector_monedas.start)
app.on_startup(_recuperar_maquinas_sostenidas)
app.on_startup(iniciar_polling)
hardware.init_gpio_lavadoras()

app.on_shutdown(hardware.limpiar_pines)
app.on_shutdown(detener_polling)

# Registro automático de páginas vía import
import pages.kiosko  # noqa: E402
import pages.admin_login  # noqa: E402
import pages.admin_dashboard  # noqa: E402
import pages.admin_operativo  # noqa: E402
import pages.admin_autoservicio  # noqa: E402
import pages.admin_personalizado  # noqa: E402
import pages.admin_superadmin  # noqa: E402
import pages.admin_cortes  # noqa: E402

if __name__ in {"__main__", "__mp_main__"}:
    try:
        ui.run(
            title="EcoLuna Kiosko",
            port=8000,
            favicon=_favicon_data_url(),
            reload=False,
            show=False,
            storage_secret="ecoluna_kiosko_secret_2025",
        )
    except KeyboardInterrupt:
        print("\nStop app by KeyboardInterrupt.\n")
