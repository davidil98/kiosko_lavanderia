# AGENTS.md — EcoLuna Kiosko Payment System (v2)

> Documento de orientación para cualquier agente o humano que trabaje en el código.
> Reescrito desde cero en la rama `feature/reestructuracion-v2`.
> La versión anterior (monolítica) está documentada en el historial de Git.

---

## 1. Visión del producto

**EcoLuna Kiosko** es el sistema central de cobro y operación de la lavandería EcoLuna. Corre en una **Raspberry Pi** que actúa como cerebro local:

- Una **pantalla táctil** (cliente) en modo kiosco muestra la selección de servicio, el cobro y la confirmación.
- Un **panel de administración** (operador) en otra pantalla o dispositivo móvil de la red local recibe las órdenes pagadas, pesa la ropa, asigna máquina y dispara el inicio del ciclo.
- El hardware (monedero, lavadoras, secadoras) se controla desde la Pi mediante **GPIO** con optoacopladores.
- Los cobros con tarjeta se hacen en una **terminal Mercado Pago Point** (NEWLAND N950) principalmente, o mostrando un **QR** de Mercado Pago (no recomendado por el momento).
- Toda la operación (órdenes, cortes de caja, catálogo de servicios, máquinas, métricas) se persiste en una base de datos **SQLite** local.

**Roles:**
- **Cliente** — solo consume el kiosko. No se identifica.
- **Operador (admin)** — Moi, David (superadmins) y Capi. Ve y manipula las órdenes.
- **Superadmin** — Moi y David. Único con acceso al CRUD de servicios/maquinas, cortes de caja, métricas y respaldo de fábrica.

**Concepto clave:** la Pi es la fuente de verdad. No hay nube. El sistema debe sobrevivir apagones y recuperar el estado al reiniciar.

---

## 2. Stack y prerrequisitos

- **Python 3.9+** (probado en 3.11).
- **NiceGUI** como framework web + UI. La app es un único proceso `python main.py` que sirve en `http://localhost:8000`.
- **SQLite** con `WAL` para concurrencia entre kiosko y admin.
- **gpiozero + RPi.GPIO** para hardware (cargados solo si están disponibles; en su defecto, modo test con teclado).
- **requests** para el cliente HTTP de Mercado Pago (bloqueante, ejecutado con `asyncio.to_thread`).
- **Highcharts** vía `nicegui_highcharts` para métricas en `/admin/superadmin`.

```bash
pip install -r requirements.txt
```

---

## 3. Estructura del repositorio

```
kiosko_pago/
├── src/
│   └── app/                              # código de la app
│       ├── main.py                       # entrypoint NiceGUI
│       ├── config.py                     # .env, constantes, paths
│       │
│       ├── core/                         # lógica de negocio (sin imports de infra)
│       │   ├── estados.py                # enums: EstadoOrden, Modalidad, MetodoPago, EtapaKanban
│       │   ├── transiciones.py           # única función que muta estado: aplicar(orden, evento)
│       │   ├── orden.py                  # clase Orden
│       │   ├── precio.py                 # calcular_precio(item, peso)
│       │   ├── servicios.py              # carga de catálogo (servicios + segmentaciones)
│       │   ├── maquinas.py               # TypedDict + cache de EQUIPOS
│       │   ├── pagos/                    # Strategy: MetodoPago ABC + Monedas/Mostrador/Point
│       │   ├── cortes.py                 # abrir/cerrar/registrar movimiento
│       │   ├── respaldo.py               # snapshot JSON de los 3 catálogos
│       │   └── reportes.py               # 5 queries de métricas
│       │
│       ├── repo/                         # persistencia (única capa con SQL)
│       │   ├── db.py                     # conexión, WAL, migraciones, seeds
│       │   ├── _row_a.py                 # mapeo row -> dataclass
│       │   ├── transacciones.py
│       │   ├── servicios.py
│       │   ├── segmentaciones.py
│       │   ├── maquinas.py
│       │   ├── cortes.py
│       │   └── respaldos.py
│       │
│       ├── adaptadores/                  # I/O externo
│       │   ├── hardware/                 # GPIO + monedero + control de máquinas
│       │   └── mercado_pago/             # cliente HTTP + Point + polling
│       │
│       ├── eventos/                      # pub/sub in-proc
│       │   ├── bus.py                    # Evento + Bus (asyncio)
│       │   └── tipos.py                  # OrdenCreada, PagoConfirmado, …
│       │
│       └── ui/                           # NiceGUI (capa obediente)
│           ├── kiosko/                   # página cliente + 5 pasos + sidebar + wizard
│           ├── admin/                    # login + dashboard + operativo + superadmin + cortes
│           └── compartido/               # estilos, auth, icono, _componentes reutilizables
│
├── tools/                                # diagnóstico GPIO + referencia MP
│   ├── test_voltaje*.py
│   └── mp_dev/
│
├── media/                                # logos, imágenes, iconos SVG
├── data/                                 # ecoluna_datos.db (gitignored)
├── tests/                                # pytest: precio, transiciones, repo
├── .env / .env.example
├── requirements.txt
├── create_desktop_shortcut.sh
├── AGENTS.md                             # este archivo
└── README.md
```

