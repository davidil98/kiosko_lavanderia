from nicegui import ui, app
import os
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

if __name__ in {"__main__", "__mp_main__"}:
    try:
        ui.run(
            title="EcoLuna Kiosko",
            port=8000,
            favicon="../media/logo_slogan.png",
            reload=False,
            show=False,
            storage_secret="ecoluna_kiosko_secret_2025",
        )
    except KeyboardInterrupt:
        print("\nStop app by KeyboardInterrupt.\n")
