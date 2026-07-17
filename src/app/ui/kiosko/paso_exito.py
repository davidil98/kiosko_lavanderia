"""Paso 5: Pago exitoso.

Muestra el resumen de la orden y un timer que resetea el kiosko a los 7s.
"""

from nicegui import ui

from app.ui.compartido.estilos import badge_servicio
from app.ui.kiosko.wizard import Paso, WizardKiosko

TIEMPO_RESET_S = 7


def render_paso_exito(wizard: WizardKiosko, refresh) -> None:
    cambio = max(0, wizard.dinero - wizard.precio_total())
    es_personalizado = wizard.servicio is not None and wizard.servicio.es_personalizado

    if wizard.servicio is None or wizard.ultimo_id_transaccion is None:
        # Estado inválido: reset inmediato
        refresh(wizard.reset())
        return

    cambio_html = (
        f'<div class="cambio-box">'
        f'<img src="/media/icons/money-bag.svg" style="width:20px;height:20px;'
        f'vertical-align:middle;margin-right:6px;">'
        f"Su cambio: ${cambio}</div>"
        if cambio > 0
        else ""
    )
    subtitulo = (
        "Tu orden ha sido registrada. Dirígete al mostrador."
        if es_personalizado
        else "Dirígete a la máquina asignada."
    )
    precio_label = "Precio" if es_personalizado else "Pagado"
    precio_valor = (
        f"${wizard.precio_total()} "
        f'<span style="font-size:0.78rem;color:#a78bfa;font-weight:600;">'
        f"(pagará en mostrador)</span>"
        if es_personalizado
        else f"${wizard.precio_total()}"
    )
    ui.html(f"""
        <div id="exito-panel">
            <div class="exito-icono">
                <img src="/media/icons/check.svg"
                     style="width:64px;height:64px;display:block;margin:0 auto;"
                     onerror="this.style.display='none'">
            </div>
            <div class="exito-titulo">¡Orden Registrada!</div>
            <div class="exito-subtitulo">{subtitulo}</div>
            <div class="exito-datos">
                <div class="exito-dato-row">
                    <span class="exito-dato-label">Orden #</span>
                    <span class="exito-dato-val">{wizard.ultimo_id_transaccion}</span>
                </div>
                <div class="exito-dato-row">
                    <span class="exito-dato-label">Cliente</span>
                    <span class="exito-dato-val">{wizard.nombre}</span>
                </div>
                <div class="exito-dato-row">
                    <span class="exito-dato-label">Servicio</span>
                    <span class="exito-dato-val">
                        {badge_servicio(wizard.servicio.codigo)}
                    </span>
                </div>
                <div class="exito-dato-row">
                    <span class="exito-dato-label">Peso</span>
                    <span class="exito-dato-val">{wizard.peso} kg</span>
                </div>
                <div class="exito-dato-row">
                    <span class="exito-dato-label">{precio_label}</span>
                    <span class="exito-dato-val">{precio_valor}</span>
                </div>
            </div>
            {cambio_html}
            <div class="reinicio-txt">
                El sistema se reiniciará automáticamente en breve...
            </div>
        </div>
    """)

    # Auto-reset a los 7 segundos via ui.timer (más limpio que asyncio.sleep)
    ui.timer(TIEMPO_RESET_S, lambda: refresh(wizard.reset()), once=True)