### Reglas de imports

| Puede importar de | No puede importar de |
|---|---|
| `core/` | `repo/`, `adaptadores/`, `eventos/`, `ui/` |
| `repo/` | `ui/`, `adaptadores/` (excepto tipos) |
| `adaptadores/` | `ui/`, `core/` (excepto tipos) |
| `eventos/` | `ui/`, `repo/`, `adaptadores/` (excepto tipos) |
| `ui/` | cualquiera (es la capa superior) |

**Verificación rápida:**
```bash
# 0 ocurrencias esperadas
grep -r "from nicegui" src/app/core src/app/repo src/app/adaptadores src/app/eventos
grep -r "from gpiozero" src/app/core src/app/repo src/app/ui
grep -r "import requests" src/app/core src/app/repo src/app/ui
grep -rE "SELECT|INSERT|UPDATE|DELETE" src/app/core src/app/ui src/app/adaptadores
```

---

## 4. Comandos principales

### Ejecutar la app

Hay 3 formas equivalentes (todas funcionan gracias a que `main.py` agrega `src/` a `sys.path` automáticamente):

```bash
# Forma 1: desde src/app (la más intuitiva)
cd src/app && python main.py             # producción (en la Pi con hardware)
cd src/app && python main.py test        # modo test (sin GPIO)

# Forma 2: desde src con módulo (usada por CI / smoke tests)
cd src && python -m app.main
cd src && python -m app.main test

# Forma 3: desde la raíz del proyecto
python src/app/main.py
python src/app/main.py test
```

En modo test, las teclas `1`/`2`/`5`/`0` simulan monedas de $1/$2/$5/$10.

### Tests

```bash
cd src/app && python -m pytest ../tests -v
```

Cobertura inicial: `test_precio.py`, `test_transiciones.py`, `test_repo.py`.

### Diagnóstico de hardware (carpeta `tools/`)

```bash
python tools/test_voltaje.py
python tools/test_voltaje_monedero.py
python tools/test_voltaje_key.py
```

### Modo kiosko en la Pi

```bash
./create_desktop_shortcut.sh    # genera KioskoEcoLuna.desktop en el escritorio
```

Abre Chromium en pantalla completa apuntando a `http://localhost:8000`.

---

## 5. Variables de entorno (`.env`)

```env
# Bypass / cortesía
BYPASS_PASSWORD=admin123

# Mercado Pago Point (terminal física)
MP_ENVIRONMENT=prod
MP_PROD_TOKEN=APP_USR-...
MP_TEST_TOKEN=APP_USR-...
MP_TERMINAL_ID=NEWLAND_N950__N950NCC904817363
```

`.env` está en `.gitignore`. `.env.example` documenta las claves esperadas.

---

## 6. Modelo de dominio

### 6.1 Enums (en `core/estados.py`)

