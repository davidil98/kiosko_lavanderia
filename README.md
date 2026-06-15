# Kiosko de Lavandería EcoLuna 🌙🫧

Este proyecto es el sistema central de administración, cobro y control de hardware para la Lavandería EcoLuna. Ha evolucionado de una interfaz local a una **Arquitectura Web (Headless)**, diseñada para separar el flujo de cobro del cliente y el panel de control del administrador, operando desde una Raspberry Pi.

El sistema controla directamente el hardware de la lavandería (lavadoras LG Inverter, cajón de dinero) mediante circuitos aislados con optoacopladores y relés, garantizando seguridad industrial.

---

## 📸 Características Principales

* **Arquitectura Web-Based:** Construida con [FastAPI / NiceGUI] para permitir múltiples pantallas simultáneas a través de la red local.
* **Sistema de Cola Asíncrono:**
* La **Pantalla Cliente (Touch)** procesa el cobro y se libera inmediatamente para el siguiente usuario.
  * La **Pantalla Admin (Mostrador)** recibe las órdenes pendientes, permitiendo al operador pesar la ropa, asignar la máquina y disparar el inicio del ciclo de forma segura.
* **Control de Hardware Aislado:** Mapeo de señales para lectura de monederos mecánicos y disparo de pulsos de inicio en máquinas industriales de 6V.
* **Registro de Ventas en Tiempo Real:** Base de datos `SQLite3` integrada (`ecoluna_datos.db`) para llevar el control financiero e historial de equipos.

---

## 🛠️ Requisitos del Sistema y Hardware

- **Cerebro Central:** Raspberry Pi (Zero 2 W / 3B+ / 4) ejecutándose como servidor.
- **Pantallas:** - 1x Pantalla Táctil (Cliente) ejecutando un navegador web en Modo Kiosco.
  - 1x Monitor VGA o Dispositivo móvil (Admin/Mostrador) conectado a la red local.
- **Electrónica:**
  - Optoacopladores (ej. 4N25) para aislar el botón de Inicio/Pausa de las lavadoras LG.
  - Módulo Relé para el disparo del solenoide (12V-18V) de la caja de billetes/cambio.
  - Tragamonedas multimoneda configurado con blindaje por software (Debounce).
- **Software:** Python 3.9+, framework web (FastAPI/NiceGUI).

---

## 🚀 Flujo de Operación (Workflow)

1. **Selección y Cobro (Cliente):** El usuario elige Lavado/Secado en la pantalla táctil y realiza el pago (Efectivo/Terminal).
2. **Generación de Ticket Virtual:** La Raspberry Pi valida el pago, la base de datos registra una nueva orden en estado "Pendiente" y la pantalla vuelve al inicio.
3. **Recepción y Asignación (Admin):** El encargado recibe la ropa, la pesa, verifica la capacidad y configura el ciclo físico (rueda de la lavadora).
4. **Disparo de Hardware:** Desde el panel web de administración, el encargado selecciona la máquina a utilizar y presiona "Iniciar". La Raspberry envía un pulso aislado de 0.5s al optoacoplador, iniciando el lavado.

---

## 🧪 Modo de Pruebas (Test Mode)

Para ejecutar el Kiosko en cualquier computadora (Windows/Mac) o cuando no tengas la Raspberry Pi o sus componentes a la mano, puedes iniciar el sistema en **Modo de Pruebas**. Este modo silencia las alertas de falta de hardware y te permite interactuar usando tu teclado físico.

```bash
cd src/web_app
python main.py test
```

**Simulación de ingreso de monedas con teclado:**
Al arrancar en este modo, en cualquier punto de las pantallas del kiosko (`/`), puedes presionar las siguientes teclas para simular un pulso desde el monedero:
- `1` = Agrega $1
- `2` = Agrega $2
- `5` = Agrega $5
- `0` = Agrega $10

---

## 🖥️ Ejecución en Modo Kiosko (Raspberry Pi)

Para un entorno de producción donde la aplicación debe arrancar en pantalla completa y de forma ininterrumpida (Modo Kiosko), se cuenta con un script para generar un acceso directo (`.desktop`).

Ejecuta el siguiente script en la raíz del proyecto para generar el lanzador:
```bash
./create_desktop_shortcut.sh
```
Esto creará el archivo **`KioskoEcoLuna.desktop`** en el escritorio del usuario, el cual:
1. Inicia el servidor de NiceGUI en segundo plano (puerto 8000).
2. Abre automáticamente el navegador Chromium en modo incógnito, sin barras y en pantalla completa apuntando a `http://localhost:8000`.

---

## 💳 Medios de Pago: Monedas + QR Mercado Pago

El kiosko acepta **monedas** (aceptador físico) y **QR de Mercado Pago** (in-store / `type=qr` con la API `/v1/orders`). Ambos métodos se gestionan mediante una arquitectura **Strategy + Open/Closed** (`src/web_app/metodos_pago.py`); añadir un nuevo método (cajero manual, terminal Point) es tan simple como crear una nueva clase y agregarla a `METODOS_PAGO_DISPONIBLES`.

