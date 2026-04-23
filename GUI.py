from PIL.ImageOps import expand
import time
import customtkinter as ctk
from PIL import Image
import os
from tkinter import messagebox
import database

# --- Carga de medios ---
IMG_LOGO_PATH = os.path.join("media", "logo_slogan.png")

# --- Configuración visual ---
ctk.set_appearance_mode("System")  # Modos: "System", "Dark", "Light"
ctk.set_default_color_theme("green")  # Temas: "blue", "green", "dark-blue"

class SidebarFrame(ctk.CTkFrame):
    """Panel lateral para mostrar el progreso de los pasos."""
    def __init__(self, master, steps, **kwargs):
        super().__init__(master, **kwargs)
        self.steps = steps
        self.step_labels = {}

        # Configuración de Grid lateral
        self.grid_columnconfigure(0, weight=1)
        
        # Título del panel
        self.title_label = ctk.CTkLabel(self, text="Progreso", font=("Helvetica", 20, "bold"))
        self.title_label.grid(row=0, column=0, pady=(20, 50), padx=20, sticky="nsew")
        
        # Crear labels para cada paso
        for i, step in enumerate(self.steps):
            self.grid_rowconfigure(i+1, weight=1)

            lbl_frame = ctk.CTkFrame(self, fg_color="#C7C3C3", corner_radius=0)
            lbl_frame.grid(row=i+1, column=0, padx=5, sticky="nsew")
            lbl = ctk.CTkLabel(lbl_frame, text=step, font=("Helvetica", 16), wraplength=140)
            lbl.pack(expand=True)
            self.step_labels[step] = lbl
            
    def set_active_step(self, active_step):
        """Resalta el paso activo y opaca los demás."""
        for step, lbl in self.step_labels.items():
            if step == active_step:
                lbl.configure(font=("Helvetica", 16, "bold"), text_color="#1f6aa5") # Color azul de resalte
            else:
                lbl.configure(font=("Helvetica", 16), text_color="black")


class HeaderFrame(ctk.CTkFrame):
    """Encabezado superior con logo, título y reloj dinámico."""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        # Logo
        try:
            self.logo_image = ctk.CTkImage(Image.open(IMG_LOGO_PATH), size=(80, 90))
            self.logo_label = ctk.CTkLabel(self, image=self.logo_image, text="")
        except Exception:
            # Fallback en caso de no encontrar la imagen
            self.logo_label = ctk.CTkLabel(self, text="[LOGO]", font=("Helvetica", 20))
        self.logo_label.pack(side="left", padx=20, pady=10)
        
        # Título
        self.titulo_label = ctk.CTkLabel(self, text="Lavandería EcoLuna", font=("Helvetica", 30, "bold"))
        self.titulo_label.pack(side="left", padx=10)
        
        # Fecha y Hora
        self.date_time_label = ctk.CTkLabel(self, text="", font=("Helvetica", 16))
        self.date_time_label.pack(side="right", padx=20)
        
        # Iniciar reloj
        self.update_clock()
        
    def update_clock(self):
        """Actualiza la fecha y hora cada segundo."""
        current_time = time.strftime("%d/%m/%Y\n\n%H:%M:%S")
        self.date_time_label.configure(text=current_time)
        self.after(1000, self.update_clock)


# --- Frames de cada paso ---

class StepSelectService(ctk.CTkFrame):
    """Vista correspondiente al paso de Selección de Servicio."""
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        
        self.instructions_label = ctk.CTkLabel(self, text="Selecciona el servicio que deseas utilizar", font=("Helvetica", 24))
        self.instructions_label.pack(pady=(40, 20))

        service_options = {
            "Lavar": "$35",
            "Secar": "$45",
            "Lavar y secar": "$75"
        }

        self.service_buttons = []
        for service, price in service_options.items():
            btn = ctk.CTkButton(self, 
                                text=f"{service}\n{price}",
                                font=("Helvetica", 20), 
                                height=60,
                                width=250,
                                command=lambda s=service, p=price: self._on_service_selected(s, p))
            btn.pack(pady=15)
            self.service_buttons.append(btn)

    def _on_service_selected(self, service, price):
        print(f"Servicio seleccionado: {service} a {price}")
        # Guardamos en sesión
        self.app.session_data["servicio"] = service
        self.app.session_data["precio"] = price
        # Avanzamos al siguiente paso automáticamente
        self.app.next_step()

    def on_show(self):
        # Se llama cada vez que esta pantalla aparece.
        # Aquí no ocupamos hacer nada porque es la primera pantalla.
        pass


