import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
from pathlib import Path

# ================================================================
# CAPA DE ACCESO A DATOS (BACKEND)
# ================================================================

def conectar_bd():
    """Establece conexión con la base de datos Salud.db"""
    ruta_bd = Path(__file__).resolve().parent / 'DB' / 'Salud.db'
    return sqlite3.connect(ruta_bd)


# -------------------- PACIENTES (CRUD COMPLETO) --------------------
def registrar_paciente(datos):
    """
    HU-01: Registrar nuevo paciente (CREATE)
    Retorna: (True, id_nuevo) o (False, mensaje_error)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            INSERT INTO Pacientes 
            (dni, nombre, apellido, fecha_nacimiento, sexo, 
             telefono, email, domicilio, obra_social)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos['dni'],
            datos['nombre'],
            datos['apellido'],
            datos['fecha_nac'],
            datos['sexo'],
            datos.get('telefono', ''),
            datos.get('email', ''),
            datos.get('domicilio', ''),
            datos.get('obra_social', '')
        ))
        
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        return True, nuevo_id
        
    except sqlite3.IntegrityError:
        return False, "❌ DNI duplicado. Ya existe un paciente con ese DNI."
    except Exception as e:
        return False, f"❌ Error: {e}"


def buscar_paciente(dni):
    """
    HU-02: Buscar paciente por DNI (READ)
    Retorna: dict con datos del paciente o None
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM Pacientes WHERE dni = ?", (dni,))
        paciente = cursor.fetchone()
        conexion.close()
        
        if paciente:
            return {
                'id': paciente[0],
                'dni': paciente[1],
                'nombre': paciente[2],
                'apellido': paciente[3],
                'fecha_nac': paciente[4],
                'sexo': paciente[5],
                'telefono': paciente[6] or '',
                'email': paciente[7] or '',
                'domicilio': paciente[8] or '',
                'obra_social': paciente[9] or '',
                'fecha_registro': paciente[10]
            }
        return None
        
    except Exception as e:
        return None


def modificar_paciente(paciente_id, datos):
    """
    HU-03: Modificar datos de un paciente (UPDATE)
    Retorna: (True, mensaje) o (False, mensaje_error)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            UPDATE Pacientes 
            SET telefono = ?, email = ?, domicilio = ?, obra_social = ?
            WHERE id = ?
        """, (
            datos.get('telefono', ''),
            datos.get('email', ''),
            datos.get('domicilio', ''),
            datos.get('obra_social', ''),
            paciente_id
        ))
        
        conexion.commit()
        afectados = cursor.rowcount
        conexion.close()
        
        if afectados > 0:
            return True, "✅ Paciente modificado correctamente."
        return False, "❌ No se encontró el paciente."
        
    except Exception as e:
        return False, f"❌ Error: {e}"


