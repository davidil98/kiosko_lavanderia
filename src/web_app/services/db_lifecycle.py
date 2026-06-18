import database_web
import hardware
from datetime import datetime as dt


async def _recuperar_maquinas_sostenidas():
    try:
        ordenes = await database_web.obtener_ordenes_en_proceso_async()

        ahora = dt.now()
        for orden in ordenes:
            equipo_id = next(
                (
                    eid
                    for eid, eq in hardware.EQUIPOS.items()
                    if eq["nombre"] == orden.get("id_equipo", "")
                ),
                None,
            )
            if not equipo_id:
                continue
            eq = hardware.EQUIPOS[equipo_id]
            if eq.get("modo") != "sostenido":
                continue

            es_personalizado = "personalizado" in (orden.get("modalidad") or "")
            if es_personalizado and orden.get("duracion_estimada_min"):
                duracion_max = orden["duracion_estimada_min"]
            else:
                duracion_max = 40 if eq["tipo"] == "secado" else 25

            inicio_str = orden.get("inicio_servicio")
            if inicio_str:
                try:
                    inicio = dt.strptime(inicio_str, "%Y-%m-%d %H:%M:%S")
                    minutos_transcurridos = (ahora - inicio).total_seconds() / 60
                    if minutos_transcurridos >= duracion_max:
                        print(
                            f"[startup] Orden {orden['id_transaccion']} en {eq['nombre']} "
                            f"excedió {duracion_max}min tras apagón. Marcando como completada."
                        )
                        await database_web.marcar_completado_async(
                            orden["id_transaccion"], orden.get("id_equipo", "")
                        )
                    else:
                        restante_min = duracion_max - minutos_transcurridos
                        print(
                            f"[startup] Reprogramando auto-apagado de {eq['nombre']} "
                            f"para orden {orden['id_transaccion']} (restante: {restante_min:.1f}min)"
                        )
                        await hardware.reprogramar_auto_apagado(
                            equipo_id, eq["gpio"], restante_min
                        )
                except Exception as e:
                    print(f"[startup] Error parseando inicio_servicio: {e}")
    except Exception as e:
        print(f"[startup] Error recuperando máquinas sostenidas: {e}")
