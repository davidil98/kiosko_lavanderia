# AGENTS.md — EcoLuna Kiosko Payment System

## Overview

This is a **Python/NiceGUI web application** for a laundromat kiosk (EcoLuna). It runs on a Raspberry Pi and controls:
- Coin acceptor (monedero) for payment
- Industrial washing machines via GPIO (optoisolated)
- SQLite database for transaction logging

### Key Paths
```
src/web_app/main.py                # Main NiceGUI app entry point
src/web_app/models.py              # State management (KioskoState dataclass)
src/web_app/database_web.py        # Async SQLite operations
src/web_app/hardware.py            # GPIO control for machines/coins
src/web_app/metodos_pago.py        # Strategy pattern for payment methods (monedas, point)
src/web_app/services/notifications.py  # State + admin/kiosko notification registry
src/web_app/services/mercadopago.py    # HTTP client for Mercado Pago Point API
src/web_app/services/point_polling.py  # Background polling task for Point orders
src/web_app/components/            # UI components (kiosko/, admin/, shared.py)
src/web_app/pages/                 # NiceGUI page handlers (kiosko, admin_login, admin_*)
tools/                             # Hardware test scripts and MercadoPago reference tools
tools/test_voltaje*.py             # GPIO hardware diagnostic scripts
tools/mp_dev/                      # MercadoPago integration reference scripts
data/ecoluna_datos.db              # SQLite database file
media/                             # Static assets (logos, images, icons/)
media/icons/                       # SVG icons (used instead of emojis for Pi compat)
agent_notation/                    # Internal agent notes and TODOs
```

---

## Build / Run Commands

### Web Application (Main)
```bash
# Normal mode (requires Raspberry Pi hardware)
cd src/web_app && python main.py

# Test mode (simulates hardware with keyboard input)
cd src/web_app && python main.py test

# In test mode: press 1/2/5/0 keys to simulate $1/$2/$5/$10 coins
```

### Hardware Test Scripts (tools/)
```bash
# Test GPIO voltage on pin 21 (monedero)
python tools/test_voltaje.py

# Test coin reader logic
python tools/test_voltaje_monedero.py

# Test voltage on specific pin
python tools/test_voltaje_key.py
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Testing

**There is no formal test framework.** Use manual testing with test mode.

To run the app in test mode and verify functionality:
1. `cd src/web_app && python main.py test`
2. Use keyboard keys to simulate coins: `1`=$1, `2`=$2, `5`=$5, `0`=$10
3. Navigate through the UI flow: select service → enter name → enter weight → wait for admin weight approval → select payment method → insert coins / wait for terminal approval → confirm

---

## Code Style Guidelines

### Python Version
- **Python 3.9+** required
- Uses type hints where obvious (not enforced strictly)

### Imports
- Standard library first, then third-party, then local
- Avoid wildcard imports (`from module import *`)
- Local relative imports use `from models import X` (web_app directory)

```python
# Correct
from nicegui import ui, app
import asyncio
from models import KioskoState, SERVICIOS_AUTO
import database_web
import hardware

# Legacy style (acceptable in older files)
import sqlite3
from gpiozero import Button
```

### Formatting
- **4 spaces** indentation (not tabs)
- **Max line length**: ~120 characters (informal, use judgment)
- Single blank line between functions/methods within classes
- No blank line between related one-liners

### Naming Conventions
| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `KioskoState`, `ServicioInfo` |
| Functions/methods | snake_case | `registrar_venta`, `seleccionar_servicio` |
| Constants | UPPER_SNAKE | `PIN_MONEDERO`, `SERVICIOS_AUTO` |
| Variables | snake_case | `dinero_ingresado`, `peso_kg` |
| Private attrs | _leading_underscore | `_trigger_change`, `_running` |
| Dataclass fields | snake_case | `nombre`, `precio`, `duracion_min` |

### Type Hints
Use where beneficial but don't over-annotate:

```python
# Good - clear intent
def seleccionar_servicio(self, servicio_nombre: str) -> None:
    ...

def get_faltante(self) -> int:
    ...

# Good - dataclass
@dataclass
class ServicioInfo:
    nombre: str
    precio: int
    duracion_min: int
    modalidad: str = 'autoservicio'

# Acceptable - infer simple types
def reset(self):
    self.servicio_seleccionado = None
