from abc import ABC, abstractmethod
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from models import KioskoState


class ResultadoPago:
    """Estandariza el resultado de cualquier intento de pago."""

    def __init__(self, exito: bool, mensaje: str = "", datos: Optional[dict] = None):
        self.exito = exito
        self.mensaje = mensaje
        self.datos = datos or {}


class MetodoPago(ABC):
    """Clase base para todos los métodos de pago (Strategy pattern + Open/Close)."""

    codigo: str = "base"
    nombre: str = "Método"
    icono: str = "/media/icons/leaf.svg"
    descripcion: str = ""

    def __init__(self, state: "KioskoState"):
        self.state = state

    @abstractmethod
    async def procesar_pago(self) -> ResultadoPago:
        """Inicia o ejecuta el flujo de pago. Puede ser asíncrono (polling)."""
        raise NotImplementedError

    @abstractmethod
    def render_panel(self, on_cancelar: Callable, on_pago_exitoso: Callable) -> None:
        """Renderiza el panel NiceGUI con los controles del método."""
        raise NotImplementedError


class MetodoMonedas(MetodoPago):
    codigo = "monedas"
    nombre = "Monedas"
    icono = "/media/icons/money-bag.svg"
    descripcion = "Inserta monedas tú mismo"

    async def procesar_pago(self) -> ResultadoPago:
        return ResultadoPago(
            exito=True,
            datos={"monto": self.state.servicio_seleccionado.precio},
        )

    def render_panel(self, on_cancelar, on_pago_exitoso):
        from nicegui import ui

        with ui.element("div").props("id=pago-panel"):
            ui.html(
                '<p style="font-size:0.88rem;color:#94a3b8;margin:0 0 2px;font-weight:600;">Cliente</p>'
            )
            ui.html(
                f'<p style="font-size:1.3rem;font-weight:800;color:#e2e8f0;margin:0 0 4px;">{self.state.nombre_cliente}</p>'
            )
            ui.html(
                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 2px;">Servicio: <strong style="color:#93c5fd;">{self.state.servicio_seleccionado.nombre}</strong></p>'
            )
            ui.html(
                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 10px;">Peso: <strong style="color:#93c5fd;">{self.state.peso_ingresado} kg</strong></p>'
            )

            faltante = self.state.get_faltante()
            pct = (
                min(
                    100,
                    int(
                        self.state.dinero_ingresado
                        / self.state.servicio_seleccionado.precio
                        * 100
                    ),
                )
                if self.state.servicio_seleccionado.precio > 0
                else 100
            )

            with ui.element("div").classes("monto-box"):
                ui.html('<div class="monto-label">Falta por insertar</div>')
                ui.html(f'<div class="monto-valor">${faltante}</div>')
                ui.html(
                    f'<div class="monto-sub">Ingresado ${self.state.dinero_ingresado} de ${self.state.servicio_seleccionado.precio}</div>'
                )

            ui.html(
                f'<div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{pct}%;"></div></div>'
            )
            ui.html(
                f'<div class="progress-pct">{pct}% completado — inserte monedas en el dispensador</div>'
            )

            btn_confirmar = ui.button("Confirmar y Registrar Pago")
            if self.state.puede_pagar():
                btn_confirmar.on("click", on_pago_exitoso)
                btn_confirmar.style(
                    "width:100%; margin-top:16px; padding:14px; font-size:1.1rem; font-weight:700; cursor:pointer;"
                )
            else:
                btn_confirmar.disable()
                btn_confirmar.style(
                    "width:100%; margin-top:16px; padding:14px; background:#1e293b; color:#475569; border-radius:11px; font-size:1.1rem; font-weight:700; cursor:not-allowed;"
                )

            ui.button("Cancelar y regresar", color="red").classes("btn-cancelar").on(
                "click", on_cancelar
            )