class StepConfirmService(ctk.CTkFrame):
    """Vista correspondiente al paso de Confirmación del Servicio."""
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        
        self.instructions_label = ctk.CTkLabel(self, text="Confirmación del Servicio", font=("Helvetica", 24))
        self.instructions_label.pack(pady=(40, 20))

        self.selected_service_lbl = ctk.CTkLabel(self, text="", font=("Helvetica", 20, "bold"))
        self.selected_service_lbl.pack(pady=(20, 10))
        
        self.price_lbl = ctk.CTkLabel(self, text="", font=("Helvetica", 20))
        self.price_lbl.pack(pady=(0, 40))

        # Contenedor para botones de navegación
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(side="bottom", pady=20, fill="x")
        
        self.btn_back = ctk.CTkButton(self.nav_frame, text="Atrás", font=("Helvetica", 18), width=120, fg_color="#F54927", hover_color="#9C2007", command=self.app.prev_step)
        self.btn_back.pack(side="left", padx=50)

        self.btn_next = ctk.CTkButton(self.nav_frame, text="Confirmar", font=("Helvetica", 18), width=120, command=self.app.next_step)
        self.btn_next.pack(side="right", padx=50)

    def on_show(self):
        # Leemos los datos centralizados de session_data
        servicio = self.app.session_data.get("servicio", "Ninguno")
        precio = self.app.session_data.get("precio", "$0")
        self.selected_service_lbl.configure(text=f"Servicio: {servicio}")
        self.price_lbl.configure(text=f"Total a pagar: {precio}")


class StepPago(ctk.CTkFrame):
    """Vista correspondiente al paso de Pago."""
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        
        self.instructions_label = ctk.CTkLabel(self, text="Realice su pago", font=("Helvetica", 24))
        self.instructions_label.pack(pady=(40, 20))

        self.status_lbl = ctk.CTkLabel(self, text="Esperando monedas/billetes...", font=("Helvetica", 16))
        self.status_lbl.pack(pady=(20, 18))

        self.counter = 0

        self.counter_lbl = ctk.CTkLabel(self, text=f"${self.counter}", font=("Helvetica", 24, "bold"))
        self.counter_lbl.pack(pady=(10, 5))

        # Inicializamos el label vacío, lo llenaremos en on_show
        self.total_lbl = ctk.CTkLabel(self, text="Total a pagar: ", font=("Helvetica", 16))
        self.total_lbl.pack(pady=(5, 0))

        # Contenedor para botones
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(side="bottom", pady=20, fill="x")
        
        self.btn_back = ctk.CTkButton(self.nav_frame, text="Cancelar y Regresar", font=("Helvetica", 18), fg_color="red", hover_color="darkred", width=200, command=self._confirm_back)
        self.btn_back.pack(side="left", padx=50)

        # Botón para simular pago exitoso
        self.btn_next = ctk.CTkButton(self.nav_frame, text="Pagar", font=("Helvetica", 18), state="disabled", width=200, command=self.app.next_step)
        self.btn_next.pack(side="right", padx=50)

    # Simulación de introducción de dinero
    def sync_counter(self, event):
        coins_list = [1, 2, 5, 10]
        try:
            if int(event.char) in coins_list:
                credit = int(event.char)
                self.counter += credit
                self.counter_lbl.configure(text=f"${self.counter}")
            
            # (Opcional) Guardar el dinero en la sesión general si lo necesitas
            self.app.session_data["dinero_ingresado"] = self.counter
        except ValueError:
            pass
        
        # Si el usuario introduce todo el dinero, activamos el botón de pagar
        if self.counter >= int(self.app.session_data.get("precio", "$0").strip("$")):
            self.btn_next.configure(state="normal")
        
        # Si el usuario introduce más dinero del necesario, notificamos con ventana emergente
        if self.counter > int(self.app.session_data.get("precio", "$0").strip("$")):
            messagebox.showinfo("Dinero ingresado", "Has ingresado más dinero del necesario. Por favor, presiona 'pagar' o cancela en tragamonedas para retirar el excedente y volver a intentar.")

    def _confirm_back(self):
        # Ventana emergente de advertencia nativa
        respuesta = messagebox.askyesno("Advertencia", "Si regresas podrías perder el dinero ingresado. ¿Estás seguro de regresar e intentar reclamar la devolución?")
        if respuesta:
            # Quitamos el evento del teclado antes de irnos para que no siga escuchando en otras pantallas
            self.app.unbind("<Key>")
            self.app.prev_step()

    def on_show(self):
        # 1. Actualizamos el precio basándonos en la selección actual
        precio = self.app.session_data.get("precio", "$0")
        self.total_lbl.configure(text=f"Total a pagar: {precio}")
        
        # 2. Reiniciamos el contador visual (útil si el usuario canceló y volvió a entrar)
        self.counter = 0
        self.counter_lbl.configure(text=f"${self.counter}")
        
        # 3. ¡LA CLAVE! Le decimos a la ventana principal (app) que escuche el teclado
        # y envíe los eventos a nuestra función sync_counter
        self.app.bind("<Key>", self.sync_counter)


