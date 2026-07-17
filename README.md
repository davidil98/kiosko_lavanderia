# EcoLuna Kiosko — Sistema de cobro y operación 🌙🫧

Sistema central de administración, cobro y control de hardware para la **Lavandería EcoLuna**. Diseñado para correr en una **Raspberry Pi** como cerebro local de la operación.

> **v2** — Reestructurado desde cero en la rama `feature/reestructuracion-v2`.
> La versión anterior (monolítica) está en el historial de Git.

---

## ¿Qué hace?

- **Pantalla táctil del cliente (kiosko):** selección de servicio, ingreso de nombre, peso, cobro con monedas o tarjeta, y confirmación.
- **Panel de administración:** un operador (en otra pantalla o móvil) recibe las órdenes, pesa la ropa, asigna la máquina e inicia el ciclo.
- **Control de hardware:** GPIO sobre optoacopladores y relés. Activa el pulso de inicio de lavadoras/secadoras LG (6V) y dispara el solenoide del cajón de dinero (por el momento no hay selenoide, se abre la caja manualmente).
- **Cobros con tarjeta:** terminal física **Mercado Pago Point** (NEWLAND N950).
- **Persistencia local:** SQLite en `data/ecoluna_datos.db`. Sin nube. Sobrevive apagones.

---

## Hardware

- **Cerebro:** Raspberry Pi (Zero 2 W / 3B+ / 4).
- **Pantallas:**
  - 1x táctil (cliente) con Chromium en modo kiosko.
  - 1x monitor o dispositivo móvil en la red local (admin).
- **Electrónica:**
  - Optoacopladores (ej. 4N25) para aislar el botón Inicio/Pausa de las lavadoras LG.
  - Módulo relé para el solenoide (12-18V) de la caja de billetes/cambio (por el momento no hay selenoide, se abre la caja manualmente).
  - Aceptador de monedas multimoneda con debounce por software (300 ms).
- **Cobro con tarjeta:** terminal Mercado Pago Point NEWLAND N950.

---

## Stack

- **Python 3.9+**
- **NiceGUI** como framework web + UI. Un solo proceso sirve `http://localhost:8000`.
- **SQLite** con `WAL` para concurrencia.
- **gpiozero + RPi.GPIO** para hardware.
- **requests** para Mercado Pago (HTTP bloqueante con `asyncio.to_thread`).
- **Highcharts** vía `nicegui_highcharts` para métricas.

---

## Instalación y arranque

```bash
# 1. Dependencias
pip install -r requirements.txt

# 2. Configurar credenciales
cp .env.example .env
# editar .env con MP_PROD_TOKEN, MP_TEST_TOKEN, MP_TERMINAL_ID, BYPASS_PASSWORD

# 3. Arrancar
cd src/app
python main.py          # producción (en la Pi con hardware)
python main.py test     # modo test (sin GPIO, monedas simuladas con teclado)
```

En modo test, en cualquier punto del kiosko (`/`), las teclas `1`/`2`/`5`/`0` simulan monedas de $1/$2/$5/$10.

---

## Tests

```bash
cd src/app
python -m pytest ../tests -v
```

Cobertura inicial: precio, transiciones de estado, repositorio.

---

## Diagnóstico de hardware

```bash
python tools/test_voltaje.py            # pulso genérico
python tools/test_voltaje_monedero.py   # pin del aceptador de monedas
python tools/test_voltaje_key.py        # modo teclado
```

---

## Modo kiosko en la Pi

```bash
./create_desktop_shortcut.sh
```

Genera `KioskoEcoLuna.desktop` en el escritorio. Al ejecutarlo:
1. Inicia el servidor NiceGUI en segundo plano (puerto 8000).
2. Abre Chromium en modo incógnito, sin barras, pantalla completa, apuntando a `http://localhost:8000`.

---

## Flujo de operación

### Cliente (autoservicio)
1. Selecciona servicio (Autolavado / Secado / Personalizado).
2. Ingresa su nombre.
3. Ingresa el peso.
4. Elige método de pago (monedas o Point).
5. Completa el pago.
6. Espera a que el operador asigne máquina.
7. El operador inicia el ciclo.

### Cliente (personalizado)
Igual pero el pago se hace en mostrador o con tarjeta. La ropa entra al kanban de personalizado: **Recibido → Alistando → Listo para Entrega**.

### Operador
- Ve la cola de órdenes pendientes.
- Aprueba el peso (o lo rechaza, pidiendo re-pesar).
- Asigna la máquina.
- Inicia el ciclo (pulso GPIO).
- Al terminar, marca como finalizado.
- Recibe pagos en efectivo del personalizado (Recibe: x, dar cambio: y) y se registra movimiento automáticamente.

### Superadmin
- CRUD de servicios, segmentaciones y máquinas.
- Métricas con Highcharts (uso por máquina, horas pico, días pico, etc.).
- Respaldo de fábrica de los 3 catálogos.
- Cortes de caja (abrir, registrar movimientos, cerrar, historial).

---

## Medios de pago

El sistema acepta **monedas** y **Punto Point** (terminal física NEWLAND N950). La arquitectura de pagos es **Strategy + Open/Closed**: añadir un nuevo método es crear una clase en `core/pagos/` y registrarla en la lista de disponibles.

### Configurar Mercado Pago

```env
# .env
MP_PROD_TOKEN=APP_USR-...
MP_TEST_TOKEN=APP_USR-...
MP_ENVIRONMENT=prod      # o "test"
MP_TERMINAL_ID=NEWLAND_N950__...
```