class MetodoQR(MetodoPago):
    codigo = "qr"
    nombre = "QR Mercado Pago"
    icono = "/media/icons/leaf.svg"
    descripcion = "Escanea con tu app"

    def __init__(self, state: "KioskoState"):
        super().__init__(state)
        self.orden_id: Optional[str] = None
        self.qr_data: Optional[str] = None
        self.qr_url: Optional[str] = None
        self.fallback_estatico: bool = False

    async def procesar_pago(self) -> ResultadoPago:
        from mp_qr import crear_orden_qr, obtener_qr_estatico_async

        try:
            monto = float(self.state.servicio_seleccionado.precio)
            ref = f"ECOLUNA_{self.state.nombre_cliente}_{id(self)}"
            desc = (
                f"{self.state.servicio_seleccionado.nombre} - "
                f"{self.state.nombre_cliente}"
            )
            data = await crear_orden_qr(monto, desc, ref)
            self.orden_id = data.get("id") or data.get("instore_order_id")
            self.qr_data = data.get("qr_data")
            self.qr_url = data.get("qr_code_url") or data.get("qr_url")
            return ResultadoPago(
                exito=True,
                datos={
                    "orden_id": self.orden_id,
                    "qr_data": self.qr_data,
                    "qr_url": self.qr_url,
                    "monto": monto,
                },
            )
        except Exception as e:
            err = str(e)
            print(
                f"[MetodoQR] API instore no disponible ({err}); usando QR estático del POS"
            )
            # Fallback: el producto instore no está habilitado.
            # Mostramos el QR estático del POS y el operador cobra el monto manualmente.
            qr_url = await obtener_qr_estatico_async()
            if qr_url:
                self.orden_id = None
                self.qr_data = None
                self.qr_url = qr_url
                self.fallback_estatico = True
                return ResultadoPago(
                    exito=True,
                    datos={
                        "qr_url": qr_url,
                        "monto": monto,
                        "fallback_estatico": True,
                    },
                )
            return ResultadoPago(
                exito=False,
                mensaje=(
                    f"No se pudo crear la orden QR ({err}). "
                    "Contacta al administrador para habilitar el producto "
                    "QR modelo atendido en Mercado Pago."
                ),
            )

    async def cancelar(self) -> None:
        if not self.orden_id:
            return  # Fallback estático no requiere cancelación
        from mp_qr import cancelar_orden_qr

        try:
            await cancelar_orden_qr(self.orden_id)
        except Exception as e:
            print(f"[MetodoQR] Error al cancelar orden {self.orden_id}: {e}")

    def render_panel(self, on_cancelar, on_pago_exitoso):
        from nicegui import ui

        with ui.element("div").props("id=pago-panel"):
            ui.html(
                f'<p style="font-size:0.88rem;color:#94a3b8;margin:0 0 2px;font-weight:600;">Cliente</p>'
            )
            ui.html(
                f'<p style="font-size:1.3rem;font-weight:800;color:#e2e8f0;margin:0 0 4px;">{self.state.nombre_cliente}</p>'
            )
            ui.html(
                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 2px;">Servicio: <strong style="color:#93c5fd;">{self.state.servicio_seleccionado.nombre}</strong></p>'
            )
            ui.html(
                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 10px;">Total: <strong style="color:#3b82f6;">${self.state.servicio_seleccionado.precio}</strong></p>'
            )

            qr_html = self._build_qr_html()
            ui.html(qr_html)

            if self.fallback_estatico:
                ui.html(
                    '<div style="margin-top:14px;padding:12px;background:rgba(234,179,8,0.13);'
                    "border:1px solid rgba(234,179,8,0.3);border-radius:10px;"
                    'color:#fde68a;font-size:0.85rem;text-align:center;">'
                    "<b>Modo QR estático</b><br>"
                    f"Escanea y el operador cobrará <b>${self.state.servicio_seleccionado.precio}</b> "
                    "en la terminal.<br>"
                    "<b>Tu orden quedará en espera</b> hasta que el administrador "
                    "confirme el pago en el mostrador."
                    "</div>"
                )
            else:
                ui.html(
                    '<p style="font-size:0.85rem;color:#94a3b8;margin-top:12px;text-align:center;">'
                    "Escanea el QR con tu app de Mercado Pago. La orden expira en 5 minutos."
                    "</p>"
                )

            ui.button("Cancelar y regresar", color="red").classes("btn-cancelar").on(
                "click", on_cancelar
            )

            if self.fallback_estatico:
                # Fallback estático: NO se puede aprobar desde el kiosko.
                # El cliente debe esperar a que el admin confirme en el panel.
                ui.html(
                    '<div style="margin-top:10px;text-align:center;font-size:0.95rem;'
                    'color:#94a3b8;font-weight:600;">'
                    "⏳ Esperando confirmación del administrador en el mostrador..."
                    "</div>"
                )
                return  # No continuar con el polling normal

            if not self.fallback_estatico:
                _estado_box = ui.html(
                    '<div id="qr-estado" style="margin-top:8px;text-align:center;font-size:0.9rem;color:#64748b;">'
                    "Esperando pago...</div>"
                )

                async def _polling_loop():
                    from mp_qr import verificar_estado_orden

                    while self.orden_id:
                        try:
                            estado = await verificar_estado_orden(self.orden_id)
                        except Exception as e:
                            print(f"[MetodoQR] Error polling: {e}")
                            await _async_sleep(3)
                            continue

                        if estado == "paid":
                            _estado_box.set_content(
                                '<div style="margin-top:8px;text-align:center;font-size:1rem;color:#4ade80;font-weight:700;">'
                                "¡Pago confirmado!</div>"
                            )
                            await _async_sleep(1)
                            await on_pago_exitoso()
                            return
                        if estado in ("cancelled", "expired"):
                            _estado_box.set_content(
                                f'<div style="margin-top:8px;text-align:center;font-size:0.9rem;color:#ef4444;">'
                                f"Orden {estado}. Cancela e intenta de nuevo.</div>"
                            )
                            return
                        await _async_sleep(3)

                import asyncio as _aio

                _aio.create_task(_polling_loop())

    def _build_qr_html(self) -> str:
        """Genera el HTML del QR. La API v2 devuelve 'qr_data' como string (no base64).
        Usamos un generador de QR en JS (qrcode-svg inline) para convertirlo a SVG visible."""
        if self.qr_url:
            return (
                f'<div style="display:flex;justify-content:center;margin-top:12px;">'
                f'<img src="{self.qr_url}" alt="QR de pago" '
                f'style="width:240px;height:240px;background:white;padding:12px;border-radius:12px;">'
                f"</div>"
            )
        if self.qr_data and self.qr_data.startswith("data:image"):
            return (
                f'<div style="display:flex;justify-content:center;margin-top:12px;">'
                f'<img src="{self.qr_data}" alt="QR de pago" '
                f'style="width:240px;height:240px;background:white;padding:12px;border-radius:12px;">'
                f"</div>"
            )
        if self.qr_data:
            qr_escaped = self.qr_data.replace('"', "&quot;")
            return (
                f'<div style="display:flex;flex-direction:column;align-items:center;margin-top:12px;">'
                f'<div id="ecoluna-qr-svg" data-qr="{qr_escaped}" '
                f'style="background:white;padding:16px;border-radius:12px;width:240px;height:240px;'
                f'display:flex;align-items:center;justify-content:center;"></div>'
                f'<script src="https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.min.js"></script>'
                f"<script>"
                f"(function(){{"
                f"var d=document.getElementById('ecoluna-qr-svg');if(!d)return;"
                f"var t=d.getAttribute('data-qr');try{{"
                f"var qr=qrcode(0,'M');qr.addData(t);qr.make();"
                f"d.innerHTML=qr.createSvgTag({{cellSize:6,margin:4}});"
                f"}}catch(e){{d.textContent='Error generando QR: '+e.message;}}"
                f"}})();"
                f"</script>"
                f"</div>"
            )
        return (
            '<div style="text-align:center;padding:20px;color:#ef4444;">'
            "No se pudo generar el QR. Intenta de nuevo.</div>"
        )


class MetodoTerminalPoint(MetodoPago):
    codigo = "terminal"
    nombre = "Terminal Point"
    icono = "/media/icons/leaf.svg"
    descripcion = "Cobro en terminal (no disponible)"

    async def procesar_pago(self) -> ResultadoPago:
        return ResultadoPago(
            exito=False,
            mensaje="La integración con terminal Point no está disponible aún.",
        )

    def render_panel(self, on_cancelar, on_pago_exitoso):
        from nicegui import ui

        with ui.element("div").props("id=pago-panel"):
            ui.html(
                '<p style="text-align:center;padding:24px;color:#ef4444;">'
                "La integración con terminal Point aún no está disponible.</p>"
            )
            ui.button("Volver").classes("btn-cancelar").on("click", on_cancelar)


async def _async_sleep(secs: float) -> None:
    import asyncio

    await asyncio.sleep(secs)


METODOS_PAGO_DISPONIBLES = [MetodoMonedas, MetodoQR, MetodoTerminalPoint]