```

### Dataclasses (Preferred for Data Models)
Use `@dataclass` for simple data containers:

```python
from dataclasses import dataclass

@dataclass
class ServicioInfo:
    nombre: str
    precio: int
    duracion_min: int
    modalidad: str = 'autoservicio'
    icono: str = '/media/icons/leaf.svg'  # Usar SVG path, no emoji
```

### Error Handling
- Use bare `except Exception` sparingly — prefer specific exceptions
- Hardware errors (GPIO) are caught and logged, system continues in degraded mode
- User errors show notifications via `ui.notify()`

```python
# Hardware errors - graceful degradation
try:
    from gpiozero import Button
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("Warning: Hardware GPIO libraries not found...")

# Async error handling
try:
    await hardware.activar_lavadora(equipo_id)
except Exception as e:
    print(f"Error activating PIN {pin}: {e}")
```

### Async/Await Patterns
- Database operations use `asyncio.run_in_executor()` to avoid blocking
- Use `asyncio.create_task()` for fire-and-forget background tasks
- Hardware callbacks that need UI updates use `asyncio.create_task()`

```python
async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)

async def registrar_venta_async(...):
    return await run_in_executor(_registrar_venta, ...)
```

### NiceGUI Patterns
- Use `@ui.page('/path')` decorator for routes
- Use `ui.refreshable` for dynamic content that needs refresh
- State management via `KioskoState` class passed to UI closures
- Callbacks in lambdas must capture values properly: `lambda s=svc: action(s)`

```python
@ui.page('/')
def kiosko_cliente():
    ui.add_head_html(FONTS_HTML + KIOSKO_CSS)
    # ...

@ui.refreshable
async def vista_ordenes():
    # ...
    await vista_ordenes()
```

### SQL Patterns
- Use parameterized queries (no string formatting)
- WAL mode for concurrent access
- Safe migrations: check column existence before ALTER TABLE

```python
conn.execute('PRAGMA journal_mode=WAL;')
cursor.execute(
    "INSERT INTO transacciones (fecha_hora, tipo_servicio, ...) VALUES (?, ?, ...)",
    (fecha_hora, servicio, monto, ...)
)
```

###   File Organization
```
src/
  web_app/
    main.py          # Routes, UI, callbacks
    models.py        # Data classes and KioskoState
    database_web.py  # Async DB operations
    hardware.py      # GPIO and machine control
    metodos_pago.py  # Strategy pattern: MetodoPago ABC + Monedas/Terminal
tools/
  test_voltaje*.py    # GPIO hardware diagnostic scripts
  mp_dev/             # MercadoPago reference scripts (not used in main flow)
```

### Comments
- Use docstrings for public functions/classes
- Inline comments explain **why**, not **what**
- No comment clutter — code should be self-explanatory

```python
def seleccionar_servicio(self, servicio_nombre: str):
    """Find and select a service by name, reset payment state."""
    for s in SERVICIOS:
        if s.nombre == servicio_nombre:
            # Personalizado skips the payment step
            self.servicio_seleccionado = s
            self.dinero_ingresado = 0
            self.paso_actual = 1
            self._trigger_change()
            return