class StepComienzaServicio(ctk.CTkFrame):
    """Vista correspondiente al paso final donde inicia la máquina."""
    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        
        self.instructions_label = ctk.CTkLabel(self, text="¡Pago Exitoso!", font=("Helvetica", 30, "bold"), text_color="#1f6aa5")
        self.instructions_label.pack(pady=(60, 20))

        self.status_lbl = ctk.CTkLabel(self, text="Tu servicio está listo para comenzar.\nPor favor, presiona inicio en la máquina.", font=("Helvetica", 20))
        self.status_lbl.pack(pady=(20, 60))

        # Contenedor para botones
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(side="bottom", pady=20, fill="x")
        
        # Botón para finalizar y reiniciar el kiosko para el siguiente cliente
        self.btn_finish = ctk.CTkButton(self.nav_frame, text="Finalizar y Salir", font=("Helvetica", 20, "bold"), height=60, width=250, command=self.app.reset_session)
        self.btn_finish.pack(pady=20)

    def on_show(self):
        # 1. Recuperamos datos
        servicio = self.app.session_data.get("servicio", "Desconocido")
        precio_str = self.app.session_data.get("precio", "$0")
        ingresado = self.app.session_data.get("dinero_ingresado", 0)
        
        # 2. Limpieza de datos (quitar el signo $ y convertir a número)
        try:
            precio = float(precio_str.replace('$', '').strip())
        except ValueError:
            precio = 0.0
            
        cambio = ingresado - precio
        
        # 3. Guardar en SQLite
        # Asumimos 45 min por defecto para este ejemplo
        database.registrar_venta(
            servicio=servicio, 
            monto=precio, 
            ingresado=ingresado, 
            cambio=cambio,
            equipo="N/A",
            duracion=45 
        )


class KioskoLavanderia(ctk.CTk):
    """Ventana principal de la aplicación."""
    def __init__(self):
        super().__init__()
        
        # --- Inicializar Base de Datos ---
        database.inicializar_bd()
        
        # --- Variables Centralizadas (State Manager) ---
        self.session_data = {
            "servicio": None,
            "precio": 0,
            "dinero_ingresado": 0
        }
        self.current_step_index = 0
        
        # Configuración de ventana
        self.title("Lavandería EcoLuna")
        self.geometry("800x480")
        # self.attributes('-fullscreen', True)
        
        # Lista de pasos
        self.steps_list = [
            "1. Selección de Servicio",
            "2. Confirmación del Servicio",
            "3. Pago",
            "4. Comienza Servicio"
        ]

        # Configuración del Grid Principal
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        
        # --- 1. Panel Lateral ---
        self.sidebar = SidebarFrame(self, steps=self.steps_list, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # --- 2. Área Principal ---
        self.main_content = ctk.CTkFrame(self, fg_color="transparent")
        self.main_content.grid(row=0, column=1, sticky="nsew")
        self.main_content.grid_rowconfigure(1, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)
        
        # 2.1 Encabezado
        self.header = HeaderFrame(self.main_content, corner_radius=0)
        self.header.grid(row=0, column=0, sticky="ew")
        
        # 2.2 Contenedor de servicios
        self.services_container = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.services_container.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self.services_container.grid_rowconfigure(0, weight=1)
        self.services_container.grid_columnconfigure(0, weight=1)
        
        # Vistas
        self.frames = {}
        self._init_frames()
        
        # Iniciar Wizard
        self.show_step_index(0)

    def _init_frames(self):
        """Inicializa todas las vistas y las almacena."""
        # Se pasa `app=self` a cada vista para que tengan acceso al state manager y navegación
        self.frames[0] = StepSelectService(self.services_container, app=self)
        self.frames[1] = StepConfirmService(self.services_container, app=self)
        self.frames[2] = StepPago(self.services_container, app=self)
        self.frames[3] = StepComienzaServicio(self.services_container, app=self)
        
        for frame in self.frames.values():
            frame.grid(row=0, column=0, sticky="nsew")
            
    def next_step(self):
        """Avanza al siguiente paso de manera lineal."""
        if self.current_step_index < len(self.steps_list) - 1:
            self.show_step_index(self.current_step_index + 1)
            
    def prev_step(self):
        """Regresa al paso anterior de manera lineal."""
        if self.current_step_index > 0:
            self.show_step_index(self.current_step_index - 1)
            
    def reset_session(self):
        """Limpia los datos y regresa al inicio."""
        self.session_data = {
            "servicio": None,
            "precio": 0,
            "dinero_ingresado": 0
        }
        self.show_step_index(0)

    def show_step_index(self, index):
        """Alterna la vista según el índice y actualiza el panel."""
        self.current_step_index = index
        step_name = self.steps_list[index]
        
        if index in self.frames:
            frame = self.frames[index]
            
            # Ejecutar lógica de inicio de la vista si existe
            if hasattr(frame, 'on_show'):
                frame.on_show()
                
            frame.tkraise()
            self.sidebar.set_active_step(step_name)
        else:
            print(f"Aviso: El paso '{step_name}' aún no tiene una vista implementada.")
            self.sidebar.set_active_step(step_name)

if __name__ == "__main__":
    app = KioskoLavanderia()
    app.mainloop()
