# AGENTS.md — EcoLuna Kiosko Payment System

## Overview

This is a **Python/NiceGUI web application** for a laundromat kiosk (EcoLuna). It runs on a Raspberry Pi and controls:
- Coin acceptor (monedero) for payment
- Industrial washing machines via GPIO (optoisolated)
- SQLite database for transaction logging

### Key Paths
```
src/web_app/main.py         # Main NiceGUI app entry point
src/web_app/models.py       # State management (KioskoState dataclass)
src/web_app/database_web.py # Async SQLite operations
src/web_app/hardware.py     # GPIO control for machines/coins
src/web_app/metodos_pago.py # Strategy pattern for payment methods (monedas, terminal)
tools/                      # Hardware test scripts and MercadoPago reference tools
tools/test_voltaje*.py      # GPIO hardware diagnostic scripts
tools/mp_dev/               # MercadoPago integration reference scripts
data/ecoluna_datos.db       # SQLite database file
media/                      # Static assets (logos, images, icons/)
media/icons/                # SVG icons (used instead of emojis for Pi compat)
agent_notation/             # Internal agent notes and TODOs
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
BYPASS_PASSWORD=admin123   # Password for courtesy/bypass service and admin confirmations
```

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