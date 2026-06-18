from nicegui import ui
from services.notifications import state


def render_paso_exito():
    cambio = state.get_cambio()
    es_personalizado = (
        state.servicio_seleccionado
        and state.servicio_seleccionado.modalidad == "personalizado"
    )
    cambio_html = (
        f'<div class="cambio-box">'
        f'<img src="/media/icons/money-bag.svg" style="width:20px;height:20px;vertical-align:middle;margin-right:6px;">'
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
        f'${state.servicio_seleccionado.precio} <span style="font-size:0.78rem;color:#a78bfa;font-weight:600;">(pagará en mostrador)</span>'
        if es_personalizado
        else f"${state.servicio_seleccionado.precio if state.servicio_seleccionado else 0}"
    )
    ui.html(f"""
        <div id="exito-panel">
            <div class="exito-icono"><img src="/media/icons/check.svg" style="width:64px;height:64px;display:block;margin:0 auto;" onerror="this.style.display='none'"></div>
            <div class="exito-titulo">¡Orden Registrada!</div>
            <div class="exito-subtitulo">{subtitulo}</div>
            <div class="exito-datos">
                <div class="exito-dato-row">
                    <span class="exito-dato-label">Orden #</span>
                    <span class="exito-dato-val">{state.ultimo_id_transaccion}</span>
                </div>
                <div class="exito-dato-row">
                    <span class="exito-dato-label">Cliente</span>
                    <span class="exito-dato-val">{state.nombre_cliente}</span>
                </div>
                <div class="exito-dato-row">
                    <span class="exito-dato-label">Servicio</span>
                    <span class="exito-dato-val">{state.servicio_seleccionado.nombre if state.servicio_seleccionado else ""}</span>
                </div>
                <div class="exito-dato-row">
                    <span class="exito-dato-label">Peso</span>
                    <span class="exito-dato-val">{state.peso_ingresado} kg</span>
                </div>
                <div class="exito-dato-row">
                    <span class="exito-dato-label">{precio_label}</span>
                    <span class="exito-dato-val">{precio_valor}</span>
                </div>
            </div>
            {cambio_html}
            <div class="reinicio-txt">El sistema se reiniciará automáticamente en breve...</div>
        </div>
    """)