def eliminar_paciente(paciente_id):
    """
    HU-03: Eliminar paciente (DELETE)
    Retorna: (True, mensaje) o (False, mensaje_error)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        # Primero eliminar signos vitales asociados (integridad referencial)
        cursor.execute("DELETE FROM SignosVitales WHERE paciente_id = ?", (paciente_id,))
        cursor.execute("DELETE FROM Pacientes WHERE id = ?", (paciente_id,))
        
        conexion.commit()
        afectados = cursor.rowcount
        conexion.close()
        
        if afectados > 0:
            return True, "✅ Paciente eliminado correctamente."
        return False, "❌ No se encontró el paciente."
        
    except Exception as e:
        return False, f"❌ Error: {e}"


def listar_pacientes():
    """
    Obtiene todos los pacientes ordenados por apellido y nombre
    Retorna: Lista de tuplas (id, dni, nombre, apellido, telefono)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, dni, nombre, apellido, telefono 
            FROM Pacientes 
            ORDER BY apellido, nombre
        """)
        pacientes = cursor.fetchall()
        conexion.close()
        return pacientes
    except Exception as e:
        return []


# -------------------- SIGNOS VITALES (HU-03) --------------------

def registrar_signos_vitales(paciente_id, datos):
    """
    HU-03: Registrar signos vitales (CREATE)
    
    Parámetros:
        paciente_id (int): ID del paciente
        datos (dict): 
            - presion_sistolica (int): mmHg
            - presion_diastolica (int): mmHg
            - frecuencia_cardiaca (int): latidos por minuto
            - temperatura (float): grados Celsius
            - saturacion_oxigeno (int): porcentaje
            - motivo_consulta (str): texto libre (obligatorio)
            - medico_id (int): opcional
    
    Retorna: (True, id_nuevo) o (False, mensaje_error)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            INSERT INTO SignosVitales 
            (paciente_id, presion_sistolica, presion_diastolica, 
             frecuencia_cardiaca, temperatura, saturacion_oxigeno, 
             motivo_consulta, medico_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            paciente_id,
            datos.get('presion_sistolica'),
            datos.get('presion_diastolica'),
            datos.get('frecuencia_cardiaca'),
            datos.get('temperatura'),
            datos.get('saturacion_oxigeno'),
            datos['motivo_consulta'],
            datos.get('medico_id')
        ))
        
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        return True, nuevo_id
        
    except Exception as e:
        return False, f"❌ Error al registrar signos vitales: {e}"


def obtener_signos_vitales(paciente_id, limite=10):
    """
    Obtiene los últimos 'limite' registros de signos vitales de un paciente
    Retorna: Lista de tuplas ordenadas por fecha descendente
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT * FROM SignosVitales 
            WHERE paciente_id = ? 
            ORDER BY fecha_hora DESC 
            LIMIT ?
        """, (paciente_id, limite))
        registros = cursor.fetchall()
        conexion.close()
        return registros
        
    except Exception as e:
        return []


# ================================================================
# CAPA DE PRESENTACIÓN (FRONTEND)
# ================================================================