| Enum | Valores | Notas |
|---|---|---|
| `EstadoOrden` | `PENDIENTE_PESO`, `PROCESANDO_PAGO`, `PENDIENTE_PAGO`, `PENDIENTE`, `EN_CURSO`, `FINALIZADO`, `CANCELADO` | Cambia solo vía `core.transiciones.aplicar()`. |
| `Modalidad` | `AUTOSERVICIO`, `PERSONALIZADO`, `AUTOSERVICIO_MONEDAS`, `AUTOSERVICIO_POINT`, `AUTOSERVICIO_MOSTRADOR`, `PERSONALIZADO_MONEDAS`, `PERSONALIZADO_POINT`, `PERSONALIZADO_MOSTRADOR`, `BYPASS` | Calculada, no concatenada con f-strings. |
| `MetodoPago` | `MONEDAS`, `POINT`, `MOSTRADOR` | Catálogo cerrado. |
| `EtapaKanban` | `RECIBIDO`, `ALISTANDO`, `LISTO_ENTREGA` | Para órdenes en `Pendiente` que pasan al panel personalizado. |
| `TipoCalculo` | `FIJO`, `POR_KG`, `POR_DURACION` | Cómo se cobra un servicio o segmentación. |

**Regla:** Cero comparaciones con strings para cualquiera de estos enums. `if orden.modalidad == Modalidad.AUTOSERVICIO_POINT`, nunca `if "point" in modalidad`.

### 6.2 Transiciones (`core/transiciones.py`)

```
PENDIENTE_PESO ──(peso aprobado)──> PROCESANDO_PAGO
PENDIENTE_PESO ──(cancelar)──────> CANCELADO

PROCESANDO_PAGO ──(pago monedas)──> PENDIENTE
PROCESANDO_PAGO ──(iniciar Point)─> PENDIENTE_PAGO
PROCESANDO_PAGO ──(mostrador)────> PENDIENTE_PAGO
PROCESANDO_PAGO ──(cancelar)─────> CANCELADO

PENDIENTE_PAGO ──(pago confirmado)─> PENDIENTE
PENDIENTE_PAGO ──(expirar/cancelar)> CANCELADO

PENDIENTE ──(asignar máquina + iniciar)──> EN_CURSO
PENDIENTE ──(cancelar)──────────────────> CANCELADO

EN_CURSO ──(completar)──> FINALIZADO
```

`core.transiciones.aplicar(orden, evento) -> Orden` es la **única** función que muta `orden.estado`. Lanza `TransicionInvalida` si la combinación no está permitida.

### 6.3 Orden (`core/orden.py`)

Dataclass inmutable. Se reconstruye con `dataclasses.replace()` en cada transición.

Campos:
- `id: int` (None si aún no se persiste)
- `servicio_codigo: str`
- `segmentacion_id: int | None`
- `modalidad: Modalidad`
- `peso_kg: float | None`
- `peso_real_kg: float | None`
- `monto: int`
- `metodo_pago: MetodoPago | None`
- `estado: EstadoOrden`
- `etapa_kanban: EtapaKanban | None`
- `maquina_codigo: str | None`
- `nombre_cliente: str`
- `mp_order_id: str | None` (Point)
- `folio_terminal: str | None` (terminal física)
- `created_at: datetime`
- `updated_at: datetime`

### 6.4 Servicios y segmentaciones

- **Servicios** viven en la tabla `servicios` (catálogo data-driven). Se cargan en cada `cargar_servicios()` (sin cache import-time).
- **Segmentaciones** son variantes de un servicio. Mismo cálculo de precio vía `core/precio.calcular_precio()`.
- La unión es polimórfica: una función `calcular_precio(item, peso)` acepta un `Servicio` o una `Segmentacion` indistintamente.

Tipos de cálculo:
- `FIJO` — `precio_fijo` directamente.
- `POR_KG` — `tarifa_por_kg * peso`.
- `POR_DURACION` — `precio_fijo` (placeholder, no se usa actualmente).

### 6.5 Máquinas

Catálogo en la tabla `maquinas`. `core/maquinas.py` expone `EQUIPOS` como cache lazy + `recargar_equipos()` para forzar recarga tras un CRUD del superadmin.

Campos relevantes: `codigo`, `nombre`, `tipo` (`mixto`/`lavado`/`secado`/`doblado`), `capacidad_kg`, `gpio` (pin BCM), `modo` (`pulso`/`sostenido`), `duracion_max_min` (solo para `sostenido`).

**Importante:** al crear o cambiar el GPIO de una máquina, **reiniciar la Pi** para que `adaptadores/hardware/gpio.py` haga `setup()` del pin nuevo.

---

## 7. Capa de persistencia (`repo/`)