```

### CSS Conventions
- CSS is defined as multi-line strings in `main.py` (KIOSKO_CSS, ADMIN_CSS)
- Uses custom classes with BEM-like naming: `.orden-card`, `.orden-card__nombre`
- Inline styles only for dynamic values (rare)

---

## Environment Variables

Create `.env` in project root (not committed to git):

```
BYPASS_PASSWORD=admin123                      # Password for courtesy/bypass service and admin confirmations
MP_ENVIRONMENT=prod                            # 'prod' or 'test'
MP_PROD_TOKEN=APP_USR-...                      # Mercado Pago production token
MP_TEST_TOKEN=APP_USR-...                      # Mercado Pago test token
MP_TERMINAL_ID=NEWLAND_N950__N950NCC904817363  # Unique Point terminal ID
```

## Integración Mercado Pago Point

Cobro automático en terminal Point. El kiosko envía la orden a la terminal física; el cliente paga y el sistema confirma sin intervención del operador.

### Flujo
1. Cliente selecciona servicio → ingresa peso → admin valida → elige **Punto Point**.
2. Kiosko llama `services/mercadopago.crear_orden_point()` con `asyncio.to_thread` (no bloquea el event loop).
3. Si éxito: orden pasa a `Pendiente-peso` → `Procesando-pago` → `Pendiente-pago` con `modalidad=autoservicio-point` o `personalizado-point` y `mp_order_id` poblado.
4. Kiosko muestra pantalla de espera "Procesando pago con Point".
5. `services/point_polling.py` vigila cada orden con `mp_order_id` no vacío. Polling cada 5s.
6. Al detectar `status="paid"`:
   - `aprobar_pago_terminal_async` con `folio = data.transactions.payments[0].id` (folio automático, no manual).
   - `numero_transaccion_terminal` se guarda con ese id.
   - Kiosko notificado → avanza a pantalla de éxito.
7. Si expira (5 min default) o se cancela en MP: orden local se borra, kiosko notificado y devuelto a métodos de pago.

### Cancelación manual
- **La terminal NEWLAND N950 no responde a cancelaciones por API**. Hay que cancelar manualmente en la terminal.
- El kiosko intenta `mercadopago.cancelar_orden()` best-effort cuando el cliente presiona "Regresar", pero si falla, debe hacerse en la terminal física.
- El operador también puede cancelar desde `/admin/operativo` con el botón existente (la terminal quedará con la orden encolada hasta cancelar manualmente).

### Selección de terminal
- Por ahora solo hay una terminal: `MP_TERMINAL_ID=NEWLAND_N950__N950NCC904817363` (hardcoded en `.env`).
- Si en el futuro hay varias, agregar selector en `/admin/settings` que liste con `listar_terminales()`.

### Archivos
- `services/mercadopago.py` — cliente HTTP (crear_orden_point, consultar_orden, cancelar_orden, listar_terminales)
- `services/point_polling.py` — tarea de fondo `iniciar_polling()` / `detener_polling()`
- `services/point_polling.py:_extraer_pago_id` — extrae `transactions.payments[0].id` para guardarlo como folio
- `database_web.py` — columna `mp_order_id` (migración automática), `obtener_ordenes_point_pendientes_async`, `guardar_mp_order_id_async`, `obtener_mp_order_id_async`
- `metodos_pago.py` — `MetodoTerminalPoint` ahora es "Punto Point" (no "Terminal Point"); usa `mercadopago.crear_orden_point`
- `components/kiosko/paso_peso.py` — rama de espera "Procesando pago con Point"
- `components/admin/operativo_seccion.py` — tarjeta Point sin botón "Confirmar" (es automático)
- `pages/admin_operativo.py` — `confirmar_pago` rechaza confirmaciones manuales de Point
- `components/shared.py:badge_metodo_pago` — badge "Point" en azul

---

## Common Tasks

### Adding a New Service
1. Add to `SERVICIOS_AUTO` or `SERVICIOS_PERSONALIZADO` in `models.py`
2. Update prices/names as needed in `main.py` UI flow

### Adding a New Machine
1. Edit `EQUIPOS` dict in `hardware.py`
2. Add GPIO pin mapping
3. Physical wiring to Raspberry Pi required

### Adding a New Payment Method
Architecture: **Strategy + Open/Closed**. `MetodoPago` is the abstract base in `src/web_app/metodos_pago.py`.

1. Create a new class extending `MetodoPago` in `metodos_pago.py`
2. Implement `async procesar_pago() -> ResultadoPago`
3. Implement `render_panel(on_cancelar, on_pago_exitoso)` using NiceGUI
4. Add the class to `METODOS_PAGO_DISPONIBLES`
5. The kiosko will auto-show it in paso 2 (selección de método de pago)

Currently implemented:
- `MetodoMonedas` (`codigo="monedas"`) — coin acceptor (self-service)
- `MetodoTerminalPoint` (`codigo="terminal"`) — manual card-terminal payment, approved by admin

Approval flow:
- After the customer enters weight on the kiosk, the order is created with `estado='Pendiente-peso'` and the kiosk shows a "waiting for operator" overlay.
- The admin sees the order under `/admin/autoservicio` in "Esperando validación de peso" and clicks **Aprobar** or **Rechazar**.
- If approved, the order moves to `estado='Procesando-pago'` and the kiosk moves to payment-method selection.
- The admin sees weight-approved orders in `/admin/autoservicio` under **Procesando pago**:
  - While the customer pays with **coins** (autoservicio only), the order stays in `Procesando-pago` and automatically moves to `Pendiente` once payment is complete.
  - If the customer chooses **Terminal**, the order becomes `estado='Pendiente-pago'`, the kiosk shows "processing payment" overlay, and the admin enters an optional transaction folio and confirms.
  - For **personalizado**, **"Pagar en mostrador"** creates a `Pendiente-pago` record with `modalidad='personalizado-pendiente-pago'`; the admin confirms the cash payment before the order moves to `Pendiente`.
- This applies to both **autoservicio** and **personalizado** services. Personalized orders only move to `/admin/personalizado` once they reach `estado='Pendiente'`.
- **Coin payment is disabled for personalized services**; they can only pay by terminal or with cash at the counter (both require admin approval).
- **Cancellation at any point deletes the pending record** from the database, both for autoservicio and personalized.
- Bypass/courtesy orders are created directly in `estado='Pendiente'` (ready for machine assignment), so they never appear in "Procesando pago".
- The customer can press **Regresar** on any waiting overlay to cancel the pending record.

### Sub-state Pattern for Wizard Pasos
The wizard uses `paso_actual: int` (0, 1, 2, 3, 4) plus boolean flags for sub-states inside a paso:
- `mostrando_sub_lavar` — true while showing the Lavar sub-menu inside paso 0
- `mostrando_metodos_pago` — true while showing payment method selection inside paso 2
- `esperando_aprobacion_admin` — true while the kiosk is waiting for admin approval (weight or terminal payment)
- `motivo_espera` — `"peso"` or `"pago"`, used to customize the waiting overlay text

**Do not use float or non-int types for `paso_actual`.** When adding a new sub-state, follow this pattern (set the boolean + `_trigger_change()`).

### Database Migrations
Add columns safely in `database_web.py`:
```python
cursor.execute("PRAGMA table_info(transacciones)")
cols_existentes = {row[1] for row in cursor.fetchall()}
if 'new_column' not in cols_existentes:
    cursor.execute("ALTER TABLE transacciones ADD COLUMN new_column TEXT DEFAULT ''")