class AppPacientes:
    """
    Aplicación principal unificada.
    CRUD completo de pacientes + gestión de signos vitales.
    """
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Gestión de Pacientes (Sprint 2)")
        self.root.geometry("950x650")
        self.root.configure(bg='#f0f0f0')
        
        # Centrar la ventana en la pantalla
        self.root.update_idletasks()
        ancho = self.root.winfo_width()
        alto = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.root.winfo_screenheight() // 2) - (alto // 2)
        self.root.geometry(f'{ancho}x{alto}+{x}+{y}')
        
        # ---------- FRAME PRINCIPAL ----------
        self.frame_principal = tk.Frame(self.root, bg='#f0f0f0')
        self.frame_principal.pack(fill='both', expand=True, padx=20, pady=20)
        
        # ---------- TÍTULO ----------
        titulo = tk.Label(
            self.frame_principal,
            text="🏥 HOSPITAL UNIVERSITARIO SAN JUSTO",
            font=('Arial', 18, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        )
        titulo.pack(pady=5)
        
        subtitulo = tk.Label(
            self.frame_principal,
            text="Sistema de Gestión de Pacientes - Sprint 2 (CRUD + Signos Vitales)",
            font=('Arial', 11),
            bg='#f0f0f0',
            fg='#666666'
        )
        subtitulo.pack(pady=2)
        
        # Separador
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # ---------- BOTONES PRINCIPALES ----------
        frame_botones = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_botones.pack(pady=10)
        
        # Configuración común para todos los botones
        estilo_boton = {
            'font': ('Arial', 10, 'bold'),
            'padx': 15,
            'pady': 8,
            'relief': 'raised',
            'bd': 2
        }
        
        # Botón Registrar (Verde)
        self.btn_registrar = tk.Button(
            frame_botones,
            text="📋 Registrar Paciente",
            bg='#4CAF50',
            fg='white',
            command=self.abrir_registro,
            **estilo_boton
        )
        self.btn_registrar.pack(side='left', padx=3)
        
        # Botón Buscar (Azul)
        self.btn_buscar = tk.Button(
            frame_botones,
            text="🔍 Buscar Paciente",
            bg='#2196F3',
            fg='white',
            command=self.abrir_busqueda,
            **estilo_boton
        )
        self.btn_buscar.pack(side='left', padx=3)
        
        # Botón Modificar (Naranja)
        self.btn_modificar = tk.Button(
            frame_botones,
            text="✏️ Modificar Paciente",
            bg='#FF9800',
            fg='white',
            command=self.abrir_modificacion,
            **estilo_boton
        )
        self.btn_modificar.pack(side='left', padx=3)
        
        # Botón Eliminar (Rojo)
        self.btn_eliminar = tk.Button(
            frame_botones,
            text="🗑️ Eliminar Paciente",
            bg='#f44336',
            fg='white',
            command=self.eliminar_paciente,
            **estilo_boton
        )
        self.btn_eliminar.pack(side='left', padx=3)
        
        # --- SEPARADOR VISUAL ENTRE GRUPOS DE BOTONES ---
        tk.Frame(frame_botones, width=20, bg='#f0f0f0').pack(side='left')
        frame_botones = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_botones.pack(pady=10)
        
        # Botón Signos Vitales (Rosa)
        self.btn_signos = tk.Button(
            frame_botones,
            text="❤️ Signos Vitales",
            bg='#E91E63',
            fg='white',
            command=self.abrir_signos,
            **estilo_boton
        )
        self.btn_signos.pack(side='left', padx=3)
        
        # --- SEPARADOR VISUAL ENTRE GRUPOS DE BOTONES ---
        tk.Frame(frame_botones, width=20, bg='#f0f0f0').pack(side='left')
        
        # Botón Ver Todos (Gris)
        self.btn_ver_todos = tk.Button(
            frame_botones,
            text="📊 Ver Todos",
            bg='#607D8B',
            fg='white',
            command=self.ver_todos,
            **estilo_boton
        )
        self.btn_ver_todos.pack(side='left', padx=3)
        
        # Separador
        tk.Frame(self.frame_principal, height=2, bg='#cccccc').pack(fill='x', pady=10)
        
        # ---------- LABEL DE RESULTADOS ----------
        self.label_resultados = tk.Label(
            self.frame_principal,
            text="Seleccione una acción para comenzar",
            font=('Arial', 11, 'italic'),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_resultados.pack(pady=5)
        
        # ---------- TABLA DE PACIENTES ----------
        frame_tabla = tk.Frame(self.frame_principal, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        self.tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'DNI', 'Nombre', 'Apellido', 'Telefono'),
            show='headings',
            height=12,
            selectmode='browse'
        )
        
        # Configurar columnas
        columnas = [
            ('ID', 'HC', 50, 'center'),
            ('DNI', 'DNI', 100, 'center'),
            ('Nombre', 'Nombre', 200, 'w'),
            ('Apellido', 'Apellido', 200, 'w'),
            ('Telefono', 'Teléfono', 120, 'center')
        ]
        
        for col, heading, width, anchor in columnas:
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor=anchor)
        
        self.tree.pack(side='left', fill='both', expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # ---------- ESTADO ----------
        self.label_estado = tk.Label(
            self.frame_principal,
            text="✅ OpenHIS-UNLaM - Doble clic en un paciente para ver sus signos vitales",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        )
        self.label_estado.pack(side='bottom', pady=5)
        
        # ---------- EVENTOS ----------
        # Doble clic en la tabla abre los signos vitales del paciente
        self.tree.bind('<Double-1>', self.on_doble_click)
        
        # Cargar todos los pacientes al iniciar
        self.ver_todos()
    
    # ============================================================
    # MÉTODOS DE LA APLICACIÓN
    # ============================================================
    
    # ---------- VER TODOS ----------
    def ver_todos(self):
        """Actualiza la tabla con todos los pacientes"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        pacientes = listar_pacientes()
        for p in pacientes:
            self.tree.insert('', 'end', values=(p[0], p[1], p[2], p[3], p[4]))
        
        self.label_resultados.config(text=f"📊 Total de pacientes: {len(pacientes)}")
    
    # ---------- DOBLE CLICK ----------
    def on_doble_click(self, event):
        """Maneja el doble clic en la tabla"""
        seleccion = self.tree.selection()
        if seleccion:
            item = self.tree.item(seleccion[0])
            paciente_id = item['values'][0]
            # Buscar los datos completos del paciente
            # (necesitamos el DNI para buscarlo)
            dni = item['values'][1]
            paciente = buscar_paciente(dni)
            if paciente:
                self.ventana_signos(paciente)
    
    # ---------- REGISTRAR PACIENTE ---------- 
    def abrir_registro(self):
        """Abre ventana para registrar nuevo paciente"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Registrar Nuevo Paciente")
        ventana.geometry("520x600")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        # Título
        tk.Label(
            ventana,
            text="📋 REGISTRO DE PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=10)
        
        tk.Label(
            ventana,
            text="Los campos con * son obligatorios",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        ).pack(pady=2)
        
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(padx=30, pady=10)
        
        campos = [
            ('DNI *', 'dni', True),
            ('Nombre *', 'nombre', True),
            ('Apellido *', 'apellido', True),
            ('Fecha Nac. (YYYY-MM-DD) *', 'fecha_nac', True),
            ('Sexo (M/F) *', 'sexo', True),
            ('Teléfono', 'telefono', False),
            ('Email', 'email', False),
            ('Domicilio', 'domicilio', False),
            ('Obra Social', 'obra_social', False)
        ]
        
        self.entries = {}
        for label_text, key, obligatorio in campos:
            frame = tk.Frame(frame_campos, bg='#f0f0f0')
            frame.pack(fill='x', pady=3)
            
            texto = label_text + ' *' if obligatorio else label_text
            tk.Label(
                frame,
                text=texto,
                width=22,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10)
            ).pack(side='left')
            
            entry = tk.Entry(frame, width=28, font=('Arial', 10))
            entry.pack(side='right')
            self.entries[key] = entry
        
        def guardar():
            obligatorios = ['dni', 'nombre', 'apellido', 'fecha_nac', 'sexo']
            for campo in obligatorios:
                if not self.entries[campo].get().strip():
                    messagebox.showerror("Error", f"El campo '{campo}' es obligatorio.")
                    return
            
            datos = {
                'dni': self.entries['dni'].get().strip(),
                'nombre': self.entries['nombre'].get().strip(),
                'apellido': self.entries['apellido'].get().strip(),
                'fecha_nac': self.entries['fecha_nac'].get().strip(),
                'sexo': self.entries['sexo'].get().strip().upper(),
                'telefono': self.entries['telefono'].get().strip(),
                'email': self.entries['email'].get().strip(),
                'domicilio': self.entries['domicilio'].get().strip(),
                'obra_social': self.entries['obra_social'].get().strip()
            }
            
            if datos['sexo'] not in ['M', 'F']:
                messagebox.showerror("Error", "El sexo debe ser 'M' o 'F'.")
                return
            
            resultado, info = registrar_paciente(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Paciente registrado con éxito.\nHistoria Clínica N°: {info}")
                ventana.destroy()
                self.ver_todos()
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        
        tk.Button(
            frame_botones,
            text="💾 Guardar",
            bg='#4CAF50',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=25,
            pady=8,
            command=guardar
        ).pack(side='left', padx=10)
        
        tk.Button(
            frame_botones,
            text="❌ Cancelar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=25,
            pady=8,
            command=ventana.destroy
        ).pack(side='left', padx=10)
    
    # ---------- BUSCAR PACIENTE ----------
    def abrir_busqueda(self):
        """Abre ventana para buscar paciente por DNI"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar Paciente")
        ventana.geometry("480x350")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="🔍 BUSCAR PACIENTE POR DNI",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=15)
        
        frame_busqueda = tk.Frame(ventana, bg='#f0f0f0')
        frame_busqueda.pack(pady=10)
        
        tk.Label(
            frame_busqueda,
            text="DNI:",
            font=('Arial', 12, 'bold'),
            bg='#f0f0f0'
        ).pack(side='left', padx=10)
        
        entry_dni = tk.Entry(frame_busqueda, font=('Arial', 12), width=20)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()
        
        frame_resultado = tk.Frame(ventana, bg='#f0f0f0')
        frame_resultado.pack(pady=10, fill='both', expand=True, padx=20)
        
        label_datos = tk.Label(
            frame_resultado,
            text="Ingrese un DNI y presione Buscar",
            font=('Arial', 10),
            bg='#f0f0f0',
            fg='#666666',
            justify='left'
        )
        label_datos.pack(pady=5)
        
        def buscar():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI para buscar.")
                return
            
            resultado = buscar_paciente(dni)
            if resultado:
                texto = (
                    f"🏥 HISTORIA CLÍNICA: {resultado['id']}\n"
                    f"📋 DNI: {resultado['dni']}\n"
                    f"👤 Nombre: {resultado['nombre']} {resultado['apellido']}\n"
                    f"📅 Fecha Nac.: {resultado['fecha_nac']}\n"
                    f"⚧️ Sexo: {resultado['sexo']}\n"
                    f"📞 Teléfono: {resultado['telefono'] or 'No registrado'}\n"
                    f"✉️ Email: {resultado['email'] or 'No registrado'}\n"
                    f"🏠 Domicilio: {resultado['domicilio'] or 'No registrado'}\n"
                    f"🏢 Obra Social: {resultado['obra_social'] or 'No registrada'}\n"
                    f"📅 Registro: {resultado['fecha_registro']}"
                )
                label_datos.config(text=texto, fg='#333333')
            else:
                label_datos.config(text="❌ Paciente no encontrado.", fg='#f44336')
        
        entry_dni.bind('<Return>', lambda e: buscar())
        
        # Botones
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=10)
        
        tk.Button(
            frame_botones,
            text="🔍 Buscar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=buscar
        ).pack(side='left', padx=10)
        
        tk.Button(
            frame_botones,
            text="❌ Cerrar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=ventana.destroy
        ).pack(side='left', padx=10)
    
    # ---------- MODIFICAR PACIENTE ----------
    def abrir_modificacion(self):
        """Abre ventana para modificar datos de un paciente"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Modificar Paciente")
        ventana.geometry("520x450")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="✏️ MODIFICAR PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=10)
        
        # Buscar por DNI
        frame_buscar = tk.Frame(ventana, bg='#f0f0f0')
        frame_buscar.pack(pady=10)
        
        tk.Label(
            frame_buscar,
            text="DNI del paciente:",
            font=('Arial', 11),
            bg='#f0f0f0'
        ).pack(side='left', padx=10)
        
        entry_dni = tk.Entry(frame_buscar, font=('Arial', 11), width=20)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()
        
        # Frame para campos modificables
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(pady=10, padx=30, fill='both', expand=True)
        
        label_nombre = tk.Label(
            frame_campos,
            text="Ingrese un DNI y presione Buscar",
            font=('Arial', 11, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        )
        label_nombre.pack(pady=5)
        
        campos_mod = [
            ('Teléfono', 'telefono'),
            ('Email', 'email'),
            ('Domicilio', 'domicilio'),
            ('Obra Social', 'obra_social')
        ]
        
        entries_mod = {}
        frame_entries = tk.Frame(frame_campos, bg='#f0f0f0')
        
        for label_text, key in campos_mod:
            frame = tk.Frame(frame_entries, bg='#f0f0f0')
            frame.pack(fill='x', pady=3)
            
            tk.Label(
                frame,
                text=label_text + ":",
                width=15,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 10)
            ).pack(side='left')
            
            entry = tk.Entry(frame, width=30, font=('Arial', 10))
            entry.pack(side='right')
            entries_mod[key] = entry
        
        paciente_id_actual = None
        
        def buscar_modificar():
            nonlocal paciente_id_actual
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI.")
                return
            
            resultado = buscar_paciente(dni)
            if resultado:
                paciente_id_actual = resultado['id']
                label_nombre.config(
                    text=f"Paciente: {resultado['nombre']} {resultado['apellido']} (HC: {resultado['id']})",
                    fg='#003366'
                )
                entries_mod['telefono'].delete(0, tk.END)
                entries_mod['telefono'].insert(0, resultado['telefono'] or '')
                entries_mod['email'].delete(0, tk.END)
                entries_mod['email'].insert(0, resultado['email'] or '')
                entries_mod['domicilio'].delete(0, tk.END)
                entries_mod['domicilio'].insert(0, resultado['domicilio'] or '')
                entries_mod['obra_social'].delete(0, tk.END)
                entries_mod['obra_social'].insert(0, resultado['obra_social'] or '')
                frame_entries.pack(pady=10)
            else:
                messagebox.showerror("Error", "Paciente no encontrado.")
        
        entry_dni.bind('<Return>', lambda e: buscar_modificar())
        
        tk.Button(
            ventana,
            text="🔍 Buscar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=buscar_modificar
        ).pack(pady=5)
        
        def guardar_modificacion():
            nonlocal paciente_id_actual
            if not paciente_id_actual:
                messagebox.showerror("Error", "Primero busque un paciente.")
                return
            
            datos = {
                'telefono': entries_mod['telefono'].get().strip(),
                'email': entries_mod['email'].get().strip(),
                'domicilio': entries_mod['domicilio'].get().strip(),
                'obra_social': entries_mod['obra_social'].get().strip()
            }
            
            resultado, mensaje = modificar_paciente(paciente_id_actual, datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ {mensaje}")
                ventana.destroy()
                self.ver_todos()
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=15)
        
        tk.Button(
            frame_botones,
            text="💾 Guardar Cambios",
            bg='#FF9800',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=guardar_modificacion
        ).pack(side='left', padx=10)
        
        tk.Button(
            frame_botones,
            text="❌ Cancelar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=ventana.destroy
        ).pack(side='left', padx=10)
    
    # ---------- ELIMINAR PACIENTE ----------
    def eliminar_paciente(self):
        """Abre ventana para eliminar un paciente"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Eliminar Paciente")
        ventana.geometry("480x250")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="🗑️ ELIMINAR PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#f44336'
        ).pack(pady=10)
        
        tk.Label(
            ventana,
            text="⚠️ Esta acción eliminará al paciente y TODOS sus signos vitales.\nEsta operación no se puede deshacer.",
            font=('Arial', 10),
            bg='#f0f0f0',
            fg='#f44336'
        ).pack(pady=5)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(pady=15)
        
        tk.Label(
            frame,
            text="DNI del paciente:",
            font=('Arial', 11),
            bg='#f0f0f0'
        ).pack(side='left', padx=10)
        
        entry_dni = tk.Entry(frame, font=('Arial', 11), width=20)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()
        
        def confirmar_eliminar():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI.")
                return
            
            paciente = buscar_paciente(dni)
            if not paciente:
                messagebox.showerror("Error", "Paciente no encontrado.")
                return
            
            if messagebox.askyesno(
                "⚠️ Confirmar Eliminación",
                f"¿Está seguro de eliminar a {paciente['nombre']} {paciente['apellido']} (HC: {paciente['id']})?\n\nSe eliminarán también sus {len(obtener_signos_vitales(paciente['id']))} registros de signos vitales."
            ):
                resultado, mensaje = eliminar_paciente(paciente['id'])
                if resultado:
                    messagebox.showinfo("Éxito", f"✅ {mensaje}")
                    ventana.destroy()
                    self.ver_todos()
                else:
                    messagebox.showerror("Error", f"❌ {mensaje}")
        
        entry_dni.bind('<Return>', lambda e: confirmar_eliminar())
        
        tk.Button(
            ventana,
            text="🗑️ Eliminar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=25,
            pady=8,
            command=confirmar_eliminar
        ).pack(pady=15)
    
    # ---------- SIGNOS VITALES ----------
    def abrir_signos(self):
        """Abre ventana para gestionar signos vitales"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Gestionar Signos Vitales")
        ventana.geometry("450x200")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="❤️ GESTIÓN DE SIGNOS VITALES",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#E91E63'
        ).pack(pady=10)
        
        tk.Label(
            ventana,
            text="Ingrese el DNI del paciente para continuar:",
            font=('Arial', 11),
            bg='#f0f0f0'
        ).pack(pady=5)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(pady=15)
        
        tk.Label(
            frame,
            text="DNI:",
            font=('Arial', 12, 'bold'),
            bg='#f0f0f0'
        ).pack(side='left', padx=10)
        
        entry_dni = tk.Entry(frame, font=('Arial', 12), width=20)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()
        
        def continuar():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI.")
                return
            
            paciente = buscar_paciente(dni)
            if not paciente:
                messagebox.showerror("Error", "Paciente no encontrado.")
                return
            
            ventana.destroy()
            self.ventana_signos(paciente)
        
        entry_dni.bind('<Return>', lambda e: continuar())
        
        tk.Button(
            ventana,
            text="❤️ Continuar",
            bg='#E91E63',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=25,
            pady=8,
            command=continuar
        ).pack(pady=10)
    
    def ventana_signos(self, paciente):
        """
        Ventana para registrar y ver signos vitales de un paciente
        """
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Signos Vitales - {paciente['nombre']} {paciente['apellido']}")
        ventana.geometry("650x600")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        # Título con datos del paciente
        tk.Label(
            ventana,
            text=f"❤️ SIGNOS VITALES",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#E91E63'
        ).pack(pady=5)
        
        tk.Label(
            ventana,
            text=f"Paciente: {paciente['nombre']} {paciente['apellido']} (HC: {paciente['id']})",
            font=('Arial', 12, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=5)
        
        # Separador
        tk.Frame(ventana, height=2, bg='#cccccc').pack(fill='x', pady=5, padx=20)
        
        # ---------- FRAME DE REGISTRO ----------
        frame_registro = tk.LabelFrame(
            ventana,
            text="📝 Registrar Nuevos Signos Vitales",
            font=('Arial', 11, 'bold'),
            bg='#f0f0f0',
            fg='#003366',
            padx=15,
            pady=10
        )
        frame_registro.pack(fill='x', padx=20, pady=10)
        
        campos = [
            ('Presión Sistólica (mmHg)', 'sistolica'),
            ('Presión Diastólica (mmHg)', 'diastolica'),
            ('Frecuencia Cardíaca (lpm)', 'fc'),
            ('Temperatura (°C)', 'temp'),
            ('Saturación O₂ (%)', 'sat'),
            ('Motivo de Consulta *', 'motivo')
        ]
        
        entries = {}
        # Usar grid para mejor organización
        for i, (label_text, key) in enumerate(campos):
            row = i // 2
            col = (i % 2) * 2
            
            tk.Label(
                frame_registro,
                text=label_text,
                width=20,
                anchor='w',
                bg='#f0f0f0',
                font=('Arial', 9)
            ).grid(row=row, column=col, sticky='w', pady=2, padx=5)
            
            entry = tk.Entry(frame_registro, width=20, font=('Arial', 10))
            entry.grid(row=row, column=col+1, pady=2, padx=5)
            entries[key] = entry
        
        # Botón Guardar Signos
        def guardar_signos():
            try:
                motivo = entries['motivo'].get().strip()
                if not motivo:
                    messagebox.showerror("Error", "El motivo de consulta es obligatorio.")
                    return
                
                # Convertir valores numéricos
                datos = {
                    'presion_sistolica': int(entries['sistolica'].get()) if entries['sistolica'].get() else None,
                    'presion_diastolica': int(entries['diastolica'].get()) if entries['diastolica'].get() else None,
                    'frecuencia_cardiaca': int(entries['fc'].get()) if entries['fc'].get() else None,
                    'temperatura': float(entries['temp'].get()) if entries['temp'].get() else None,
                    'saturacion_oxigeno': int(entries['sat'].get()) if entries['sat'].get() else None,
                    'motivo_consulta': motivo,
                    'medico_id': None
                }
                
                resultado, info = registrar_signos_vitales(paciente['id'], datos)
                if resultado:
                    messagebox.showinfo("Éxito", "✅ Signos vitales registrados correctamente.")
                    # Limpiar campos
                    for key in entries:
                        entries[key].delete(0, tk.END)
                    # Actualizar historial
                    actualizar_historial()
                else:
                    messagebox.showerror("Error", f"❌ {info}")
                    
            except ValueError:
                messagebox.showerror("Error", "Ingrese valores numéricos válidos en los campos correspondientes.")
        
        tk.Button(
            frame_registro,
            text="💾 Guardar Signos Vitales",
            bg='#4CAF50',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=guardar_signos
        ).grid(row=3, column=0, columnspan=4, pady=10)
        
        # ---------- FRAME DE HISTORIAL ----------
        frame_historial = tk.LabelFrame(
            ventana,
            text="📊 Historial de Signos Vitales (últimos 10)",
            font=('Arial', 11, 'bold'),
            bg='#f0f0f0',
            fg='#003366',
            padx=10,
            pady=10
        )
        frame_historial.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Treeview para historial
        tree_historial = ttk.Treeview(
            frame_historial,
            columns=('Fecha', 'Presión', 'FC', 'Temp', 'SatO₂', 'Motivo'),
            show='headings',
            height=6
        )
        tree_historial.heading('Fecha', text='Fecha/Hora')
        tree_historial.heading('Presión', text='Presión')
        tree_historial.heading('FC', text='FC (lpm)')
        tree_historial.heading('Temp', text='Temp (°C)')
        tree_historial.heading('SatO₂', text='SatO₂ (%)')
        tree_historial.heading('Motivo', text='Motivo')
        
        tree_historial.column('Fecha', width=150)
        tree_historial.column('Presión', width=100)
        tree_historial.column('FC', width=80, anchor='center')
        tree_historial.column('Temp', width=80, anchor='center')
        tree_historial.column('SatO₂', width=80, anchor='center')
        tree_historial.column('Motivo', width=150)
        
        tree_historial.pack(side='left', fill='both', expand=True)
        
        # Scrollbar
        scroll_historial = ttk.Scrollbar(frame_historial, orient='vertical', command=tree_historial.yview)
        scroll_historial.pack(side='right', fill='y')
        tree_historial.configure(yscrollcommand=scroll_historial.set)
        
        def actualizar_historial():
            """Actualiza el historial de signos vitales"""
            for item in tree_historial.get_children():
                tree_historial.delete(item)
            
            registros = obtener_signos_vitales(paciente['id'])
            for r in registros:
                presion = f"{r[3]}/{r[4]}" if r[3] and r[4] else "-"
                tree_historial.insert('', 'end', values=(
                    r[2],  # fecha_hora
                    presion,
                    r[5] or '-',  # fc
                    r[6] or '-',  # temp
                    r[7] or '-',  # sat
                    r[8] or '-'   # motivo
                ))
            
            # Actualizar estado
            estado_historial.config(text=f"Total de registros: {len(registros)}")
        
        # Estado del historial
        estado_historial = tk.Label(
            frame_historial,
            text="Total de registros: 0",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666'
        )
        estado_historial.pack(side='bottom', pady=5)
        
        # Cargar historial inicial
        actualizar_historial()
        
        # ---------- BOTÓN CERRAR ----------
        tk.Button(
            ventana,
            text="❌ Cerrar",
            bg='#f44336',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=25,
            pady=8,
            command=ventana.destroy
        ).pack(pady=10)

# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = AppPacientes(root)
    root.mainloop()