- `db.py` se conecta a `data/ecoluna_datos.db` con `WAL`. Crea/migra todas las tablas de forma idempotente al primer `init_db()`.
- Cada tabla tiene su módulo (`transacciones.py`, `servicios.py`, etc.) con funciones nombradas `<verbo>_<entidad>` (`listar_pendientes`, `obtener_por_codigo`, `crear_orden`, `actualizar_estado`, …).
- `_row_a.py` centraliza el mapeo de filas SQLite a dataclasses. Ningún otro archivo hace `dict(row)` para construir modelos.
- Las queries async exponen `_sync` y `_async`; las páginas NiceGUI usan siempre la versión `async` con `asyncio.to_thread` o `run_in_executor`.

**Migraciones:** son aditivas. Si una columna nueva no existe, se añade con `ALTER TABLE`. Nunca se borran columnas en producción.

---

## 8. Hardware y adaptadores

### 8.1 GPIO (`adaptadores/hardware/`)

- `gpio.py` — `init_gpio_lavadoras()` (configura cada pin en `LOW`), `limpiar_pines()` (al apagar la app).
- `monedero.py` — `LectorMonedas(callback)` escucha el pin 21 con debounce de 300 ms. En modo test, ignora GPIO y acepta pulsos por teclado (`1`/`2`/`5`/`0`).
- `maquinas_pin.py` — `ControlMaquinas.activar(codigo)`, `activar_con_duracion(codigo, min)`, `apagar(codigo)`, `recuperar()`. Maneja modo `pulso` (HIGH 0.5s) y `sostenido` (HIGH continuo + tarea asyncio de auto-apagado).

### 8.2 Recuperación tras apagón

`adaptadores/hardware/gpio.py:recuperar_maquinas_sostenidas()` se llama en `app.on_startup`. Lee las órdenes en `EN_CURSO`:
- Si el tiempo transcurrido supera la `duracion_max_min`, marca la orden como `FINALIZADO`.
- Si no, reprograma el auto-apagado con el tiempo restante.

---

## 9. Mercado Pago

### 9.1 Cliente (`adaptadores/mercado_pago/cliente.py`)

Funciones bloqueantes (se llaman con `asyncio.to_thread`):
- `crear_orden_point(amount, descripcion, external_ref, retry_on_409=True) -> dict`
- `consultar_orden(order_id) -> dict`
- `cancelar_orden(order_id) -> bool` (best-effort; la N950 no responde a cancelaciones por API)
- `listar_terminales() -> list`

El token se elige según `MP_ENVIRONMENT` (`prod` o `test`). Si `MP_ENVIRONMENT=prod` y `MP_PROD_TOKEN` está vacío, se hace fallback a `MP_TEST_TOKEN` con un warning.

### 9.2 Polling de Point (`adaptadores/mercado_pago/polling.py`)

Tarea asyncio que cada 5 segundos:
1. Lee órdenes con `estado == PENDIENTE_PAGO` y `modalidad in (AUTOSERVICIO_POINT, PERSONALIZADO_POINT)`.
2. Consulta el estado en MP.
3. Si `status == "paid"`: extrae `transactions.payments[0].id` como folio, llama a `core.transiciones.aplicar(orden, PAGO_CONFIRMADO)`, persiste y publica `PagoConfirmado` en el bus.
4. Si `status in ("expired", "cancelled")`: cancela la orden local y notifica al kiosko.

Arranca en `app.on_startup` y se detiene en `app.on_shutdown`.

### 9.3 Punto Point (terminal física)

- El cliente elige "Pago con Point" en el kiosko.
- `adaptadores/mercado_pago/point.py:crear_orden_point()` envía la orden a la terminal NEWLAND N950 con `expiration_time=PT5M`.
- El kiosko muestra overlay "Procesando pago con Point".
- El polling confirma automáticamente (sin intervención del operador).
- Si el cliente presiona "Regresar", se intenta `cancelar_orden()` best-effort; si falla, hay que cancelar manualmente en la terminal.

---

## 10. Bus de eventos (`eventos/`)

`Bus` es un pub/sub en proceso. Cada suscriptor abre un `asyncio.Queue` por tipo de evento.

```python
bus = Bus()

# Productor (en core/ o adaptadores/)
await bus.publish(PagoConfirmado(orden_id=42))

# Consumidor (en ui/)
cola = bus.subscribe("pago.confirmado")
async for evento in cola:
    refrescar_pantalla(evento.orden_id)
```