```

---

## Iconos SVG (Reemplazo de Emojis)

**Problema**: Los emojis no renderizan correctamente en la Raspberry Pi (dependen de fuentes del sistema). La solución es usar íconos SVG en lugar de emojis en toda la UI.

### Archivos SVG disponibles
Ubicación: `media/icons/` — 19 SVGs creados con estilo consistente (24x24, `stroke="currentColor"` o fill fijo):

| Archivo | Uso |
|---------|-----|
| `basket.svg` | Kanban "Alistando" |
| `bed.svg` | Edredones (personalizado) |
| `box.svg` | Kanban "Listo para Entrega" |
| `check.svg` | Éxito / orden registrada |
| `circle-orange.svg` | Badge "En Proceso" |
| `circle-yellow.svg` | Badge "Pendiente" |
| `gear.svg` | Máquina en uso / asignada |
| `inbox.svg` | Kanban "Recibido" |
| `leaf.svg` | Autolavado (opcional) |
| `money-bag.svg` | Cambio en éxito |
| `notes.svg` | Notas en kanban |
| `scale.svg` | Peso (paso 2) |
| `shirt.svg` | Ropa (personalizado), admin |
| `sleep.svg` | Estado vacío sin máquinas |
| `ticket.svg` | Cortesía / Bypass |
| `user.svg` | Chip de operador |
| `warning.svg` | Capacidad excedida |
| `wave.svg` | Bienvenida admin |
| `wind.svg` | Secado |

### Emoji → SVG: estado actual

| Archivo | Emojis pendientes | Prioridad |
|---------|-------------------|-----------|
| `src/web_app/models.py` | 0 | Alta |
| `src/web_app/main.py` | 10 (UI kiosko + admin) | Alta |
| `src/web_app/hardware.py` | 1 (línea 101, consola) | Media |
| `tools/test_voltaje*.py` | 4 (consola, desarrollo) | Baja |

### Patrón de reemplazo

```python
# Antes (emoji en ui.html)
ui.html('<div class="cambio-box">💰 Su cambio: $X</div>')

# Después (SVG img)
ui.html(
    '<div class="cambio-box">'
    '<img src="/media/icons/money-bag.svg" style="width:20px;height:20px;vertical-align:middle;margin-right:6px;">'
    f'Su cambio: ${cambio}</div>'
)