### Configuración de credenciales

Las credenciales viven en `.env` (no se sube al repo por estar en `.gitignore`):

```env
# Token de pruebas (recomendado durante desarrollo)
MP_TEST_TOKEN=APP_USR-XXXX-test
# Token de producción (cuando vayas a cobrar dinero real)
MP_PROD_TOKEN=APP_USR-XXXX-prod
# Selecciona cuál se usa al iniciar
MP_ENVIRONMENT=test
```

### 🔄 Cambiar de Test → Producción

**No se requiere cambiar código.** Solo edita `.env`:

1. Abre `.env` y rellena `MP_PROD_TOKEN` con tu token de producción (disponible en [Tus Integraciones](https://www.mercadopago.com.mx/developers/panel/app)).
2. Cambia `MP_ENVIRONMENT=prod`.
3. Reinicia el kiosko (`python main.py`).

El módulo `mp_qr.py` lee `MP_ENVIRONMENT` al iniciar y elige el token correcto. No hay que tocar nada en `main.py` ni `metodos_pago.py`.

**Para volver a modo test:** cambia `MP_ENVIRONMENT=test` y reinicia.

> ⚠️ **Importante:** nunca commitees el `.env`. El `.gitignore` ya lo excluye, pero verifica antes de hacer `git add`.

### 🖥️ Terminal Point (pendiente)

La integración con **terminal Point física** está en pruebas. En el entorno de test la terminal responde con error `409 already_queued_order_on_terminal` aunque no tenga cobros visibles, se haya reiniciado, re-vinculado y probado en modos `PDV` y `STANDALONE`.

**Diagnóstico actual:**
- El bloqueo parece estar del lado de Mercado Pago (orden fantasma en servidores o limitación del sandbox de Point).
- No existe endpoint público para listar/cancelar órdenes Point atoradas.

**Acción pendiente:**
Enviar ticket a soporte de Mercado Pago ([soporte para integraciones](https://www.mercadopago.com.mx/developers/es/support/center)) con:
- `terminal_id`: `NEWLAND_N950__N950NCC904817363`
- `pos_id`: `132903603`
- Error: `409 already_queued_order_on_terminal`
- Referencia: orden `type=point` creada via `/v1/orders` en cuenta de test user `3438707426`.

Mientras tanto, el kiosko opera con **monedas + QR Mercado Pago** (dinámico si está habilitado, o estático como fallback).

### 🔧 Habilitar el producto "QR modelo atendido" (instore QR)

Si al escanear el QR dinámico ves en los logs errores como `404 resource not found` en `/instore/qr/v2/orders`, significa que tu cuenta de Mercado Pago **no tiene habilitado el producto "QR modelo atendido"** necesario para la integración dinámica. Esto ocurre tanto en test como en producción si no se activa el producto.

Mientras tanto, el kiosko usa automáticamente el **QR estático** del POS `CAJA01` como respaldo: el cliente escanea el QR, paga con su app de Mercado Pago, y el operador confirma el pago en el panel de administración.

Para activar el producto y obtener la API dinámica:

1. **Inicia sesión** en [Tus Integraciones](https://www.mercadopago.com.mx/developers/panel/app) con la cuenta vendedora.
2. **Crea una integración** tipo "QR modelo atendido" / "QR in-store" (suele estar en "Productos disponibles" → "Pagos presenciales" → "QR modelo atendido").
3. **Asocia tu POS `CAJA01`** (puedes usar `src/mp_dev/create_checkout.py` para crearlo si no existe).
4. **Verifica que el sponsor** (tu `MP_USER_ID` en `.env`) sea el dueño de la cuenta vendedora.
5. **Espera ~5 minutos** a que MP propague los cambios.
6. **Reinicia el kiosko** y vuelve a probar.

Si la activación por panel no funciona, **contacta a soporte de Mercado Pago** ([soporte para integraciones](https://www.mercadopago.com.mx/developers/es/support/center)) indicando:
- Tu `MP_USER_ID`
- Tu POS `CAJA01`
- El error: *"Necesito habilitar el producto QR in-store atendido en mi cuenta para usar el endpoint `/instore/qr/v2/orders`. El endpoint responde 404."*

Mientras la API no esté habilitada, **el kiosko seguirá funcionando con el QR estático como fallback**.

### 🧪 Probar pagos QR en modo Test

Mercado Pago provee **tarjetas de prueba** que simulan diferentes escenarios sin usar dinero real. Inicia sesión en la app de Mercado Pago con tu **usuario de test** (no tu cuenta real) y escanea los QR que genere el kiosko.

#### Mastercard de prueba (las más usadas)

| Marca | Número | Vencimiento | CVV | Resultado al pagar |
|-------|--------|-------------|-----|--------------------|
| Mastercard | **5031 7557 3453 0604** | 11/30 | 123 | ✅ Aprobado |
| Mastercard | **5031 4332 1540 6351** | 11/30 | 123 | ❌ Fondos insuficientes |
| Mastercard | **5031 4332 1540 6202** | 11/30 | 123 | ❌ Tarjeta inválida (BIN desconocido) |
| Mastercard | **5031 4332 1540 6210** | 11/30 | 123 | ❌ No autorizado |
| Mastercard | **5031 4332 1540 6228** | 11/30 | 123 | ❌ Error de tarjeta |
| Mastercard | **5031 4332 1540 6285** | 11/30 | 123 | ❌ Llamar al emisor |
| Mastercard | **5031 4332 1540 6293** | 11/30 | 123 | ⚠️ Pedir autorización (no se completa) |

#### Visa de prueba

| Marca | Número | Vencimiento | CVV | Resultado al pagar |
|-------|--------|-------------|-----|--------------------|
| Visa | **4509 9535 6623 3704** | 11/30 | 123 | ✅ Aprobado |
| Visa | **4013 5406 8274 4600** | 11/30 | 123 | ❌ Rechazado (genérico) |
| Visa | **4851 7500 1000 0012** | 11/30 | 123 | ❌ CVV inválido |
| Visa | **4012 8888 8888 1881** | 11/30 | 123 | ❌ Fecha de vencimiento inválida |
| Visa | **4009 1300 0000 0009** | 11/30 | 123 | ❌ Tarjeta reportada como robada |

#### American Express

| Marca | Número | Vencimiento | CVV | Resultado |
|-------|--------|-------------|-----|-----------|
| Amex | **3711 8030 3257 522** | 11/30 | 1234 | ✅ Aprobado |
| Amex | **3707 5850 1100 0009** | 11/30 | 1234 | ❌ Rechazado |

> **Datos a usar en el checkout (datos del pagador ficticio):**
> - Nombre: `APRO` (para aprobadas) o `RECH` (para rechazadas)
> - DNI: `12345678`
> - Email: `test_user_XXXXX@testuser.com` (el de tu cuenta de test)

#### Pasos para probar en el kiosko

1. **Carga `.env` con tokens de test** y `MP_ENVIRONMENT=test`.
2. **Inicia la app:** `cd src/web_app && python main.py test` (o `python main.py` en la Pi).
3. **Sigue el flujo del cliente:** Selecciona servicio → nombre → peso → método de pago → elige **QR Mercado Pago**.
4. El kiosko genera un QR. **Abre tu app de Mercado Pago con la cuenta de test** y escanea el QR.
5. Confirma el pago con la tarjeta de prueba que prefieras.
6. El kiosko detectará el pago (polling cada 3s) y mostrará el paso de éxito.

#### ⚡ Prueba del modo recuperación de órdenes (apagón simulado)

Para verificar que las órdenes huérfanas se cancelan al iniciar:

1. Selecciona servicio → método de pago QR (genera una orden `open` en MP).
2. **Cierra la app o apaga la Pi** (Ctrl+C o `sudo shutdown`).
3. Vuelve a iniciar el kiosko.
4. Revisa la terminal: debería imprimir cuántas órdenes huérfanas se cancelaron. En producción esas órdenes liberarían el slot en MP y permitirían nuevos cobros.

---

## 🗄️ Estructura de la Base de Datos

La aplicación crea automáticamente el archivo `ecoluna_datos.db`. La tabla principal `transacciones` gestiona la cola de trabajo:

* `id_transaccion`: ID único.
* `fecha_hora`: Fecha y hora exactas de la venta.
* `tipo_servicio`: "Lavar", "Secar", "Ambos".
* `monto_pagado`: Costo total cobrado.
* `id_equipo`: Identificador de la máquina asignada (Lavadora 1, Secadora 2).
* `estado`: **Pendiente** (Pagado, esperando ropa) | **En Curso** (Lavando) | **Finalizado**.

---

## 📝 Próximos Pasos (Roadmap)

[x] **Migración a Web:** Extraer la lógica de `customtkinter` y montar el servidor backend/frontend.
[x] **Implementación de íconos:** Reemplazar los emojis por íconos svg.
[x] **Medios de pago múltiples:** Strategy pattern con Monedas, QR MP, y slot para Terminal Point.
[ ] **Integración de Caja de Dinero:** Añadir pulso a través de un módulo relé para abrir el cajón (solenoide 18V) al dar cambio.
[ ] **Auditoría Energética (PZEM-004T):** Implementar monitoreo de consumo eléctrico en tiempo real para evitar que clientes (o personal) seleccionen ciclos de secado en lavadoras asignadas solo para lavado.
[ ] **Acceso Remoto:** Configuración de túnel (ej. Tailscale) para revisión de cortes de caja a distancia.
[ ] **Bypass:** Acoplar Google Authenticator para el paso de autorización de Servicios de Cortesía en el panel de administrador.