# Kiosko de Lavandería EcoLuna 🌙🫧

Este proyecto es el sistema central de administración, cobro y control de hardware para la Lavandería EcoLuna. Ha evolucionado de una interfaz local a una **Arquitectura Web (Headless)**, diseñada para separar el flujo de cobro del cliente y el panel de control del administrador, operando desde una Raspberry Pi.

El sistema controla directamente el hardware de la lavandería (lavadoras LG Inverter, cajón de dinero) mediante circuitos aislados con optoacopladores y relés, garantizando seguridad industrial.

---

## 📸 Características Principales

* **Arquitectura Web-Based:** Construida con [FastAPI / NiceGUI] para permitir múltiples pantallas simultáneas a través de la red local.
* **Sistema de Cola Asíncrono (Cuello de botella eliminado):** * La **Pantalla Cliente (Touch)** procesa el cobro y se libera inmediatamente para el siguiente usuario.
  * La **Pantalla Admin (Mostrador)** recibe las órdenes pendientes, permitiendo al operador pesar la ropa, asignar la máquina y disparar el inicio del ciclo de forma segura.
* **Control de Hardware Aislado:** Mapeo de señales para lectura de monederos mecánicos y disparo de pulsos de inicio en máquinas industriales de 24V.
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

- [ ] **Migración a Web:** Extraer la lógica de `customtkinter` y montar el servidor backend/frontend.
- [ ] **Integración de Caja de Dinero:** Añadir pulso a través de un módulo relé para abrir el cajón (solenoide 18V) al dar cambio.
- [ ] **Auditoría Energética (PZEM-004T):** Implementar monitoreo de consumo eléctrico en tiempo real para evitar que clientes (o personal) seleccionen ciclos de secado en lavadoras asignadas solo para lavado.
- [ ] **Acceso Remoto:** Configuración de túnel (ej. Tailscale) para revisión de cortes de caja a distancia.