# Alternativa con ui.image
with ui.element('div').classes('dash-card-icon'):
    ui.image('/media/icons/shirt.svg').style('width:48px;height:48px;')
```

### Verificación
1. `cd src/web_app && python main.py test`
2. Visitar `/` y `/admin` — confirmar que los SVGs cargan correctamente
3. Si un SVG no aparece, verificar que `app.add_static_files('/media', MEDIA_DIR)` esté activo en `main.py`

### Documentación detallada
Ver `agent_notation/icons_todo.md` para mapeo completo por línea y consejos de implementación.

---

## Roles y Superadministrador

- `Moi` y `David`: **superadmins** (acceso a `/admin/superadmin` y al CRUD de servicios).
- `Capi`: admin normal (operativo, autoservicio, personalizado; no ve el superadmin).
- Definido en `src/web_app/services/auth.py:SUPERADMINS`.
- `es_superadmin()` consulta el usuario actual de la sesión.

## Servicios Data-Driven (catálogo en DB)

Desde esta branch, el catálogo de servicios **vive en la tabla `servicios`** de SQLite en vez de estar hardcoded en `models.py`. El kiosko lee en cada render y los cambios se reflejan al instante.

### Tabla `servicios`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | |
| `codigo` | TEXT UNIQUE | Identificador lógico (`autolavado`, `secado`, `pers_ropa`, `pers_edredon`) |
| `nombre` | TEXT | Visible al cliente |
| `modalidad` | TEXT | `autoservicio` o `personalizado` |
| `icono` | TEXT | Path SVG |
| `tipo_calculo` | TEXT | `fijo`, `por_kg`, `por_duracion` |
| `precio_fijo` | INTEGER | Para `fijo` y `por_duracion` |
| `tarifa_por_kg` | REAL | Para `por_kg` |
| `duracion_min` | INTEGER | Duración estimada del ciclo |
| `limite_kg` | INTEGER | NULL = sin límite |
| `tipos_equipo` | TEXT | CSV de tipos: `mixto,lavado,secado` |
| `orden` | INTEGER | Posición en pantalla |
| `activo` | INTEGER | 0/1, soft delete |

Seed inicial: 4 servicios (Autolavado $45 fijo, Secado $50 fijo, Pers-Ropa $30/kg, Pers-Edredones $150 fijo). Solo se inserta si la tabla está vacía.

### Funciones clave

- `cargar_servicios(solo_activos=True) -> list[ServicioInfo]` — recarga cada vez que se llama.
- `get_servicio_por_codigo(codigo) -> ServicioInfo | None` — para `state.seleccionar_servicio(codigo)`.
- `calcular_precio(servicio, peso_kg) -> int` — devuelve el precio final según `tipo_calculo`.
- `database_web.listar_servicios_async()`, `obtener_servicio_por_codigo_async()`, `actualizar_servicio_async()`.

### Compatibilidad

`SERVICIOS_AUTO`, `SERVICIOS_PERSONALIZADO` y `SERVICIOS` ahora son **funciones** (callables) que invocan `cargar_servicios()`. El código que hacía `from models import SERVICIOS_AUTO` debe usar `SERVICIOS_AUTO()` o migrar a `cargar_servicios()`. `state.seleccionar_servicio(nombre)` cambió a `state.seleccionar_servicio(codigo)`.

## Estado del branch

- ✅ Segment 1: Servicios data-driven sin CRUD.
- ✅ Segment 2: Tabla `segmentaciones` y nuevo paso en kiosko.
- ✅ Segment 3: CRUD de servicios y segmentaciones en `/admin/superadmin`.
- ✅ Segment 4: Tabla `maquinas` y `hardware.py` data-driven.
- ✅ Segment 4.5: Respaldo de fábrica (default snapshot).
- ✅ Segment 5: Métricas con Highcharts en `/admin/superadmin`.
- ✅ Segment 6: Cortes de caja en `/admin/cortes`.

## Cortes de Caja

Ruta: `/admin/cortes`. Accesible para **todos los admins autenticados**. Tarjeta en el dashboard admin para todos.

### Tablas

- `cortes_caja` — el ciclo de apertura/cierre con saldo inicial, real, esperado y diferencia.
- `movimientos_caja` — todos los ingresos y egresos manuales y automáticos.

### Flujo

1. **Abrir caja** (solo superadmin + `BYPASS_PASSWORD`): se registra saldo inicial.
2. **Movimientos durante el turno**: cualquier admin/socio/superadmin registra ingresos o egresos con tipo, monto y concepto predefinido. No requiere `BYPASS_PASSWORD`.
3. **Cerrar caja** (solo superadmin + `BYPASS_PASSWORD`): se ingresa el efectivo contado, sistema calcula esperado vs real, guarda diferencia y notas.
4. **Historial**: tabla de cortes cerrados con sus datos y notas.

### Auto-registro

Cuando un admin confirma un pago en efectivo desde el panel operativo (`confirmar_pago` con modalidad `pendiente-pago` o `mostrador`), el sistema crea automáticamente un movimiento de **ingreso** en el corte activo, con el monto y la descripción del servicio. Esto evita que el operador tenga que registrar manualmente cada pago de personalizado. Los **cambios** dados al cliente se siguen registrando manualmente como egreso "Cambio a cliente".

### Archivos

- `database_web.py` — tablas `cortes_caja` y `movimientos_caja` con índices, 6 helpers (`obtener_corte_activo`, `abrir_corte`, `cerrar_corte`, `listar_cortes`, `registrar_movimiento`, `listar_movimientos`).
- `pages/admin_cortes.py` — la página completa con 3 secciones.
- `pages/admin_operativo.py` — auto-registro de movimiento al confirmar pago mostrador.
- `pages/admin_dashboard.py` — tarjeta "Cortes de Caja" para todos los admins.

## Métricas con Highcharts

Tab "Métricas" en `/admin/superadmin`. Usa `nicegui_highcharts` (instalado en el venv). Filtro de rango arriba: "Todo el historial", "Últimos 7 días", "Último mes", "Últimos 3 meses", "Último año".

### KPIs (cards superiores)

4 métricas globales: órdenes totales, recaudado, kilos lavados, promedio kg/orden.

### Gráficos

1. **Uso por máquina** — pie chart, número de servicios por `id_equipo`.
2. **Horas pico del día** — column chart, 24 buckets (00:00-23:00).
3. **Días pico de la semana** — column chart, 7 buckets (Dom-Sáb).
4. **Consumo promedio por servicio** — bar chart con doble eje Y (kg prom y monto prom).
5. **Tasa de uso efectivo vs tarjeta** — stacked column por mes. Mapeo: `monedas`→Efectivo, `point`→Tarjeta (Point), `terminal`→Tarjeta (Terminal), `pendiente-pago`/`mostrador`→Efectivo (mostrador).

### Helpers en `database_web.py`

- `reporte_uso_por_maquina_async(desde, hasta)` — `[{id_equipo, n_servicios, total_kg, total_min}]`
- `reporte_horas_pico_async(desde, hasta)` — 24 buckets `[{hora, n}]`
- `reporte_dias_pico_async(desde, hasta)` — 7 buckets `[{dow, nombre, n}]`
- `reporte_consumo_promedio_async(desde, hasta)` — `[{tipo_servicio, n, kg_prom, kg_total, monto_prom, monto_total}]`
- `reporte_tasa_pago_async(desde, hasta)` — `[{mes, Efectivo, Tarjeta (Point), Tarjeta (Terminal), Efectivo (mostrador), n, monto_total}]`
- `reporte_resumen_async(desde, hasta)` — `{n_orden, recaudado, kg_total, kg_prom}`

Las funciones aceptan fechas como string `YYYY-MM-DD` o vacío para "todo el historial". Filtra automáticamente estados no finalizados (`Pendiente-peso`).

## Respaldo de fábrica (default snapshot)

El primer `init_db()` guarda un snapshot automático de los catálogos data-driven (`servicios`, `segmentaciones`, `maquinas`) en la tabla `_backup_default`. El superadmin puede:

- **Crear respaldo ahora**: sobrescribe el snapshot con el estado actual. Útil cuando ya configuraste el catálogo a tu gusto y quieres que ese sea el nuevo "punto de retorno".
- **Restaurar valores por defecto**: borra el estado actual de los 3 catálogos y los reemplaza con el snapshot. Las órdenes históricas **no** se tocan. Requiere `BYPASS_PASSWORD`.

### Tabla `_backup_default`

| Columna | Tipo | Descripción |
|---|---|---|
| `tabla` | TEXT PK | `servicios`, `segmentaciones` o `maquinas` |
| `datos` | TEXT (JSON) | Snapshot serializado de todas las filas |
| `created_at` | TEXT | Fecha del último respaldo |
| `nota` | TEXT | Motivo (ej. "Respaldo manual") |

### Helpers en `database_web.py`

- `listar_backups_async()` — devuelve metadata de los 3 snapshots.
- `obtener_backup_async(tabla)` — devuelve el dict completo con `datos: list[dict]`.
- `crear_backup_async(tabla, nota)` — sobrescribe el snapshot de una tabla.
- `crear_backup_completo_async(nota)` — sobrescribe los 3.
- `restaurar_backup_async(tabla) -> (ok, n_filas)` — borra y reinserta.
- `restaurar_backup_completo_async()` — restaura los 3.

## Máquinas (catálogo de hardware)

El catálogo de máquinas (lavadoras, secadoras) vive en la tabla `maquinas` de SQLite. `hardware.EQUIPOS` se carga de la DB al primer acceso y se cachea en memoria.

### Tabla `maquinas`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | |
| `codigo` | TEXT UNIQUE | Identificador lógico (`lavasecadora_1`) |
| `nombre` | TEXT | Visible al admin |
| `tipo` | TEXT | `mixto` / `lavado` / `secado` / `doblado` |
| `capacidad_kg` | INTEGER | Capacidad de carga |
| `gpio` | INTEGER | Pin BCM en la Raspberry |
| `modo` | TEXT | `pulso` (0.5s) o `sostenido` (HIGH continuo) |
| `duracion_max_min` | INTEGER | Tiempo máx. de seguridad para modo sostenido |
| `orden` | INTEGER | Posición en panel |
| `activa` | INTEGER | 0/1, soft delete |

Seed inicial: 4 máquinas (lavasecadora 1-3 + secadora 1). Solo se inserta si la tabla está vacía.

### API de hardware.py

`EQUIPOS` ahora es un **proxy dinámico** que lee del cache:

```python
# Antes (sigue funcionando):
eq = hardware.EQUIPOS["lavasecadora_1"]
for codigo, eq in hardware.EQUIPOS.items():
    ...