Reemplaza los 3 sets de callbacks (`_operativo_refresh_callbacks`, etc.) y los 2 dicts de clients (`_admin_clients`, `_kiosko_clients`) que existían en `services/notifications.py`.

Tipos de evento (en `eventos/tipos.py`): `OrdenCreada`, `PesoAprobado`, `PesoRechazado`, `PagoConfirmado`, `MaquinaAsignada`, `CicloIniciado`, `OrdenFinalizada`, `OrdenCancelada`.

---

## 11. UI NiceGUI

### 11.1 Reglas

- Las páginas **nunca** importan de `core/`, `repo/` o `adaptadores/` directamente para mutar estado. Siempre llaman a una función de `core/` o esperan un evento del bus.
- Toda mutación de UI tras una acción async va por el bus, no por callbacks anidados.
- Cero SQL en la UI. Cero `from gpiozero` en la UI. Cero `import requests` en la UI.
- Los componentes reutilizables viven en `ui/compartido/_componentes.py`:
  - `tarjeta_orden(v: dict, *, acciones: list[Accion])` — una sola implementación para los 3 paneles operativos.
  - `badge_modalidad(m: Modalidad)`, `badge_metodo_pago(m: MetodoPago)`, `badge_servicio(s: str)` — funciones puras, devuelven HTML o un nodo NiceGUI.
  - `dialogo_bypass(on_autorizar)` — reutilizable entre admin operativo y superadmin.

### 11.2 Rutas

| Ruta | Acceso | Descripción |
|---|---|---|
| `/` | público | Pantalla del cliente (5 pasos del wizard). |
| `/admin/login` | público | Login con usuario + contraseña. |
| `/admin` | autenticado | Dashboard con tarjetas de acceso. |
| `/admin/operativo` | autenticado | Bypass, cambio de usuario, kanban de pendientes. |
| `/admin/autoservicio` | autenticado | Aprobar peso, asignar máquina, iniciar ciclo. |
| `/admin/personalizado` | autenticado | Recepción, alistamiento, entrega. |
| `/admin/superadmin` | superadmin | Servicios, segmentaciones, máquinas, calculadora, métricas, respaldo. |
| `/admin/cortes` | autenticado | Abrir caja, registrar movimientos, cerrar caja, historial. |

### 11.3 Wizard del cliente

`ui/kiosko/wizard.py` controla el flujo. 5 pasos:
- `0` — Selección de servicio (mostrando_sub_lavar para "Lavar")
- `1` — Ingreso de nombre
- `2` — Peso (con sub-estado `mostrando_segmentaciones` si el servicio tiene variantes)
- `3` — Selección de método de pago + cobro
- `4` — Éxito (auto-reset a los 7s)

Sub-estados (banderas booleanas, no floats en `paso_actual`):
- `mostrando_sub_lavar`
- `mostrando_segmentaciones`
- `mostrando_metodos_pago`
- `esperando_admin` (con `motivo: "peso" | "pago"`)

---

## 12. Operación

### 12.1 Flujo del cliente (autoservicio)

1. Selecciona servicio (Autolavado / Secado / Personalizado).
2. Ingresa nombre.
3. Si es personalizado y tiene segmentaciones, elige una.
4. Ingresa peso.
5. Orden queda en `PENDIENTE_PESO` y se notifica al admin.
6. Admin aprueba peso → kiosko muestra métodos de pago.
7. Cliente elige método y completa el pago.
8. Orden pasa a `PENDIENTE` (lista para asignar máquina).
9. Admin asigna máquina e inicia ciclo → `EN_CURSO`.
10. Al terminar, `FINALIZADO`.

### 12.2 Flujo del cliente (personalizado)

Igual pero:
- El cliente no paga en el kiosko (queda en `PENDIENTE_PAGO` con `metodo_pago=mostrador`).
- El operador cobra en mostrador, registra el pago → `PENDIENTE`.
- La ropa entra al kanban de personalizado: `RECIBIDO` → `ALISTANDO` → `LISTO_ENTREGA`.

### 12.3 Cortes de caja

- **Abrir** (superadmin + `BYPASS_PASSWORD`): saldo inicial.
- **Movimientos** durante el turno: cualquier admin registra ingresos o egresos.
- **Auto-registro**: al confirmar un pago en efectivo desde el panel operativo, se crea un movimiento de ingreso automáticamente.
- **Cerrar** (superadmin + `BYPASS_PASSWORD`): efectivo contado, sistema calcula esperado vs real, guarda diferencia y notas.
- **Historial**: tabla de cortes cerrados.