El cliente HTTP (`adaptadores/mercado_pago/cliente.py`) lee `MP_ENVIRONMENT` y elige el token correcto. Si `MP_ENVIRONMENT=prod` y `MP_PROD_TOKEN` está vacío, hace fallback a `MP_TEST_TOKEN` con un warning.

### Tarjetas de prueba (entorno test)

| Marca | Número | Vencimiento | CVV | Resultado |
|-------|--------|-------------|-----|-----------|
| Mastercard | `5031 7557 3453 0604` | 11/30 | 123 | ✅ Aprobado |
| Mastercard | `5031 4332 1540 6351` | 11/30 | 123 | ❌ Fondos insuficientes |
| Visa | `4509 9535 6623 3704` | 11/30 | 123 | ✅ Aprobado |
| Visa | `4013 5406 8274 4600` | 11/30 | 123 | ❌ Rechazado |
| Amex | `3711 8030 3257 522` | 11/30 | 1234 | ✅ Aprobado |

> Datos del pagador ficticio:
> - Nombre: `APRO` (aprobadas) o `RECH` (rechazadas)
> - DNI: `12345678`
> - Email: el de tu cuenta de test

### ⚠️ Importante

- **Nunca** commitees `.env`. Está en `.gitignore`, pero verifica antes de `git add`.
- Al cambiar entre test y producción solo edita `.env` y reinicia. No se toca código.

---

## Estructura del proyecto

```
kiosko_pago/
├── src/app/                      # código de la app
│   ├── main.py                   # entrypoint NiceGUI
│   ├── config.py
│   ├── core/                     # lógica de negocio (sin infra)
│   │   ├── estados.py            # enums: EstadoOrden, Modalidad, MetodoPago, …
│   │   ├── transiciones.py       # única función que muta estados
│   │   ├── orden.py              # clase Orden
│   │   ├── precio.py             # calcular_precio(item, peso)
│   │   ├── servicios.py
│   │   ├── maquinas.py
│   │   ├── pagos/                # Strategy: Monedas, Point, Mostrador
│   │   ├── cortes.py
│   │   ├── respaldo.py
│   │   └── reportes.py
│   │
│   ├── repo/                     # persistencia (única capa con SQL)
│   │   ├── db.py
│   │   ├── _row_a.py             # row -> dataclass
│   │   ├── transacciones.py
│   │   ├── servicios.py
│   │   ├── segmentaciones.py
│   │   ├── maquinas.py
│   │   ├── cortes.py
│   │   └── respaldos.py
│   │
│   ├── adaptadores/              # I/O externo
│   │   ├── hardware/             # GPIO + monedero + máquinas
│   │   └── mercado_pago/         # cliente HTTP + Point + polling
│   │
│   ├── eventos/                  # bus pub/sub in-proc
│   │
│   └── ui/                       # NiceGUI (capa obediente)
│       ├── kiosko/               # página cliente + 5 pasos + wizard
│       ├── admin/                # login + dashboard + operativo + superadmin + cortes
│       └── compartido/           # estilos, auth, _componentes reutilizables
│
├── tools/                        # diagnóstico GPIO + referencia MP
├── media/                        # logos, imágenes, iconos SVG
├── data/                         # ecoluna_datos.db (gitignored)
├── tests/                        # pytest
├── .env / .env.example
├── requirements.txt
├── create_desktop_shortcut.sh
├── AGENTS.md                     # guía técnica detallada
└── README.md                     # este archivo
```

Las **reglas de imports** completas y el modelo de dominio están en `AGENTS.md`.

---

## Modelo de datos (resumen)

Tablas principales (todas en SQLite):

- `transacciones` — órdenes. Estados: `Pendiente-peso`, `Procesando-pago`, `Pendiente-pago`, `Pendiente`, `En-curso`, `Finalizado`, `Cancelado`.
- `servicios` — catálogo de servicios (data-driven, editable por el superadmin).
- `segmentaciones` — variantes dentro de un servicio (ej. "Lava + Seca + Dobla").
- `maquinas` — lavadoras y secadoras con su pin GPIO, modo (`pulso`/`sostenido`) y capacidad.
- `cortes_caja` + `cortes_movimientos` — apertura, cierre y arqueo por turno.
- `respaldos_catalogo` — snapshot JSON de los 3 catálogos para restaurar a un estado conocido.

---

## Roles y accesos

- **Cliente** — anónimo, solo consume el kiosko (`/`).
- **Operador** (Moi, Capi, David) — login en `/admin/login`. Ve y manipula órdenes.
- **Superadmin** (Moi, David) — además tiene acceso a `/admin/superadmin` y `/admin/cortes`.

---

## Próximos pasos (roadmap)

- [x] **Migración a Web:** extraer la lógica legacy y montar el servidor NiceGUI.
- [x] **Estrategia de pagos:** Monedas + Point + QR MP.
- [x] **Cortes de caja** con arqueo.
- [x] **Métricas** con Highcharts.
- [x] **Respaldo de fábrica** de los 3 catálogos.
- [ ] **Caja de dinero:** añadir pulso a través de un módulo relé para abrir el cajón al dar cambio.
- [ ] **Auditoría energética (PZEM-004T):** monitoreo de consumo en tiempo real.
- [ ] **Acceso remoto:** túnel (ej. Tailscale) para revisión de cortes a distancia.
- [ ] **Bypass con TOTP:** acoplar Google Authenticator al paso de autorización de servicios de cortesía.

---

## Soporte

Para detalles técnicos, decisiones de arquitectura y reglas de contribución, ver [`AGENTS.md`](./AGENTS.md).