# Nuevo: forzar recarga desde la DB tras editar
hardware.recargar_equipos()
```

- `get_equipos() -> dict` — devuelve el cache, lo carga de la DB si está vacío.
- `recargar_equipos() -> dict` — fuerza recarga (llamar después de editar desde el superadmin).

**Importante:** al agregar una nueva máquina con un GPIO diferente, **reiniciar el kiosko** para que `init_gpio_lavadoras()` haga el setup del pin. El sistema avisa de esto en el `ui.notify` tras crear.

### Validación de GPIO

La DB no enforce unique en GPIO (puede haber dos máquinas con el mismo GPIO si una está desactivada). La validación la hace la UI al crear/editar (`existe_gpio_async(gpio, id_excluir)`). La UI muestra el error antes de intentar el UPDATE.

### CRUD en `/admin/superadmin`

Tab **Máquinas** (entre Segmentaciones y Calculadora). Botones:

- **+ Crear máquina** — diálogo con código, nombre, tipo, GPIO, capacidad, modo, duración máx sostenido. Valida GPIO duplicado y código único.
- **✎ Editar** — diálogo con todos los campos, incluye checkbox de activa.
- **⏸/▶ Activar/Desactivar** — soft delete.
- **🗑 Eliminar** — diálogo de confirmación con `BYPASS_PASSWORD`. Hard delete solo si no hay órdenes históricas con esa máquina; si las hay, devuelve `False` y se debe desactivar.

### Archivos

- `database_web.py` — tabla `maquinas` con migración, helpers (`listar_maquinas_async`, `obtener_maquina_por_codigo_async`, `crear_maquina_async`, `actualizar_maquina_async`, `eliminar_maquina_hard_async`, `existe_gpio_async`).
- `hardware.py` — `EQUIPOS` como proxy dinámico, `get_equipos()`, `recargar_equipos()`. El resto del código no requiere cambios porque la API del dict se mantiene.
- `pages/admin_superadmin.py` — tab Máquinas con CRUD completo.

## Panel Superadministrador

Ruta: `/admin/superadmin`. Acceso restringido con `redirigir_si_no_superadmin()` (solo `Moi` y `David`). Visible como tarjeta en el dashboard admin cuando el usuario actual es superadmin.

### Tabs

1. **Servicios y Tarifas**: lista los 4 servicios con su tipo de cálculo, precio, duración, límite y tipos de equipo. Botones:
   - **✎ Editar**: abre un diálogo con todos los campos editables y un preview en vivo del precio. Requiere `BYPASS_PASSWORD` para confirmar.
   - **⏸/▶ Activar/Desactivar**: soft delete, no afecta órdenes históricas.

2. **Segmentaciones**: agrupa por servicio, lista todas las segmentaciones. Editar/activar con el mismo patrón.

3. **Calculadora**: herramienta de preview que simula el precio de un servicio o segmentación con un peso dado. Útil para responderle al cliente en mostrador. Disponible también para admins normales (útil para cualquier operador).

### Segunda barrera

Todos los cambios (servicios y segmentaciones) requieren confirmar con la contraseña de bypass (`BYPASS_PASSWORD`, default `admin123`). Si la contraseña no coincide, se muestra una notificación negativa y no se aplica el cambio.

### Cambios al instante

El kiosko y el panel operativo leen la DB en cada render, por lo que cualquier cambio en servicios/segmentaciones se refleja al instante. No requiere reiniciar el kiosko.

### Estructura

- `src/web_app/pages/admin_superadmin.py` — la página completa con sus 3 tabs.
- `src/web_app/pages/admin_dashboard.py` — agrega la tarjeta "Superadmin" condicional.
- `src/web_app/services/auth.py:redirigir_si_no_superadmin()` — guarda de acceso.

## Segmentaciones (catálogo anidado)

Una segmentación es una **variante** dentro de un servicio. Ejemplos:
- "Personalizado – Ropa" tiene "Lava + Seca + Dobla", "Solo Lava + Exprime", "Lava + Seca".
- "Personalizado – Edredones" tiene "Lava + Seca", "Solo Lavado".

### Tabla `segmentaciones`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | |
| `servicio_id` | INTEGER FK | Referencia a `servicios.id` (CASCADE) |
| `codigo` | TEXT | Identificador lógico único por servicio |
| `nombre` | TEXT | Visible al cliente |
| `descripcion` | TEXT | Texto explicativo |
| `tipo_calculo` | TEXT | `fijo` / `por_kg` / `por_duracion` |
| `precio_fijo` | INTEGER | Para `fijo` y `por_duracion` |
| `tarifa_por_kg` | REAL | Para `por_kg` |
| `duracion_min` | INTEGER | Duración estimada |
| `orden` | INTEGER | Posición en pantalla |
| `activo` | INTEGER | 0/1, soft delete |

UNIQUE(`servicio_id`, `codigo`). Seed inicial: 3 segmentaciones para `pers_ropa` y 2 para `pers_edredon`.

### Flujo del kiosko

1. Cliente selecciona servicio en paso 0.
2. Ingresa peso en paso 2.
3. **Si el servicio tiene segmentaciones**, paso 2.5 muestra las opciones con precio calculado en vivo.
4. Cliente elige segmentación → paso 3 (métodos de pago).
5. **Si el servicio NO tiene segmentaciones**, va directo de paso 2 a paso 3.

### Cálculo de precio

`calcular_precio(item, peso_kg)` funciona idéntico para `ServicioInfo` y `SegmentacionInfo`. La función `state.get_item_cobro()` devuelve la segmentación si está seleccionada, si no el servicio.

### Helpers en `models.py`

- `SegmentacionInfo` (dataclass).
- `cargar_segmentaciones(servicio_id=None, solo_activos=True) -> list[SegmentacionInfo]`.
- `get_segmentacion_por_id(id_seg) -> SegmentacionInfo | None`.
- `format_precio(item, peso_kg) -> str` — formato visual (`$45` o `$30/kg`).

### En el admin

Cuando se completa el pago, `finalizar_pago` concatena el nombre de la segmentación al `tipo_servicio` (ej. "Personalizado – Ropa · Lava + Seca + Dobla") para que el admin lo vea en sus tarjetas.
Ver `agent_notation/icons_todo.md` para mapeo completo por línea y consejos de implementación.