### 12.4 Métricas (Highcharts)

Tab "Métricas" en `/admin/superadmin`. Filtros de rango: todo, 7d, 30d, 90d, 1y.

- **KPIs**: órdenes totales, recaudado, kilos lavados, kg/orden promedio.
- **Gráficos**: uso por máquina, horas pico (24 buckets), días pico (7 buckets), consumo promedio por servicio, tasa efectivo vs tarjeta (mensual stacked column).

### 12.5 Respaldo de fábrica

Snapshot automático al primer `init_db()`. El superadmin puede:
- **Crear respaldo ahora** — sobrescribe con el estado actual.
- **Restaurar valores por defecto** — requiere `BYPASS_PASSWORD`. Borra y reinserta los 3 catálogos desde el snapshot. Las órdenes históricas **no** se tocan.

---

## 13. Convenciones de código

- **Python 3.9+**, type hints donde aportan claridad.
- **4 espacios** de indentación, **~120 caracteres** máx. por línea.
- **Dataclasses** para modelos de datos.
- **Enums** en lugar de strings mágicos.
- **Imports**: stdlib → third-party → local. Sin wildcards.
- **Async**: las páginas NiceGUI son `async`. Las funciones de DB y MP se ejecutan con `asyncio.to_thread` o `run_in_executor`.
- **CSS**: las clases siguen BEM-ish (`.orden-card`, `.orden-card__nombre`). Viven en `ui/compartido/estilos.py` como strings.
- **Iconos**: SVGs en `media/icons/`, jamás emojis (problema de fuentes en la Pi).
- **Comentarios**: docstrings en funciones públicas. Inline solo donde el "por qué" no es obvio.

### Paleta del kiosko (Solar High-Contrast)

El kiosko cliente usa una paleta de **alto contraste** optimizada para luz solar directa sobre pantallas VGA cuadradas. Se activa con `<body data-theme="high-contrast">` (solo en el kiosko, **no en el admin**).

| Variable | Color | Uso |
|---|---|---|
| `--bg-primary` | `#000000` | Fondo principal |
| `--bg-card` | `#1c1c1c` | Tarjetas |
| `--bg-elevated` | `#2d2d2d` | Elementos elevados |
| `--text-primary` | `#ffffff` | Texto principal |
| `--accent` | `#00ff00` | Verde neón (botón primario) |
| `--success` | `#00ff00` | Éxito |
| `--error` | `#ff0000` | Error |
| `--warning` | `#ffff00` | Advertencia |
| `--border` | `#ffffff` | Bordes |

**Contraste WCAG AAA verificado:**
- Texto blanco sobre negro: 21:1
- Verde neón sobre negro: 15.3:1
- Gris claro sobre negro: 13.6:1

Para regenerar el CSS de la paleta tras cambios: `python src/app/static/kiosko.css` (no requiere recompilación).

### Favicon

El favicon `.ico` se genera desde `media/logo_slogan.png` con:

```bash
.venv/bin/python tools/build_favicon.py
```

Genera `src/app/static/favicon.ico` con 3 sizes (16, 32, 48). El `main.py` lo carga automáticamente. Si no existe, usa un emoji de fallback (no recomendado para la Pi).

---

## 14. Glosario

| Término | Significado |
|---|---|
| **Kiosko** | Pantalla táctil del cliente. |
| **Wizard** | Flujo de 5 pasos que sigue el cliente. |
| **Orden** | Una transacción pendiente, en curso o finalizada. |
| **Punto Point** | Terminal física Mercado Pago NEWLAND N950. |
| **Bypass** | Servicio de cortesía (lavado gratis). Requiere `BYPASS_PASSWORD`. |
| **Corte de caja** | Ciclo de apertura → movimientos → cierre con arqueo. |
| **Kanban** | Vista de 3 columnas (Recibido / Alistando / Listo) en `/admin/personalizado`. |
| **Segmentación** | Variante de un servicio (ej. "Lava + Seca + Dobla" dentro de Personalizado Ropa). |
| **Respaldo de fábrica** | Snapshot JSON de los 3 catálogos para restaurarlos a un estado conocido. |
