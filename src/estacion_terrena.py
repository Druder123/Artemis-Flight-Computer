import tkinter as tk
from tkinter import ttk, messagebox
import threading
import serial
import serial.tools.list_ports
import csv
from datetime import datetime
import queue

class EstacionTerrenaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ESTACIÓN TERRENA v1.0")
        self.root.geometry("1280x800")
        self.root.configure(bg="#07111a") 

        # Protocolo para cierre seguro de hilos y puerto serial
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Cola segura entre el hilo serial y la GUI
        self.data_queue = queue.Queue()

        # Estilos ttk
        self.style = ttk.Style()
        self.style.theme_use('default')
        self.style.configure('.', background='#07111a', foreground='#a5f3fc')
        self.style.configure('TCombobox', 
                             fieldbackground='#0f202e', 
                             background='#0a1924', 
                             foreground='#a5f3fc', 
                             darkcolor='#0891b2', 
                             lightcolor='#0891b2',
                             bordercolor='#0891b2')

        # Control Serial y Archivos
        self.serial_port = None
        self.running = False
        self.rx_thread = None
        self.csv_writer = None
        self.csv_file = None
        
        # Estado de la Misión
        self.estado_actual_mision = "ESPERA"
        self.max_altura = 0.0
        self.start_time = None
        self.last_alt = 0.0
        self.last_time = None
        
        # Telemetría
        self.telemetry_data = {
            "Presion": tk.StringVar(value="1013.2 hPa"),
            "Temperatura": tk.StringVar(value="22.4 °C"),
            "Humedad": tk.StringVar(value="45 %"),
            "Latitud": tk.StringVar(value="19.4326"),
            "Longitud": tk.StringVar(value="-99.1332"),
            "Altitud": tk.StringVar(value="0 m"),
            "AccX": tk.StringVar(value="0.00 g"),
            "AccY": tk.StringVar(value="0.00 g"),
            "AccZ": tk.StringVar(value="1.00 g"),
            "Velocidad": tk.StringVar(value="0.0 m/s"),
            "VelVertical": tk.StringVar(value="0.0 m/s"),
            "RPM": tk.StringVar(value="0 RPM"),
            "Apogeo": tk.StringVar(value="0.0 m")
        }
        
        self.mission_time_var = tk.StringVar(value="T+ 00:00:00")
        self.history_altitude = []
        self.history_accel = []

        self.create_widgets()
        self.update_mission_time()
        self.process_queue()

    def create_widgets(self):
        # 1. HEADER
        header_frame = tk.Frame(self.root, bg="#07111a", height=60)
        header_frame.pack(fill=tk.X, padx=20, pady=10)
        header_frame.pack_propagate(False)

        title_lbl = tk.Label(header_frame, text="🚀 ESTACIÓN TERRENA  v1.0", 
                             font=("Arial", 16, "bold"), fg="#38bdf8", bg="#07111a")
        title_lbl.pack(side=tk.LEFT)

        info_frame = tk.Frame(header_frame, bg="#07111a")
        info_frame.pack(side=tk.RIGHT)

        tk.Label(info_frame, text="Misión:", font=("Arial", 10), fg="#64748b", bg="#07111a").grid(row=0, column=0, padx=5)
        
        self.mission_combo = ttk.Combobox(info_frame, values=["PRUEBA-SIM", "VUELO-CDR"], width=12, font=("Arial", 10, "bold"))
        self.mission_combo.grid(row=0, column=1, padx=5)
        self.mission_combo.current(0)

        tk.Label(info_frame, text="Tiempo de misión:", font=("Arial", 10), fg="#64748b", bg="#07111a").grid(row=0, column=2, padx=15)
        
        timer_lbl = tk.Label(info_frame, textvariable=self.mission_time_var, 
                             font=("Consolas", 12, "bold"), fg="#38bdf8", bg="#0d1e2d", 
                             padx=10, pady=3, bd=1, relief="solid")
        timer_lbl.grid(row=0, column=3, padx=5)

        sep = tk.Frame(self.root, bg="#0891b2", height=2)
        sep.pack(fill=tk.X, padx=20, pady=(0, 10))

        # 2. CONTENEDOR PRINCIPAL
        main_grid = tk.Frame(self.root, bg="#07111a")
        main_grid.pack(fill=tk.BOTH, expand=True, padx=15)
        
        main_grid.columnconfigure((0, 1, 2, 3), weight=1)
        main_grid.rowconfigure(0, weight=3)
        main_grid.rowconfigure(1, weight=2)

        self.create_etapa_mision(main_grid, row=0, col=0)
        self.create_comunicaciones(main_grid, row=0, col=1)
        self.create_telemetria(main_grid, row=0, col=2)
        self.create_graficas(main_grid, row=0, col=3)
        self.create_alertas(main_grid, row=1, col=0, colspan=2)
        self.create_comandos(main_grid, row=1, col=2, colspan=2)

    def create_etapa_mision(self, parent, row, col):
        frame = self.create_neon_panel(parent, "🚀 ETAPA DE MISIÓN", row, col)
        
        self.estados_mision = ["ESPERA", "ASCENSO", "DESACOPLE", "DESCENSO", "ATERRIZAJE"]
        self.estado_labels = {}
        
        for estado in self.estados_mision:
            sub_frame = tk.Frame(frame, bg="#0d1e2d")
            sub_frame.pack(fill=tk.X, padx=15, pady=4)
            
            indicator = tk.Label(sub_frame, text="○", font=("Arial", 12, "bold"), fg="#64748b", bg="#0d1e2d")
            indicator.pack(side=tk.LEFT, padx=5)
            
            lbl = tk.Label(sub_frame, text=f"  {estado}  ", font=("Arial", 10), fg="#94a3b8", bg="#0d1e2d", padx=5, pady=2)
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.estado_labels[estado] = (lbl, indicator)

        info_box = tk.Frame(frame, bg="#0a1924", bd=1, relief="solid")
        info_box.pack(fill=tk.BOTH, expand=True, padx=15, pady=(10, 5))
        
        tk.Label(info_box, text="Criterios de Transición:", font=("Arial", 8, "bold"), fg="#0891b2", bg="#0a1924").pack(anchor="w", padx=8, pady=2)
        tk.Label(info_box, text="• Altura > 8m -> Ascenso\n• Caída de Presión -> Desacople\n• RPM > 100 -> Descenso\n• Altura < 4m -> Aterrizaje", font=("Arial", 8), fg="#94a3b8", bg="#0a1924", justify=tk.LEFT).pack(anchor="w", padx=15)

    def create_comunicaciones(self, parent, row, col):
        frame = self.create_neon_panel(parent, "📡 COMUNICACIONES", row, col)
        
        top_conn = tk.Frame(frame, bg="#0d1e2d")
        top_conn.pack(fill=tk.X, padx=10, pady=5)

        self.btn_conectar = tk.Button(top_conn, text="CONECTAR", bg="#0a1924", fg="#38bdf8", 
                                      activebackground="#0891b2", activeforeground="white",
                                      font=("Arial", 9, "bold"), bd=1, relief="solid", 
                                      command=self.toggle_connection, width=12, height=1)
        self.btn_conectar.pack(side=tk.LEFT, padx=5)

        self.status_conn_lbl = tk.Label(top_conn, text="DESCONECTADO", font=("Arial", 8, "bold"), fg="#f43f5e", bg="#0d1e2d")
        self.status_conn_lbl.pack(side=tk.RIGHT, padx=5)

        port_sel_frame = tk.Frame(frame, bg="#0d1e2d")
        port_sel_frame.pack(fill=tk.X, padx=10, pady=2)
        tk.Label(port_sel_frame, text="COM:", font=("Arial", 8), fg="#94a3b8", bg="#0d1e2d").pack(side=tk.LEFT, padx=5)
        
        self.port_combobox = ttk.Combobox(port_sel_frame, values=self.get_serial_ports(), width=8, font=("Arial", 8))
        self.port_combobox.pack(side=tk.LEFT, padx=2)
        if self.port_combobox.cget("values"):
            self.port_combobox.current(0)

        self.baud_combobox = ttk.Combobox(port_sel_frame, values=["9600", "57600", "115200"], width=8, font=("Arial", 8))
        self.baud_combobox.pack(side=tk.LEFT, padx=5)
        self.baud_combobox.current(2)

        chk_frame = tk.Frame(frame, bg="#0d1e2d")
        chk_frame.pack(fill=tk.X, padx=15, pady=5)
        tk.Label(chk_frame, text="Radio Check:   ✓ Link OK", font=("Arial", 9), fg="#a5f3fc", bg="#0d1e2d").pack(anchor="w")
        
        sig_frame = tk.Frame(frame, bg="#0d1e2d")
        sig_frame.pack(fill=tk.X, padx=15, pady=2)
        tk.Label(sig_frame, text="Señal de Enlace: ", font=("Arial", 9), fg="#94a3b8", bg="#0d1e2d").pack(side=tk.LEFT)
        self.signal_lbl = tk.Label(sig_frame, text="📶 Excelente", font=("Arial", 9, "bold"), fg="#10b981", bg="#0d1e2d")
        self.signal_lbl.pack(side=tk.LEFT, padx=5)

        tk.Label(frame, text="Consola Serial:", font=("Arial", 8, "bold"), fg="#0891b2", bg="#0d1e2d").pack(anchor="w", padx=15, pady=(5, 0))
        self.txt_console = tk.Text(frame, height=5, bg="#0a1924", fg="#38bdf8", font=("Consolas", 8), 
                                   insertbackground="white", bd=1, relief="solid")
        self.txt_console.pack(fill=tk.BOTH, expand=True, padx=15, pady=(2, 8))

    def create_telemetria(self, parent, row, col):
        frame = self.create_neon_panel(parent, "📊 TELEMETRÍA", row, col)
        
        tel_grid = tk.Frame(frame, bg="#0d1e2d")
        tel_grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        tel_grid.columnconfigure((0, 1, 2, 3), weight=1)

        variables = [
            ("Presión:", "Presion", 0, 0),
            ("Temperatura:", "Temperatura", 1, 0),
            ("Humedad:", "Humedad", 2, 0),
            ("Acel. X:", "AccX", 3, 0),
            ("Acel. Y:", "AccY", 4, 0),
            ("Acel. Z:", "AccZ", 5, 0),
            ("Latitud:", "Latitud", 0, 2),
            ("Longitud:", "Longitud", 1, 2),
            ("Altitud:", "Altitud", 2, 2),
            ("Velocidad:", "Velocidad", 3, 2),
            ("Vel. Vert:", "VelVertical", 4, 2),
            ("Apogeo:", "Apogeo", 5, 2),
        ]

        for label_text, var_name, r, c in variables:
            lbl = tk.Label(tel_grid, text=label_text, font=("Arial", 8), fg="#94a3b8", bg="#0d1e2d", anchor="w")
            lbl.grid(row=r, column=c, sticky="w", padx=2, pady=3)
            
            val_lbl = tk.Label(tel_grid, textvariable=self.telemetry_data[var_name], 
                               font=("Consolas", 9, "bold"), fg="#ffffff", bg="#0a1924", 
                               bd=1, relief="solid", width=11, height=1, anchor="center")
            val_lbl.grid(row=r, column=c+1, sticky="e", padx=2, pady=3)

        self.last_update_lbl = tk.Label(frame, text="Última actualización: --:--:--", font=("Arial", 7), fg="#64748b", bg="#0d1e2d")
        self.last_update_lbl.pack(side=tk.BOTTOM, pady=5)

    def create_graficas(self, parent, row, col):
        frame = self.create_neon_panel(parent, "📈 GRÁFICAS", row, col)
        
        tk.Label(frame, text="Altura vs Tiempo", font=("Arial", 8, "bold"), fg="#a5f3fc", bg="#0d1e2d").pack(anchor="w", padx=10, pady=(2, 0))
        self.canvas_alt = tk.Canvas(frame, height=90, bg="#0a1924", highlightthickness=1, highlightbackground="#0891b2")
        self.canvas_alt.pack(fill=tk.X, padx=10, pady=2)
        
        tk.Label(frame, text="Aceleración Z vs Tiempo", font=("Arial", 8, "bold"), fg="#a5f3fc", bg="#0d1e2d").pack(anchor="w", padx=10, pady=(4, 0))
        self.canvas_acc = tk.Canvas(frame, height=90, bg="#0a1924", highlightthickness=1, highlightbackground="#0891b2")
        self.canvas_acc.pack(fill=tk.X, padx=10, pady=2)

        self.draw_grid_background(self.canvas_alt, "Altura (m)", 120)
        self.draw_grid_background(self.canvas_acc, "Acel. Z (g)", 4.0)

    def draw_grid_background(self, canvas, label_y, max_val):
        canvas.delete("all")
        for x in range(30, 260, 40):
            canvas.create_line(x, 10, x, 75, fill="#132b3d", dash=(2, 2))
        for y in range(15, 80, 20):
            canvas.create_line(30, y, 250, y, fill="#132b3d", dash=(2, 2))
        
        val_top = f"{max_val:.0f}" if max_val >= 10 else f"{max_val:.1f}"
        val_mid = f"{max_val/2:.0f}" if max_val >= 10 else f"{max_val/2:.1f}"
        
        canvas.create_text(25, 10, text=val_top, fill="#64748b", font=("Arial", 7), anchor="e")
        canvas.create_text(25, 45, text=val_mid, fill="#64748b", font=("Arial", 7), anchor="e")
        canvas.create_text(25, 75, text="0", fill="#64748b", font=("Arial", 7), anchor="e")
        
        canvas.create_text(240, 83, text="Tiempo", fill="#64748b", font=("Arial", 7), anchor="e")
        canvas.create_text(32, 8, text=label_y, fill="#a5f3fc", font=("Arial", 7), anchor="w")

    def create_alertas(self, parent, row, col, colspan):
        frame = self.create_neon_panel(parent, "🔔 ALERTAS Y ESTADO DEL SISTEMA", row, col, columnspan=colspan)
        
        table_header = tk.Frame(frame, bg="#0a1924")
        table_header.pack(fill=tk.X, padx=15, pady=(5, 0))
        
        tk.Label(table_header, text="Hora", font=("Arial", 8, "bold"), fg="#64748b", bg="#0a1924", width=10, anchor="w").pack(side=tk.LEFT)
        tk.Label(table_header, text="Nivel", font=("Arial", 8, "bold"), fg="#64748b", bg="#0a1924", width=15, anchor="w").pack(side=tk.LEFT)
        tk.Label(table_header, text="Mensaje", font=("Arial", 8, "bold"), fg="#64748b", bg="#0a1924", anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.alerts_container = tk.Frame(frame, bg="#0d1e2d")
        self.alerts_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        self.add_alert_row("Sistema", "INFO", "Estación Terrena en espera de conexión...", "#38bdf8")

        footer_state = tk.Frame(frame, bg="#0d1e2d")
        footer_state.pack(fill=tk.X, padx=15, pady=(0, 8))
        tk.Label(footer_state, text="Estado general:", font=("Arial", 9), fg="#94a3b8", bg="#0d1e2d").pack(side=tk.LEFT)
        
        self.state_badge = tk.Label(footer_state, text="ESPERANDO CONEXIÓN", font=("Arial", 9, "bold"), fg="#38bdf8", bg="#0f2b3c", 
                                   padx=15, pady=2, bd=1, relief="solid")
        self.state_badge.pack(side=tk.LEFT, padx=10)

    def add_alert_row(self, hora, nivel, mensaje, color):
        children = self.alerts_container.winfo_children()
        if len(children) >= 4:
            children[0].destroy()

        lbl_bg = "#2d2218" if ("ADVERTENCIA" in nivel or "CRÍTICO" in nivel) else "#0d1e2d"
        row = tk.Frame(self.alerts_container, bg=lbl_bg)
        row.pack(fill=tk.X, pady=1)

        tk.Label(row, text=hora, font=("Consolas", 8), fg="#94a3b8", bg=lbl_bg, width=10, anchor="w").pack(side=tk.LEFT)
        tk.Label(row, text=nivel, font=("Arial", 8, "bold"), fg=color, bg=lbl_bg, width=15, anchor="w").pack(side=tk.LEFT)
        tk.Label(row, text=mensaje, font=("Arial", 8), fg="#ffffff", bg=lbl_bg, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

    def create_comandos(self, parent, row, col, colspan):
        frame = self.create_neon_panel(parent, "⌨ COMANDOS Y CONTROL", row, col, columnspan=colspan)
        
        btn_grid = tk.Frame(frame, bg="#0d1e2d")
        btn_grid.pack(fill=tk.X, padx=15, pady=10)
        btn_grid.columnconfigure((0, 1), weight=1)

        btn_iniciar = tk.Button(btn_grid, text="INICIAR ADQUISICIÓN", bg="#0f2434", fg="#38bdf8", 
                                font=("Arial", 9, "bold"), bd=1, relief="solid", pady=4, command=self.toggle_connection)
        btn_iniciar.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        btn_detener = tk.Button(btn_grid, text="DETENER ADQUISICIÓN", bg="#0f2434", fg="#f43f5e", 
                                font=("Arial", 9, "bold"), bd=1, relief="solid", pady=4, command=self.stop_connection)
        btn_detener.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        btn_guardar = tk.Button(btn_grid, text="GUARDAR DATOS (CSV)", bg="#0f2434", fg="#a5f3fc", 
                                font=("Arial", 9, "bold"), bd=1, relief="solid", pady=4, command=self.save_data_manual)
        btn_guardar.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        btn_limpiar = tk.Button(btn_grid, text="LIMPIAR CONSOLA", bg="#0f2434", fg="#a5f3fc", 
                                font=("Arial", 9, "bold"), bd=1, relief="solid", pady=4, command=lambda: self.txt_console.delete("1.0", tk.END))
        btn_limpiar.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        cmd_quick = tk.Frame(frame, bg="#0d1e2d")
        cmd_quick.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(cmd_quick, text="Acción:", font=("Arial", 8), fg="#94a3b8", bg="#0d1e2d").pack(side=tk.LEFT, padx=5)
        
        self.cmd_combo = ttk.Combobox(cmd_quick, values=["CMD,CALIBRATE", "CMD,FORCE_DEPLOY", "CMD,BUZZER_ON"], width=22)
        self.cmd_combo.pack(side=tk.LEFT, padx=5)
        self.cmd_combo.current(0)

        btn_enviar = tk.Button(cmd_quick, text="ENVIAR", bg="#0891b2", fg="white", font=("Arial", 8, "bold"), bd=0, padx=10, command=self.enviar_comando_rapido)
        btn_enviar.pack(side=tk.LEFT, padx=5)

        self.log_file_lbl = tk.Label(frame, text="Archivo de datos: NINGUNO", font=("Arial", 7), fg="#64748b", bg="#0d1e2d")
        self.log_file_lbl.pack(side=tk.BOTTOM, pady=5, anchor="w", padx=15)

    def create_neon_panel(self, parent, title, row, col, columnspan=1):
        outer = tk.Frame(parent, bg="#0891b2", bd=0)
        outer.grid(row=row, column=col, columnspan=columnspan, padx=8, pady=8, sticky="nsew")
        
        inner = tk.Frame(outer, bg="#0d1e2d")
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        header = tk.Frame(inner, bg="#0a1924")
        header.pack(fill=tk.X)
        
        lbl_title = tk.Label(header, text=title, font=("Arial", 9, "bold"), fg="#38bdf8", bg="#0a1924", pady=5)
        lbl_title.pack(anchor="w", padx=10)

        return inner

    def get_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def update_mission_time(self):
        if self.running and self.start_time:
            delta = datetime.now() - self.start_time
            seconds = int(delta.total_seconds())
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            self.mission_time_var.set(f"T+ {hours:02d}:{minutes:02d}:{secs:02d}")
        self.root.after(1000, self.update_mission_time)

    def toggle_connection(self):
        if not self.running:
            port = self.port_combobox.get()
            baud = self.baud_combobox.get()
            
            if not port:
                messagebox.showerror("Error", "Por favor selecciona un puerto COM válido.")
                return
            
            try:
                self.serial_port = serial.Serial(port, int(baud), timeout=1)
                self.running = True
                self.start_time = datetime.now()
                self.last_time = datetime.now()
                self.btn_conectar.config(text="DESCONECTAR", bg="#ef4444", fg="white")
                self.status_conn_lbl.config(text="CONECTADO", fg="#10b981")
                self.state_badge.config(text="ADQUISICIÓN ACTIVA", fg="#10b981")
                
                filename = f"Vuelo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                self.log_file_lbl.config(text=f"Archivo de datos: {filename}")
                self.csv_file = open(filename, mode='w', newline='')
                self.csv_writer = csv.writer(self.csv_file)
                self.csv_writer.writerow(["Timestamp", "Presion", "Temp", "Hum", "Latitud", "Longitud", "AccX", "AccY", "AccZ", "RPM", "Altura"])
                
                while not self.data_queue.empty():
                    try:
                        self.data_queue.get_nowait()
                    except queue.Empty:
                        break
                
                self.rx_thread = threading.Thread(target=self.receive_data, daemon=True)
                self.rx_thread.start()
                
                self.log_to_console(f"Enlace establecido con {port}.\n")
                self.add_alert_row(datetime.now().strftime("%H:%M:%S"), "CONEXIÓN", f"Puerto {port} abierto.", "#10b981")
            except Exception as e:
                messagebox.showerror("Error de Conexión", f"No se pudo abrir el puerto: {e}")
        else:
            self.stop_connection()

    def stop_connection(self):
        if self.running:
            self.running = False
            self.btn_conectar.config(text="CONECTAR", bg="#0a1924", fg="#38bdf8")
            self.status_conn_lbl.config(text="DESCONECTADO", fg="#f43f5e")
            self.state_badge.config(text="CONEXIÓN FINALIZADA", fg="#f43f5e")
            
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.close()
                except Exception:
                    pass
            if self.csv_file:
                try:
                    self.csv_file.close()
                except Exception:
                    pass
            
            self.log_to_console("Adquisición detenida por el usuario.\n")
            self.add_alert_row(datetime.now().strftime("%H:%M:%S"), "SISTEMA", "Lectura serial finalizada.", "#f43f5e")

    def save_data_manual(self):
        if self.csv_file:
            self.csv_file.flush()
            messagebox.showinfo("Guardado", "¡Datos en archivo CSV actualizados correctamente!")
        else:
            messagebox.showwarning("Advertencia", "No hay transmisión activa para guardar.")

    def enviar_comando_rapido(self):
        cmd = self.cmd_combo.get()
        self.log_to_console(f"[CMD] -> {cmd}\n")
        self.add_alert_row(datetime.now().strftime("%H:%M:%S"), "COMANDO", f"Enviado: {cmd}", "#a855f7")
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(f"{cmd}\n".encode())
            except Exception as e:
                self.log_to_console(f"Error TX: {e}\n")

    def log_to_console(self, text):
        self.txt_console.insert(tk.END, text)
        self.txt_console.see(tk.END)

    def calculate_altitude(self, pressure_hpa):
        try:
            p0 = 1013.25
            altitude = 44330.0 * (1.0 - (pressure_hpa / p0) ** 0.1903)
            return max(0.0, altitude)
        except Exception:
            return 0.0

    def receive_data(self):
        while self.running:
            try:
                if self.serial_port and self.serial_port.is_open and self.serial_port.in_waiting > 0:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        self.data_queue.put((timestamp, line))
            except Exception as e:
                self.data_queue.put(("ERROR", str(e)))
                break
            
            threading.Event().wait(0.01)

    def process_queue(self):
        while not self.data_queue.empty():
            try:
                timestamp, line = self.data_queue.get_nowait()
                
                if timestamp == "ERROR":
                    self.log_to_console(f"Error de lectura serial: {line}\n")
                    self.stop_connection()
                    messagebox.showerror("Error de Puerto", "Se perdió la comunicación con el dispositivo Serial.")
                    break
                
                self.log_to_console(f"[{timestamp}] -> {line}\n")
                
                parts = line.split(',')
                # CORRECCIÓN: Validar los 10 campos requeridos del CSV
                if len(parts) >= 10:
                    try:
                        presion = float(parts[0])
                        temp = float(parts[1])
                        hum = float(parts[2])
                        lat = float(parts[3])
                        lon = float(parts[4])
                        accx = float(parts[5])
                        accy = float(parts[6])
                        accz = float(parts[7])
                        rpm = int(float(parts[8]))
                        altura_actual = float(parts[9])  # CORRECCIÓN: Lectura directa de la altitud precalibrada
                    except ValueError:
                        self.log_to_console("⚠️ Trama corrupta o incompleta omitida.\n")
                        continue
                    
                    # Cálculo dinámico de velocidad vertical (m/s)
                    now = datetime.now()
                    if self.last_time is not None:
                        dt = (now - self.last_time).total_seconds()
                        if dt > 0:
                            v_vertical = (altura_actual - self.last_alt) / dt
                            self.telemetry_data["VelVertical"].set(f"{v_vertical:.1f} m/s")
                    self.last_alt = altura_actual
                    self.last_time = now

                    # Actualizar UI
                    self.telemetry_data["Presion"].set(f"{presion:.1f} hPa")
                    self.telemetry_data["Temperatura"].set(f"{temp:.1f} °C")
                    self.telemetry_data["Humedad"].set(f"{hum:.0f} %")
                    self.telemetry_data["Latitud"].set(f"{lat:.4f}")
                    self.telemetry_data["Longitud"].set(f"{lon:.4f}")
                    self.telemetry_data["Altitud"].set(f"{altura_actual:.1f} m")
                    self.telemetry_data["AccX"].set(f"{accx:.2f} g")
                    self.telemetry_data["AccY"].set(f"{accy:.2f} g")
                    self.telemetry_data["AccZ"].set(f"{accz:.2f} g")
                    self.telemetry_data["RPM"].set(f"{rpm} RPM")
                    
                    if altura_actual > self.max_altura:
                        self.max_altura = altura_actual
                        self.telemetry_data["Apogeo"].set(f"{self.max_altura:.1f} m")

                    self.last_update_lbl.config(text=f"Última actualización: {timestamp}")

                    self.evaluar_etapa_mision(altura_actual, accz, rpm)
                    self.update_plots(altura_actual, accz)

                    if self.csv_writer and self.csv_file:
                        self.csv_writer.writerow([
                            timestamp, presion, temp, hum, lat, lon, 
                            accx, accy, accz, rpm, round(altura_actual, 2)
                        ])
                        
            except queue.Empty:
                break
            except Exception as ex:
                self.log_to_console(f"Excepción al procesar: {ex}\n")
        
        self.root.after(50, self.process_queue)

    def evaluar_etapa_mision(self, altura, accz, rpm):
        estado_anterior = self.estado_actual_mision

        if self.estado_actual_mision == "ESPERA":
            if altura > 8.0:
                self.estado_actual_mision = "ASCENSO"

        elif self.estado_actual_mision == "ASCENSO":
            if self.max_altura > 30.0 and altura < (self.max_altura - 2.5):
                self.estado_actual_mision = "DESACOPLE"

        elif self.estado_actual_mision == "DESACOPLE":
            if rpm > 100 or altura < (self.max_altura * 0.7):
                self.estado_actual_mision = "DESCENSO"

        elif self.estado_actual_mision == "DESCENSO":
            if altura < 4.0:
                self.estado_actual_mision = "ATERRIZAJE"

        elif self.estado_actual_mision == "ATERRIZAJE":
            if altura < 1.0 and self.max_altura > 50.0:
                self.max_altura = 0.0
                self.estado_actual_mision = "ESPERA"

        if self.estado_actual_mision != estado_anterior:
            hora_log = datetime.now().strftime("%H:%M:%S")
            self.add_alert_row(
                hora_log, 
                "✓ FASE", 
                f"Transición a etapa: {self.estado_actual_mision}", 
                "#22d3ee"
            )

        for estado, (lbl, ind) in self.estado_labels.items():
            if estado == self.estado_actual_mision:
                lbl.config(bg="#0ea5e9", fg="#ffffff", font=("Arial", 10, "bold"))
                ind.config(text="✓", fg="#22d3ee")
            else:
                lbl.config(bg="#0d1e2d", fg="#94a3b8", font=("Arial", 10, "normal"))
                ind.config(text="○", fg="#64748b")

    def update_plots(self, alt, accz):
        self.history_altitude.append(alt)
        self.history_accel.append(accz)
        
        if len(self.history_altitude) > 40:
            self.history_altitude.pop(0)
        if len(self.history_accel) > 40:
            self.history_accel.pop(0)

        # Escala dinámica de Altura
        max_alt_scale = max(120.0, max(self.history_altitude, default=120.0))
        self.draw_grid_background(self.canvas_alt, "Altura (m)", max_alt_scale)
        if len(self.history_altitude) > 1:
            points_alt = []
            for idx, val in enumerate(self.history_altitude):
                x = 30 + (idx * 5.5)
                y = 75 - ((val / max_alt_scale) * 60)
                y = max(15, min(75, y))
                points_alt.append((x, y))
            self.canvas_alt.create_line(points_alt, fill="#22d3ee", width=2)

        # Escala dinámica de Aceleración
        max_acc_scale = max(4.0, max(self.history_accel, default=4.0))
        self.draw_grid_background(self.canvas_acc, "Acel. Z (g)", max_acc_scale)
        if len(self.history_accel) > 1:
            points_acc = []
            for idx, val in enumerate(self.history_accel):
                x = 30 + (idx * 5.5)
                y = 75 - ((val / max_acc_scale) * 60)
                y = max(15, min(75, y))
                points_acc.append((x, y))
            self.canvas_acc.create_line(points_acc, fill="#38bdf8", width=2)

    def on_closing(self):
        self.stop_connection()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = EstacionTerrenaApp(root)
    root.mainloop()