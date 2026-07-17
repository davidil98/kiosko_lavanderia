"""Tests del cliente HTTP y el polling de Mercado Pago Point.

Mockeamos `requests` y el token de config para no tocar la red real.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _mp_env(monkeypatch):
    """Inyecta tokens de test y deshabilita el fallback prod."""
    import app.config as cfg

    monkeypatch.setattr(cfg, "MP_PROD_TOKEN", "APP_USR-PROD")
    monkeypatch.setattr(cfg, "MP_TEST_TOKEN", "APP_USR-TEST")
    monkeypatch.setattr(cfg, "MP_TERMINAL_ID", "TERMINAL-X")
    monkeypatch.setattr(cfg, "MP_ENVIRONMENT", "test")
    monkeypatch.setattr("app.adaptadores.mercado_pago.cliente.MP_ENVIRONMENT", "test")
    monkeypatch.setattr(
        "app.adaptadores.mercado_pago.cliente.MP_PROD_TOKEN", "APP_USR-PROD"
    )
    monkeypatch.setattr(
        "app.adaptadores.mercado_pago.cliente.MP_TEST_TOKEN", "APP_USR-TEST"
    )
    monkeypatch.setattr(
        "app.adaptadores.mercado_pago.cliente.MP_TERMINAL_ID", "TERMINAL-X"
    )
    yield


# ── cliente.py ───────────────────────────────────────────────────────────────


def test_token_elige_test_en_modo_test():
    from app.adaptadores.mercado_pago import cliente

    assert cliente.token() == "APP_USR-TEST"


def test_token_elige_prod_si_esta_configurado():
    from app.adaptadores.mercado_pago import cliente

    with (
        patch.object(cliente, "MP_ENVIRONMENT", "prod"),
        patch.object(cliente, "MP_PROD_TOKEN", "APP_USR-PROD-X"),
    ):
        assert cliente.token() == "APP_USR-PROD-X"


def test_token_prod_sin_token_cae_a_test():
    from app.adaptadores.mercado_pago import cliente

    with (
        patch.object(cliente, "MP_ENVIRONMENT", "prod"),
        patch.object(cliente, "MP_PROD_TOKEN", ""),
    ):
        assert cliente.token() == "APP_USR-TEST"


def test_terminal_id_sin_config_lanza():
    from app.adaptadores.mercado_pago import cliente

    with patch.object(cliente, "MP_TERMINAL_ID", ""):
        with pytest.raises(RuntimeError):
            cliente.terminal_id()


def test_headers_incluye_bearer_y_json():
    from app.adaptadores.mercado_pago import cliente

    h = cliente.headers()
    assert h["Authorization"] == "Bearer APP_USR-TEST"
    assert h["Content-Type"] == "application/json"


def test_headers_con_idempotency_agrega_uuid():
    from app.adaptadores.mercado_pago import cliente

    h1 = cliente.headers(con_idempotency=True)
    h2 = cliente.headers(con_idempotency=True)
    assert "X-Idempotency-Key" in h1
    assert h1["X-Idempotency-Key"] != h2["X-Idempotency-Key"]


# ── point.py ─────────────────────────────────────────────────────────────────


def _mock_response(status, json_data=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.json = (
        MagicMock(return_value=json_data)
        if json_data is not None
        else MagicMock(side_effect=ValueError)
    )
    return r


def test_crear_orden_point_exitosa():
    from app.adaptadores.mercado_pago import point

    r201 = _mock_response(201, {"id": "mp_001", "status": "open"})
    with patch(
        "app.adaptadores.mercado_pago.point.requests.post", return_value=r201
    ) as m:
        out = point.crear_orden_point(45.0, "EcoLuna test", "REF_1")
    assert out == {"id": "mp_001", "status": "open"}
    m.assert_called_once()


def test_crear_orden_point_409_retry_ok():
    from app.adaptadores.mercado_pago import point

    r409 = _mock_response(409, text="queued")
    r201 = _mock_response(201, {"id": "mp_002"})
    with patch(
        "app.adaptadores.mercado_pago.point.requests.post", side_effect=[r409, r201]
    ) as m:
        out = point.crear_orden_point(45.0, "test", reintentar_en_409=True)
    assert out == {"id": "mp_002"}
    assert m.call_count == 2


def test_crear_orden_point_409_sin_retry_devuelve_vacio():
    from app.adaptadores.mercado_pago import point

    r409 = _mock_response(409, text="queued")
    with patch("app.adaptadores.mercado_pago.point.requests.post", return_value=r409):
        out = point.crear_orden_point(45.0, "test", reintentar_en_409=False)
    assert out == {}


def test_crear_orden_point_500_devuelve_vacio():
    from app.adaptadores.mercado_pago import point

    r500 = _mock_response(500, text="server error")
    with patch("app.adaptadores.mercado_pago.point.requests.post", return_value=r500):
        out = point.crear_orden_point(45.0, "test")
    assert out == {}


def test_crear_orden_point_error_de_red_devuelve_vacio():
    from app.adaptadores.mercado_pago import point
    import requests

    with patch(
        "app.adaptadores.mercado_pago.point.requests.post",
        side_effect=requests.ConnectionError("no internet"),
    ):
        out = point.crear_orden_point(45.0, "test")
    assert out == {}


def test_consultar_orden_exitosa():
    from app.adaptadores.mercado_pago import point

    r200 = _mock_response(200, {"id": "mp_x", "status": "paid"})
    with patch("app.adaptadores.mercado_pago.point.requests.get", return_value=r200):
        out = point.consultar_orden("mp_x")
    assert out["status"] == "paid"


def test_consultar_orden_vacia_devuelve_vacio():
    from app.adaptadores.mercado_pago import point

    assert point.consultar_orden("") == {}


def test_cancelar_orden_exitosa():
    from app.adaptadores.mercado_pago import point

    r200 = _mock_response(200)
    with patch("app.adaptadores.mercado_pago.point.requests.post", return_value=r200):
        assert point.cancelar_orden("mp_x") is True


def test_cancelar_orden_rechazada_devuelve_false():
    from app.adaptadores.mercado_pago import point

    r500 = _mock_response(500, text="n950 does not support cancel")
    with patch("app.adaptadores.mercado_pago.point.requests.post", return_value=r500):
        assert point.cancelar_orden("mp_x") is False


def test_extraer_folio_pago_existe():
    from app.adaptadores.mercado_pago import point

    data = {"transactions": {"payments": [{"id": "p_99"}]}}
    assert point.extraer_folio_pago(data) == "p_99"


def test_extraer_folio_pago_sin_pagos():
    from app.adaptadores.mercado_pago import point

    assert point.extraer_folio_pago({}) == ""
    assert point.extraer_folio_pago({"transactions": {}}) == ""


# ── polling.py end-to-end ────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _db_tmp(tmp_path):
    from app.repo import db
    from app.adaptadores.mercado_pago import polling

    db.usar_path_test(tmp_path / "mp.db")
    db.init_db()
    # Resetear estado del módulo de polling entre tests
    polling._tarea = None
    polling._detenido = False
    yield
    db.usar_path_test(None)


def _orden_point_en_pendiente_pago() -> int:
    """Helper: crea una orden en Pendiente-pago con mp_order_id."""
    from app.repo import transacciones

    return asyncio.run(
        transacciones.crear_orden_pendiente_pago(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            monto=45,
            nombre_cliente="Test",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
    )


def test_polling_confirma_pago_y_pasa_a_pendiente():
    """Flujo completo: orden Point → polling detecta paid → estado = Pendiente."""
    from app.adaptadores.mercado_pago import polling
    from app.adaptadores.mercado_pago.point import consultar_orden as consultar_real
    from app.repo import transacciones

    oid = _orden_point_en_pendiente_pago()
    asyncio.run(transacciones.guardar_mp_order_id(oid, "mp_test_1"))

    paid = {
        "id": "mp_test_1",
        "status": "paid",
        "transactions": {"payments": [{"id": "p_42"}]},
    }

    async def main():
        eventos = []

        async def notificar(tipo, id_orden):
            eventos.append((tipo, id_orden))

        with patch(
            "app.adaptadores.mercado_pago.polling.point.consultar_orden",
            return_value=paid,
        ):
            for orden in await transacciones.listar_point_pendientes():
                await polling._revisar_orden(orden, notificar)
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente"
        assert t["numero_transaccion_terminal"] == "p_42"
        assert eventos == [("pago.confirmado", str(oid))]

    asyncio.run(main())


def test_polling_cancela_orden_expirada():
    from app.adaptadores.mercado_pago import polling
    from app.repo import transacciones

    oid = _orden_point_en_pendiente_pago()
    asyncio.run(transacciones.guardar_mp_order_id(oid, "mp_exp_1"))

    async def main():
        async def notificar(tipo, id_orden):
            pass

        with patch(
            "app.adaptadores.mercado_pago.polling.point.consultar_orden",
            return_value={"id": "mp_exp_1", "status": "expired"},
        ):
            for orden in await transacciones.listar_point_pendientes():
                await polling._revisar_orden(orden, notificar)
        assert await transacciones.obtener_por_id(oid) is None

    asyncio.run(main())


def test_polling_cancela_orden_cancelled():
    from app.adaptadores.mercado_pago import polling
    from app.repo import transacciones

    oid = _orden_point_en_pendiente_pago()
    asyncio.run(transacciones.guardar_mp_order_id(oid, "mp_can_1"))

    async def main():
        async def notificar(tipo, id_orden):
            pass

        with patch(
            "app.adaptadores.mercado_pago.polling.point.consultar_orden",
            return_value={"id": "mp_can_1", "status": "cancelled"},
        ):
            for orden in await transacciones.listar_point_pendientes():
                await polling._revisar_orden(orden, notificar)
        assert await transacciones.obtener_por_id(oid) is None

    asyncio.run(main())


def test_polling_ignora_status_open_sin_modificar():
    from app.adaptadores.mercado_pago import polling
    from app.repo import transacciones

    oid = _orden_point_en_pendiente_pago()
    asyncio.run(transacciones.guardar_mp_order_id(oid, "mp_open_1"))

    async def main():
        async def notificar(tipo, id_orden):
            pass

        with patch(
            "app.adaptadores.mercado_pago.polling.point.consultar_orden",
            return_value={"id": "mp_open_1", "status": "open"},
        ):
            for orden in await transacciones.listar_point_pendientes():
                await polling._revisar_orden(orden, notificar)
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente-pago"

    asyncio.run(main())


def test_polling_error_de_red_no_modifica_orden():
    from app.adaptadores.mercado_pago import polling
    from app.repo import transacciones

    oid = _orden_point_en_pendiente_pago()
    asyncio.run(transacciones.guardar_mp_order_id(oid, "mp_err_1"))

    async def main():
        async def notificar(tipo, id_orden):
            pass

        # consultar_orden devuelve {} en error
        with patch(
            "app.adaptadores.mercado_pago.polling.point.consultar_orden",
            return_value={},
        ):
            for orden in await transacciones.listar_point_pendientes():
                await polling._revisar_orden(orden, notificar)
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente-pago"

    asyncio.run(main())


def test_polling_cancela_orden_expirada():
    from app.adaptadores.mercado_pago import polling
    from app.repo import transacciones

    oid = _orden_point_en_pendiente_pago()
    asyncio.run(transacciones.guardar_mp_order_id(oid, "mp_exp_1"))

    async def main():
        async def notificar(tipo, id_orden):
            pass

        with patch(
            "app.adaptadores.mercado_pago.polling.asyncio.to_thread",
            return_value={"id": "mp_exp_1", "status": "expired"},
        ):
            for orden in await transacciones.listar_point_pendientes():
                await polling._revisar_orden(orden, notificar)
        assert await transacciones.obtener_por_id(oid) is None

    asyncio.run(main())


def test_polling_cancela_orden_cancelled():
    from app.adaptadores.mercado_pago import polling
    from app.repo import transacciones

    oid = _orden_point_en_pendiente_pago()
    asyncio.run(transacciones.guardar_mp_order_id(oid, "mp_can_1"))

    async def main():
        async def notificar(tipo, id_orden):
            pass

        with patch(
            "app.adaptadores.mercado_pago.polling.asyncio.to_thread",
            return_value={"id": "mp_can_1", "status": "cancelled"},
        ):
            for orden in await transacciones.listar_point_pendientes():
                await polling._revisar_orden(orden, notificar)
        assert await transacciones.obtener_por_id(oid) is None

    asyncio.run(main())


def test_polling_ignora_status_open_sin_modificar():
    from app.adaptadores.mercado_pago import polling
    from app.repo import transacciones

    oid = _orden_point_en_pendiente_pago()
    asyncio.run(transacciones.guardar_mp_order_id(oid, "mp_open_1"))

    async def main():
        async def notificar(tipo, id_orden):
            pass

        with patch(
            "app.adaptadores.mercado_pago.polling.asyncio.to_thread",
            return_value={"id": "mp_open_1", "status": "open"},
        ):
            for orden in await transacciones.listar_point_pendientes():
                await polling._revisar_orden(orden, notificar)
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente-pago"

    asyncio.run(main())


def test_polling_error_de_red_no_modifica_orden():
    from app.adaptadores.mercado_pago import polling
    from app.repo import transacciones

    oid = _orden_point_en_pendiente_pago()
    asyncio.run(transacciones.guardar_mp_order_id(oid, "mp_err_1"))

    async def main():
        async def notificar(tipo, id_orden):
            pass

        # consultar_orden devuelve {} en error
        with patch(
            "app.adaptadores.mercado_pago.polling.asyncio.to_thread", return_value={}
        ):
            for orden in await transacciones.listar_point_pendientes():
                await polling._revisar_orden(orden, notificar)
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente-pago"

    asyncio.run(main())


def test_iniciar_y_detener_polling_lanza_y_da_tarea():
    from app.adaptadores.mercado_pago import polling

    async def main():
        polling.iniciar(polling.notificar_noop)
        assert polling._tarea is not None
        await polling.detener()
        assert polling._tarea is None

    asyncio.run(main())


def test_iniciar_polling_dos_veces_no_duplica():
    from app.adaptadores.mercado_pago import polling

    async def main():
        polling.iniciar(polling.notificar_noop)
        primera = polling._tarea
        polling.iniciar(polling.notificar_noop)
        assert polling._tarea is primera
        await polling.detener()

    asyncio.run(main())
