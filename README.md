# Kiosko de Lavandería EcoLuna 🌙🫧

Este proyecto es una interfaz gráfica moderna (GUI) desarrollada para la administración de pagos y servicios de la Lavandería EcoLuna. Está diseñada específicamente para ejecutarse en una Raspberry Pi con pantalla táctil de 7 pulgadas (resolución 800x480), controlando el flujo mediante optoacopladores.

Actualmente soporta integración con **monederos/tragamonedas** físicos para pagos en efectivo mediante el mapeo de señales, y deja preparada la arquitectura para integrar APIs de pagos electrónicos en un futuro.

---

## 📸 Características Principales

* **Interfaz Moderna (Dark/Light Mode):** Construida con `customtkinter` para una estética pulida y botones grandes ideales para pantallas táctiles.
* **Flujo de Asistente (Wizard):** Motor de navegación de pasos ("State Manager") completamente dinámico:
  1. Selección de Servicio (Lavado, Secado, Ambos).
  2. Confirmación y Total a Pagar.
  3. Ingreso de Efectivo (Simulado con eventos de teclado para el tragamonedas).
  4. Pantalla de Inicio de Máquina y fin de sesión.
* **Manejo de Estado Centralizado:** Guarda dinámicamente lo ingresado por un cliente y se "formatea" limpiamente usando `reset_session()` para el próximo usuario.
* **Registro de Ventas en Tiempo Real:** Base de datos `SQLite3` integrada (`ecoluna_datos.db`) para llevar un registro automático de las transacciones (servicio, monto pagado, cambio y fecha).

---

## 🛠️ Requisitos del Sistema

- **Hardware:** Computadora estándar o Raspberry Pi (idealmente con pantalla táctil).
- **Software:** Python 3.9 o superior.

### Dependencias

El proyecto utiliza las siguientes bibliotecas de Python:

```bash
pip install customtkinter
pip install Pillow
```

*Nota: `sqlite3` viene integrado por defecto en las librerías estándar de Python.*

---

## 🚀 Instalación y Ejecución

1. Clona el repositorio en tu máquina o Raspberry Pi:
   ```bash
   git clone <tu-url-del-repositorio>
   cd lavanderia/kiosko_pago
   ```
2. Instala las dependencias necesarias:
   ```bash
   pip install -r requirements.txt
   ```
3. Ejecuta la aplicación principal:
   ```bash
   python3 GUI.py
   ```

*(Nota para producción: En `GUI.py`, línea ~301, puedes descomentar `self.attributes('-fullscreen', True)` para bloquear la pantalla en modo Kiosko en tu Raspberry).*

---

## 🗄️ Estructura de la Base de Datos

La aplicación crea automáticamente el archivo `ecoluna_datos.db` en la primera ejecución. Cada vez que una persona completa un pago, se guarda un registro en la tabla `transacciones` con la siguiente estructura:

* `id_transaccion`: ID único.
* `fecha_hora`: Fecha y hora exactas de la venta.
* `tipo_servicio`: "Lavar", "Secar", "Lavar y secar".
* `monto_pagado`: Costo total cobrado.
* `dinero_ingresado`: Dinero depositado en la máquina.
* `cambio_devuelto`: Dinero sobrante.
* `id_equipo`: Identificador de la máquina (ej. "N/A" por ahora).
* `duracion_estimada_min`: Tiempo aproximado asignado.

---

## ⌨️ Uso del Teclado / Tragamonedas

La pantalla 3 (Pago) está esperando el "pulso" digital del tragamonedas que se mapea a teclas del sistema.
Para probarlo en tu computadora:
- En la pantalla de pago, presiona los números `1`, `2` o `5` en tu teclado; verás cómo el contador de dinero depositado sube automáticamente hasta cubrir el total.
- Si ingresas dinero de más o cancelas la operación, el kiosko te enviará un aviso para proteger tu saldo.

---

## 📝 Próximos Pasos (Roadmap)
- [] Integración con los pines GPIO de Raspberry Pi (salidas optoacopladas).
- [] Lector de código QR para pagos electrónicos.
- [] Opción de Selección de Máquina / Torreta específica.