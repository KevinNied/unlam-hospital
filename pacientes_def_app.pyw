# ================================================================
# Pacientes_def_app.pyw
# SPRINT 3 - MÓDULO DE GESTIÓN DE PACIENTES (INDEPENDIENTE)
# ================================================================
#
# FUNCIONALIDADES:
#   ✅ Registrar paciente (CREATE) - HU-01
#   ✅ Buscar paciente por DNI (READ) - HU-02
#   ✅ Modificar datos del paciente (UPDATE)
#   ✅ Baja lógica de paciente (DELETE lógico - activo = 0)
#   ✅ Reactivar paciente (si fue dado de baja)
#   ✅ Ver listado de pacientes activos
#   ✅ Ver listado de pacientes inactivos
#   ✅ Interfaz gráfica con Tkinter
#
# NOTA IMPORTANTE:
#   Los signos vitales ahora son un módulo INDEPENDIENTE
#   (signos_vitales_app.py)
#
#   El borrado es LÓGICO (activo = 0). Los datos se conservan
#   para auditoría y para evitar eliminar información clínica.
# ================================================================

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
from pathlib import Path

try:
    from tkcalendar import DateEntry
except ImportError:
    DateEntry = None

COLOR_FONDO = '#F4F7FB'
COLOR_TEXTO = '#183B56'
COLOR_SECUNDARIO = '#5C7184'


class BotonRedondeado(tk.Canvas):
    """Botón sin relieve nativo para conservar bordes redondeados en Windows."""

    def __init__(self, parent, text, command, color, width=140, height=44):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent.cget('bg'),
            highlightthickness=0,
            bd=0,
            cursor='hand2'
        )
        self.command = command
        self.color = color
        self.hover_color = self._oscurecer(color)
        self._dibujar(text, color)
        self.bind('<Enter>', lambda event: self._dibujar(text, self.hover_color))
        self.bind('<Leave>', lambda event: self._dibujar(text, self.color))
        self.bind('<Button-1>', lambda event: self.command())

    def _dibujar(self, text, color):
        self.delete('all')
        ancho = int(self['width'])
        alto = int(self['height'])
        radio = 12
        self.create_rectangle(radio, 0, ancho - radio, alto, fill=color, outline=color)
        self.create_rectangle(0, radio, ancho, alto - radio, fill=color, outline=color)
        for x, y, inicio in ((0, 0, 90), (ancho - 2 * radio, 0, 0),
                             (0, alto - 2 * radio, 180), (ancho - 2 * radio, alto - 2 * radio, 270)):
            self.create_arc(x, y, x + 2 * radio, y + 2 * radio, start=inicio,
                            extent=90, fill=color, outline=color)
        self.create_text(ancho // 2, alto // 2, text=text,
                         fill='white', font=('Segoe UI', 11, 'bold'))

    @staticmethod
    def _oscurecer(color):
        color = color.lstrip('#')
        rgb = [max(0, int(int(color[i:i + 2], 16) * 0.85)) for i in (0, 2, 4)]
        return '#' + ''.join(f'{valor:02x}' for valor in rgb)


class EntradaRedondeada(tk.Frame):
    """Campo de texto cuadrado para igualar entradas y listas desplegables."""

    def __init__(self, parent, width=205, height=30):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg='white',
            highlightbackground='#AEBBC5',
            highlightcolor='#2B6384',
            highlightthickness=1,
            bd=0
        )
        self.pack_propagate(False)
        self.entry = tk.Entry(self, relief='flat', bd=0, highlightthickness=0,
                              bg='white', fg=COLOR_TEXTO, insertbackground=COLOR_TEXTO,
                              font=('Segoe UI', 10))
        self.entry.pack(fill='both', expand=True, padx=1, pady=1)

    def get(self):
        return self.entry.get()

    def delete(self, *args):
        return self.entry.delete(*args)

    def insert(self, *args):
        return self.entry.insert(*args)

    def bind(self, sequence=None, func=None, add=None):
        return self.entry.bind(sequence, func, add)

    def focus(self):
        return self.entry.focus()

# ================================================================
# CAPA DE ACCESO A DATOS (BACKEND)
# ================================================================

def conectar_bd():
    """Establece conexión con la base de datos Salud.db"""
    ruta_bd = Path(__file__).resolve().parent / 'DB' / 'Salud.db'
    return sqlite3.connect(ruta_bd)


# -------------------- CRUD DE PACIENTES --------------------

def registrar_paciente(datos):
    """
    HU-01: Registrar nuevo paciente (CREATE)
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("""
            INSERT INTO Pacientes 
            (dni, nombre, apellido, fecha_nacimiento, sexo, 
             telefono, email, domicilio, obra_social, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos['dni'],
            datos['nombre'],
            datos['apellido'],
            datos['fecha_nac'],
            datos['sexo'],
            datos.get('telefono', ''),
            datos.get('email', ''),
            datos.get('domicilio', ''),
            datos.get('obra_social', ''),
            1  # activo
        ))
        
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        print(f"[DEBUG] Paciente registrado con ID: {nuevo_id}")
        return True, nuevo_id
        
    except sqlite3.IntegrityError:
        return False, "❌ DNI duplicado. Ya existe un paciente con ese DNI."
    except Exception as e:
        print(f"[ERROR] Error en registrar_paciente: {e}")
        return False, f"❌ Error: {e}"


def buscar_paciente(dni):
    """
    HU-02: Buscar paciente por DNI (READ)
    Busca tanto activos como inactivos para permitir reactivación
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
                'fecha_registro': paciente[10],
                'activo': paciente[11] if len(paciente) > 11 else 1
            }
        return None
        
    except Exception as e:
        print(f"[ERROR] Error en buscar_paciente: {e}")
        return None


def buscar_pacientes_por_dni(texto, limite=8):
    """Busca pacientes cuyo DNI comienza con el texto ingresado."""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, dni, nombre, apellido, activo
            FROM Pacientes
            WHERE dni LIKE ?
            ORDER BY dni
            LIMIT ?
        """, (f'{texto}%', limite))
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        print(f"[ERROR] Error en buscar_pacientes_por_dni: {e}")
        return []


def buscar_paciente_por_id(paciente_id):
    """Busca un paciente por su ID"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM Pacientes WHERE id = ?", (paciente_id,))
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
                'fecha_registro': paciente[10],
                'activo': paciente[11] if len(paciente) > 11 else 1
            }
        return None
    except Exception as e:
        print(f"[ERROR] Error en buscar_paciente_por_id: {e}")
        return None


def listar_pacientes(activos=True):
    """
    Lista pacientes según su estado
    activos=True: solo activos
    activos=False: solo inactivos
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        if activos:
            cursor.execute("""
                SELECT id, dni, nombre, apellido, telefono, activo 
                FROM Pacientes 
                WHERE activo = 1
                ORDER BY apellido, nombre
            """)
        else:
            cursor.execute("""
                SELECT id, dni, nombre, apellido, telefono, activo 
                FROM Pacientes 
                WHERE activo = 0
                ORDER BY apellido, nombre
            """)
        
        pacientes = cursor.fetchall()
        conexion.close()
        print(f"[DEBUG] Pacientes {'activos' if activos else 'inactivos'}: {len(pacientes)}")
        return pacientes
        
    except Exception as e:
        print(f"[ERROR] Error en listar_pacientes: {e}")
        return []


def modificar_paciente(paciente_id, datos):
    """Modifica datos de un paciente"""
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
        print(f"[ERROR] Error en modificar_paciente: {e}")
        return False, f"❌ Error: {e}"


def dar_baja_paciente(paciente_id):
    """
    HU-03: Baja LÓGICA de paciente (DELETE lógico - activo = 0)
    
    IMPORTANTE: Los datos NO se eliminan. Se marca como inactivo.
    Los signos vitales y prescripciones se conservan.
    """
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        # Verificar que el paciente existe
        cursor.execute("SELECT id, activo FROM Pacientes WHERE id = ?", (paciente_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            conexion.close()
            return False, "❌ No se encontró el paciente."
        
        if resultado[1] == 0:
            conexion.close()
            return False, "❌ El paciente ya estaba dado de baja."
        
        # Baja lógica: activo = 0
        cursor.execute("UPDATE Pacientes SET activo = 0 WHERE id = ?", (paciente_id,))
        conexion.commit()
        conexion.close()
        
        print(f"[DEBUG] Paciente {paciente_id} dado de baja (lógica)")
        return True, "✅ Paciente dado de baja correctamente.\nLos signos vitales y prescripciones se conservan."
        
    except Exception as e:
        print(f"[ERROR] Error en dar_baja_paciente: {e}")
        return False, f"❌ Error: {e}"


def reactivar_paciente(paciente_id):
    """Reactiva un paciente dado de baja (activo = 1)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute("UPDATE Pacientes SET activo = 1 WHERE id = ?", (paciente_id,))
        conexion.commit()
        afectados = cursor.rowcount
        conexion.close()
        
        if afectados > 0:
            return True, "✅ Paciente reactivado correctamente."
        return False, "❌ No se encontró el paciente."
        
    except Exception as e:
        return False, f"❌ Error: {e}"


def contar_signos_vitales_paciente(paciente_id):
    """Cuenta los signos vitales asociados a un paciente"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM SignosVitales WHERE paciente_id = ?", (paciente_id,))
        total = cursor.fetchone()[0]
        conexion.close()
        return total
    except Exception as e:
        return 0


def contar_prescripciones_paciente(paciente_id):
    """Cuenta las prescripciones asociadas a un paciente"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM Prescripciones WHERE paciente_id = ?", (paciente_id,))
        total = cursor.fetchone()[0]
        conexion.close()
        return total
    except Exception as e:
        return 0


def listar_prescripciones_paciente(paciente_id):
    """Obtiene las prescripciones recientes de un paciente para su ficha."""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT p.fecha_prescripcion, f.nombre, p.dosis, p.via_administracion,
                   p.frecuencia, p.fecha_fin, p.activo
            FROM Prescripciones p
            LEFT JOIN Farmacos f ON p.farmaco_id = f.id
            WHERE p.paciente_id = ?
            ORDER BY p.fecha_prescripcion DESC
            LIMIT 20
        """, (paciente_id,))
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        print(f"[ERROR] Error en listar_prescripciones_paciente: {e}")
        return []


def listar_signos_vitales_paciente(paciente_id):
    """Obtiene los signos vitales recientes de un paciente para su ficha."""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT s.fecha_hora, s.presion_sistolica, s.presion_diastolica,
                   s.frecuencia_cardiaca, s.temperatura, s.saturacion_oxigeno,
                   s.motivo_consulta, s.activo
            FROM SignosVitales s
            WHERE s.paciente_id = ?
            ORDER BY s.fecha_hora DESC
            LIMIT 20
        """, (paciente_id,))
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        print(f"[ERROR] Error en listar_signos_vitales_paciente: {e}")
        return []


# ================================================================
# CAPA DE PRESENTACIÓN (FRONTEND)
# ================================================================

class AppPacientes:
    """Aplicación de gestión de pacientes (independiente de signos vitales)"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Gestión de Pacientes")
        self.root.geometry("1050x650")
        self.root.configure(bg=COLOR_FONDO)

        estilo = ttk.Style(self.root)
        estilo.theme_use('clam')
        estilo.configure('Patients.Treeview', background='#FFFFFF', fieldbackground='#FFFFFF',
                 foreground=COLOR_TEXTO, rowheight=32, font=('Segoe UI', 10))
        estilo.configure('Patients.Treeview.Heading', background='#1B4965', foreground='white',
                 font=('Segoe UI', 10, 'bold'), padding=(8, 8), relief='flat', borderwidth=0)
        estilo.map('Patients.Treeview.Heading', background=[('active', '#2B6384')],
                   foreground=[('active', 'white')])
        estilo.map('Patients.Treeview', background=[('selected', '#B8D8E8')],
               foreground=[('selected', COLOR_TEXTO)])
        
        # Centrar la ventana
        self.root.update_idletasks()
        ancho = self.root.winfo_width()
        alto = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.root.winfo_screenheight() // 2) - (alto // 2)
        self.root.geometry(f'{ancho}x{alto}+{x}+{y}')
        
        # ---------- FRAME PRINCIPAL ----------
        self.frame_principal = tk.Frame(self.root, bg=COLOR_FONDO)
        self.frame_principal.pack(fill='both', expand=True, padx=20, pady=20)
        
        # ---------- TÍTULO ----------
        titulo = tk.Label(
            self.frame_principal,
            text="👤 HOSPITAL UNIVERSITARIO SAN JUSTO",
            font=('Segoe UI', 18, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_TEXTO
        )
        titulo.pack(pady=5)
        
        subtitulo = tk.Label(
            self.frame_principal,
            text="Sistema de Gestión de Pacientes - Sprint 3",
            font=('Segoe UI', 11),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO
        )
        subtitulo.pack(pady=2)
        
        tk.Frame(self.frame_principal, height=1, bg='#D8E2EA').pack(fill='x', pady=10)
        
        # ---------- BOTONES PRINCIPALES ----------
        frame_botones = tk.Frame(self.frame_principal, bg=COLOR_FONDO)
        frame_botones.pack(pady=10)
        
        estilo_boton = {
            'font': ('Segoe UI', 10, 'bold'),
            'padx': 15,
            'pady': 8,
            'relief': 'flat',
            'bd': 0,
            'cursor': 'hand2'
        }
        
        self.btn_registrar = BotonRedondeado(
            frame_botones, "📋  Registrar Paciente", self.abrir_registro, '#4CAF50', 170, 42
        )
        self.btn_registrar.pack(side='left', padx=3)
        
        self.btn_buscar = BotonRedondeado(
            frame_botones, "🔍  Buscar Paciente", self.abrir_busqueda, '#2196F3', 155, 42
        )
        self.btn_buscar.pack(side='left', padx=3)
        
        self.btn_modificar = BotonRedondeado(
            frame_botones, "✏️  Modificar Paciente", self.abrir_modificacion, '#FF9800', 190, 42
        )
        self.btn_modificar.pack(side='left', padx=3)
        
        self.btn_baja = BotonRedondeado(
            frame_botones, "🗑️  Dar de Baja", self.dar_baja_paciente, '#f44336', 150, 42
        )
        self.btn_baja.pack(side='left', padx=3)
        
        # --- SEPARADOR ---
        tk.Frame(frame_botones, width=10, bg=COLOR_FONDO).pack(side='left')
        
        self.btn_ver_activos = BotonRedondeado(
            frame_botones, "📊  Ver Activos", lambda: self.ver_pacientes(activos=True), '#607D8B', 130, 42
        )
        self.btn_ver_activos.pack(side='left', padx=3)
        
        self.btn_ver_inactivos = BotonRedondeado(
            frame_botones, "📋  Ver Inactivos", lambda: self.ver_pacientes(activos=False), '#9E9E9E', 140, 42
        )
        self.btn_ver_inactivos.pack(side='left', padx=3)
        
        tk.Frame(self.frame_principal, height=1, bg='#D8E2EA').pack(fill='x', pady=10)
        
        # ---------- LABEL DE RESULTADOS ----------
        self.label_resultados = tk.Label(
            self.frame_principal,
            text="Seleccione una acción para comenzar",
            font=('Segoe UI', 10, 'italic'),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO
        )
        self.label_resultados.pack(pady=5)
        
        # ---------- TABLA DE PACIENTES ----------
        frame_tabla = tk.Frame(self.frame_principal, bg=COLOR_FONDO)
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        self.tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'DNI', 'Nombre', 'Apellido', 'Teléfono', 'Estado'),
            show='headings',
            height=12,
            selectmode='browse'
        )
        self.tree.configure(style='Patients.Treeview')
        self.tree.tag_configure('par', background='#F2F7FA')
        self.tree.tag_configure('impar', background='#FFFFFF')
        
        columnas = [
            ('ID', 'HC', 50, 'center'),
            ('DNI', 'DNI', 100, 'center'),
            ('Nombre', 'Nombre', 180, 'w'),
            ('Apellido', 'Apellido', 180, 'w'),
            ('Teléfono', 'Teléfono', 120, 'center'),
            ('Estado', 'Estado', 80, 'center')
        ]
        self.columnas = columnas
        self.orden_columna = None
        self.orden_ascendente = True
        
        for col, heading, width, anchor in columnas:
            self.tree.heading(col, text=heading, command=lambda columna=col: self.ordenar_tabla(columna))
            self.tree.column(col, width=width, anchor=anchor)
        
        self.tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Evento doble clic
        self.tree.bind('<Double-1>', self.on_doble_click)
        
        # ---------- ESTADO ----------
        self.label_estado = tk.Label(
            self.frame_principal,
            text="✅ OpenHIS-UNLaM",
            font=('Segoe UI', 9),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO
        )
        self.label_estado.pack(side='bottom', pady=5)
        
        # Cargar pacientes activos al iniciar
        self.ver_pacientes(activos=True)
    
    # ============================================================
    # MÉTODOS DE LA APLICACIÓN
    # ============================================================
    
    def ver_pacientes(self, activos=True):
        """Actualiza la tabla con pacientes según su estado"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        pacientes = listar_pacientes(activos=activos)
        
        for indice, p in enumerate(pacientes):
            # p = (id, dni, nombre, apellido, telefono, activo)
            estado = "✅ Activo" if p[5] == 1 else "🚫 Inactivo"
            etiqueta = 'par' if indice % 2 == 0 else 'impar'
            self.tree.insert('', 'end', values=(p[0], p[1], p[2], p[3], p[4] or '', estado), tags=(etiqueta,))
        
        tipo = "activos" if activos else "inactivos"
        self.label_resultados.config(text=f"📊 Total de pacientes {tipo}: {len(pacientes)}")

    def ordenar_tabla(self, columna):
        """Ordena la tabla por la columna seleccionada y alterna ascendente/descendente."""
        if self.orden_columna == columna:
            self.orden_ascendente = not self.orden_ascendente
        else:
            self.orden_columna = columna
            self.orden_ascendente = True

        items = [(self.tree.set(item, columna), item) for item in self.tree.get_children('')]

        def clave(valor):
            texto = valor[0].strip()
            return (0, int(texto)) if texto.isdigit() else (1, texto.lower())

        items.sort(key=clave, reverse=not self.orden_ascendente)
        for posicion, (_, item) in enumerate(items):
            self.tree.move(item, '', posicion)
            self.tree.item(item, tags=('par' if posicion % 2 == 0 else 'impar',))

        for nombre, encabezado, _, _ in self.columnas:
            indicador = ''
            if nombre == columna:
                indicador = '  ▲' if self.orden_ascendente else '  ▼'
            self.tree.heading(nombre, text=encabezado + indicador)
    
    def on_doble_click(self, event):
        """Maneja el doble clic en la tabla"""
        seleccion = self.tree.selection()
        if not seleccion:
            return
        
        item = self.tree.item(seleccion[0])
        valores = item['values']
        if not valores:
            return
        
        paciente_id = valores[0]
        paciente = buscar_paciente_por_id(paciente_id)
        if paciente:
            self.ver_detalle_paciente(paciente)
    
    def ver_detalle_paciente(self, paciente):
        """Muestra una ficha organizada con datos y actividad clínica."""
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Ficha del paciente - {paciente['nombre']} {paciente['apellido']}")
        ventana.geometry("820x650")
        ventana.minsize(680, 540)
        ventana.configure(bg=COLOR_FONDO)
        ventana.grab_set()
        ventana.resizable(True, True)

        estado = "✅ Activo" if paciente['activo'] == 1 else "🚫 Inactivo"
        tk.Label(
            ventana,
            text=f"👤 {paciente['nombre']} {paciente['apellido']}",
            font=('Segoe UI', 18, 'bold'), bg=COLOR_FONDO, fg=COLOR_TEXTO
        ).pack(pady=(12, 2))
        tk.Label(
            ventana,
            text=f"Historia Clínica N° {paciente['id']}   ·   DNI {paciente['dni']}   ·   {estado}",
            font=('Segoe UI', 10, 'bold'), bg=COLOR_FONDO, fg=COLOR_SECUNDARIO
        ).pack(pady=(0, 10))

        notebook = ttk.Notebook(ventana)
        notebook.pack(fill='both', expand=True, padx=20, pady=5)

        datos_tab = tk.Frame(notebook, bg=COLOR_FONDO)
        notebook.add(datos_tab, text='  Datos personales  ')
        detalles = [
            ('Fecha de nacimiento', paciente['fecha_nac']), ('Sexo', paciente['sexo']),
            ('Teléfono', paciente['telefono'] or 'No registrado'),
            ('Email', paciente['email'] or 'No registrado'),
            ('Domicilio', paciente['domicilio'] or 'No registrado'),
            ('Obra social', paciente['obra_social'] or 'No registrada'),
            ('Fecha de registro', paciente['fecha_registro'])
        ]
        for fila, (label, valor) in enumerate(detalles):
            tk.Label(datos_tab, text=label, font=('Segoe UI', 10, 'bold'),
                     bg=COLOR_FONDO, fg=COLOR_SECUNDARIO, anchor='w').grid(
                         row=fila, column=0, sticky='w', padx=30, pady=7)
            tk.Label(datos_tab, text=str(valor), font=('Segoe UI', 10),
                     bg=COLOR_FONDO, fg=COLOR_TEXTO, anchor='w').grid(
                         row=fila, column=1, sticky='w', padx=20, pady=7)
        datos_tab.columnconfigure(1, weight=1)

        prescripciones_tab = tk.Frame(notebook, bg=COLOR_FONDO)
        notebook.add(prescripciones_tab, text='  Prescripciones  ')
        prescripciones_tree = ttk.Treeview(
            prescripciones_tab,
            columns=('Fecha', 'Fármaco', 'Dosis', 'Vía', 'Frecuencia', 'Vencimiento', 'Estado'),
            show='headings', style='Patients.Treeview', selectmode='browse'
        )
        for columna, ancho in (
            ('Fecha', 130), ('Fármaco', 190), ('Dosis', 100), ('Vía', 100),
            ('Frecuencia', 120), ('Vencimiento', 110), ('Estado', 90)
        ):
            prescripciones_tree.heading(columna, text=columna)
            prescripciones_tree.column(columna, width=ancho, anchor='w')
        prescripciones_tree.pack(fill='both', expand=True, padx=10, pady=10)
        prescripciones_scroll = ttk.Scrollbar(prescripciones_tab, orient='vertical', command=prescripciones_tree.yview)
        prescripciones_scroll.pack(side='right', fill='y')
        prescripciones_tree.configure(yscrollcommand=prescripciones_scroll.set)
        for indice, registro in enumerate(listar_prescripciones_paciente(paciente['id'])):
            estado_prescripcion = 'Activa' if registro[6] == 1 else 'Anulada'
            prescripciones_tree.insert('', 'end', values=(
                registro[0] or '-', registro[1] or 'Sin fármaco', registro[2] or '-',
                registro[3] or '-', registro[4] or '-', registro[5] or '-', estado_prescripcion
            ), tags=('par' if indice % 2 == 0 else 'impar',))

        signos_tab = tk.Frame(notebook, bg=COLOR_FONDO)
        notebook.add(signos_tab, text='  Signos vitales  ')
        signos_tree = ttk.Treeview(
            signos_tab,
            columns=('Fecha', 'Presión', 'FC', 'Temp.', 'Sat. O2', 'Motivo', 'Estado'),
            show='headings', style='Patients.Treeview', selectmode='browse'
        )
        for columna, ancho in (
            ('Fecha', 140), ('Presión', 100), ('FC', 70), ('Temp.', 80),
            ('Sat. O2', 80), ('Motivo', 220), ('Estado', 90)
        ):
            signos_tree.heading(columna, text=columna)
            signos_tree.column(columna, width=ancho, anchor='w')
        signos_tree.pack(fill='both', expand=True, padx=10, pady=10)
        signos_scroll = ttk.Scrollbar(signos_tab, orient='vertical', command=signos_tree.yview)
        signos_scroll.pack(side='right', fill='y')
        signos_tree.configure(yscrollcommand=signos_scroll.set)
        for indice, registro in enumerate(listar_signos_vitales_paciente(paciente['id'])):
            presion = f'{registro[1]}/{registro[2]}' if registro[1] and registro[2] else '-'
            estado_signo = 'Activo' if registro[7] == 1 else 'Anulado'
            signos_tree.insert('', 'end', values=(
                registro[0] or '-', presion, registro[3] or '-', registro[4] or '-',
                registro[5] or '-', registro[6] or '-', estado_signo
            ), tags=('par' if indice % 2 == 0 else 'impar',))

        frame_botones = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_botones.pack(pady=12)
        if paciente['activo'] == 1:
            BotonRedondeado(
                frame_botones, "✏️  Modificar",
                lambda: [ventana.destroy(), self.abrir_modificacion_con_id(paciente['id'])],
                '#FF9800', 135, 40
            ).pack(side='left', padx=5)
            BotonRedondeado(
                frame_botones, "🗑️  Dar de Baja",
                lambda: [ventana.destroy(), self.baja_con_id(paciente['id'])],
                '#f44336', 150, 40
            ).pack(side='left', padx=5)
        else:
            BotonRedondeado(
                frame_botones, "♻️  Reactivar",
                lambda: [ventana.destroy(), self.reactivar_con_id(paciente['id'])],
                '#4CAF50', 135, 40
            ).pack(side='left', padx=5)
        BotonRedondeado(frame_botones, "✕  Cerrar", ventana.destroy, '#9E9E9E', 110, 40).pack(side='left', padx=5)
    
    # ---------- REGISTRAR PACIENTE ----------
    def abrir_registro(self):
        """Abre ventana para registrar nuevo paciente"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Registrar Nuevo Paciente")
        ventana.geometry("550x540")
        ventana.configure(bg=COLOR_FONDO)
        ventana.grab_set()
        ventana.resizable(False, False)
        
        tk.Label(
            ventana,
            text="📋 REGISTRO DE PACIENTE",
            font=('Segoe UI', 16, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_TEXTO
        ).pack(pady=(8, 4))
        
        tk.Label(
            ventana,
            text="Los campos con * son obligatorios",
            font=('Segoe UI', 9, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO
        ).pack(pady=(0, 5))
        
        frame_campos = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_campos.pack(padx=30, pady=5)
        
        campos = [
            ('DNI', 'dni', True),
            ('Nombre', 'nombre', True),
            ('Apellido', 'apellido', True),
            ('Fecha de nacimiento', 'fecha_nac', True),
            ('Sexo', 'sexo', True),
            ('Teléfono', 'telefono', False),
            ('Email', 'email', False),
            ('Domicilio', 'domicilio', False),
            ('Obra Social', 'obra_social', False)
        ]

        obras_sociales = [
            'OSDE', 'Swiss Medical', 'Galeno', 'Medife', 'Sancor Salud',
            'IOMA', 'PAMI', 'Particular'
        ]

        def crear_combo_busqueda(parent, valores):
            """Crea un combo editable que filtra sus opciones al escribir."""
            combo = ttk.Combobox(parent, width=26, font=('Segoe UI', 10), state='normal')
            valores = tuple(valores)
            combo['values'] = valores

            def restaurar_opciones(event=None):
                combo['values'] = valores

            def filtrar(event):
                if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab'):
                    return
                texto = combo.get().lower()
                coincidencias = [valor for valor in valores if texto in valor.lower()]
                combo['values'] = coincidencias

            combo.bind('<FocusIn>', restaurar_opciones)
            combo.bind('<KeyRelease>', filtrar)
            return combo

        def formatear_fecha(event):
            """Agrega guiones al escribir YYYYMMDD cuando no hay calendario."""
            if event.keysym in ('Left', 'Right', 'Tab'):
                return
            texto = ''.join(caracter for caracter in event.widget.get() if caracter.isdigit())[:8]
            formateado = texto
            if len(texto) > 4:
                formateado = f'{texto[:4]}-{texto[4:]}'
            if len(texto) > 6:
                formateado = f'{texto[:4]}-{texto[4:6]}-{texto[6:]}'
            event.widget.delete(0, tk.END)
            event.widget.insert(0, formateado)

        sugerencias = {
            'dni': 'Ej.: 36689468',
            'nombre': 'Ej.: Juan',
            'apellido': 'Ej.: Perez',
            'fecha_nac': 'AAAA-MM-DD',
            'telefono': 'Ej.: 1123456789',
            'email': 'Ej.: nombre@correo.com',
            'domicilio': 'Ej.: Calle 123'
        }

        def entrada_interna(entry):
            return getattr(entry, 'entry', entry)

        def agregar_sugerencia(entry, texto):
            interno = entrada_interna(entry)
            interno.insert(0, texto)
            interno.config(fg='#91A0AC')

            def enfocar(event):
                if entry.get() == texto:
                    entry.delete(0, tk.END)
                    interno.config(fg=COLOR_TEXTO)

            def desenfocar(event):
                if not entry.get().strip():
                    entry.insert(0, texto)
                    interno.config(fg='#91A0AC')
                else:
                    interno.config(fg=COLOR_TEXTO)

            def actualizar_color(event):
                if entry.get() != texto:
                    interno.config(fg=COLOR_TEXTO)

            entry.bind('<FocusIn>', enfocar, '+')
            entry.bind('<FocusOut>', desenfocar, '+')
            entry.bind('<KeyRelease>', actualizar_color, '+')

        validar_numerico = ventana.register(
            lambda valor: valor == '' or valor.isdigit()
        )
        
        self.entries = {}
        for label_text, key, obligatorio in campos:
            frame = tk.Frame(frame_campos, bg=COLOR_FONDO)
            frame.pack(fill='x', pady=2)
            
            texto = label_text + ' (*)' if obligatorio else label_text
            tk.Label(
                frame,
                text=texto,
                width=22,
                anchor='w',
                bg=COLOR_FONDO,
                fg=COLOR_TEXTO,
                font=('Segoe UI', 10, 'bold')
            ).pack(side='left')
            
            if key == 'fecha_nac':
                if DateEntry is not None:
                    entry = DateEntry(
                        frame,
                        width=26,
                        font=('Arial', 10),
                        date_pattern='yyyy-mm-dd',
                        locale='es_AR'
                    )
                    entry.delete(0, tk.END)
                else:
                    entry = EntradaRedondeada(frame)
                    entry.bind('<KeyRelease>', formatear_fecha)
            elif key == 'sexo':
                entry = crear_combo_busqueda(frame, ('F', 'M'))
            elif key == 'obra_social':
                entry = crear_combo_busqueda(frame, obras_sociales)
            else:
                entry = EntradaRedondeada(frame)
            if key in sugerencias and (key != 'fecha_nac' or DateEntry is None):
                agregar_sugerencia(entry, sugerencias[key])
            if key in ('dni', 'telefono'):
                entrada_interna(entry).configure(
                    validate='key',
                    validatecommand=(validar_numerico, '%P')
                )
            entry.pack(side='right')
            self.entries[key] = entry

        def obtener_valor(campo):
            valor = self.entries[campo].get().strip()
            return '' if valor == sugerencias.get(campo) else valor
        
        def guardar():
            obligatorios = ['dni', 'nombre', 'apellido', 'fecha_nac', 'sexo']
            for campo in obligatorios:
                if not obtener_valor(campo):
                    messagebox.showerror("Error", f"El campo '{campo}' es obligatorio.")
                    return

            fecha_nacimiento = obtener_valor('fecha_nac')
            try:
                datetime.strptime(fecha_nacimiento, '%Y-%m-%d')
            except ValueError:
                messagebox.showerror("Error", "La fecha debe tener el formato AAAA-MM-DD y ser válida.")
                return
            
            sexo = self.entries['sexo'].get().strip().upper()
            if sexo not in ['M', 'F']:
                messagebox.showerror("Error", "El sexo debe ser 'M' o 'F'.")
                return
            
            datos = {
                'dni': obtener_valor('dni'),
                'nombre': obtener_valor('nombre'),
                'apellido': obtener_valor('apellido'),
                'fecha_nac': fecha_nacimiento,
                'sexo': sexo,
                'telefono': obtener_valor('telefono'),
                'email': obtener_valor('email'),
                'domicilio': obtener_valor('domicilio'),
                'obra_social': self.entries['obra_social'].get().strip()
            }
            
            resultado, info = registrar_paciente(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Paciente registrado con éxito.\nHistoria Clínica N°: {info}")
                ventana.destroy()
                self.ver_pacientes(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        frame_botones = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_botones.pack(pady=12)
        
        BotonRedondeado(
            frame_botones,
            text="💾  Guardar",
            color='#4CAF50',
            command=guardar,
            width=140,
            height=46
        ).pack(side='left', padx=10)

        BotonRedondeado(
            frame_botones,
            text="✕  Cancelar",
            color='#F44336',
            command=ventana.destroy,
            width=140,
            height=46
        ).pack(side='left', padx=10)
    
    # ---------- BUSCAR PACIENTE ----------
    def abrir_busqueda(self):
        """Abre ventana para buscar paciente por DNI"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar Paciente")
        ventana.geometry("600x600")
        ventana.minsize(500, 520)
        ventana.configure(bg=COLOR_FONDO)
        ventana.grab_set()
        ventana.resizable(True, True)
        
        tk.Label(
            ventana,
            text="🔍 BUSCAR PACIENTE POR DNI",
            font=('Segoe UI', 16, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_TEXTO
        ).pack(pady=15)
        
        frame_busqueda = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_busqueda.pack(pady=10)
        
        tk.Label(
            frame_busqueda,
            text="DNI:",
            font=('Segoe UI', 11, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_TEXTO
        ).pack(side='left', padx=10)
        
        entry_dni = EntradaRedondeada(frame_busqueda, width=185, height=32)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()

        frame_sugerencias = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_sugerencias.pack(fill='x', padx=80, pady=(0, 2))

        lista_sugerencias = tk.Listbox(
            frame_sugerencias,
            height=4,
            font=('Segoe UI', 10),
            bg='white',
            fg=COLOR_TEXTO,
            selectbackground='#B8D8E8',
            selectforeground=COLOR_TEXTO,
            relief='flat',
            highlightthickness=1,
            highlightbackground='#C7D2DA'
        )
        lista_sugerencias.pack_forget()
        coincidencias = []
        
        frame_resultado = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_resultado.pack(pady=10, fill='both', expand=True, padx=20)
        
        label_datos = tk.Label(
            frame_resultado,
            text="Ingrese un DNI y presione Buscar",
            font=('Segoe UI', 10),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO,
            justify='left',
            anchor='nw',
            wraplength=520
        )
        label_datos.pack(pady=5)

        def ajustar_resultado(event=None):
            label_datos.config(wraplength=max(300, ventana.winfo_width() - 80))

        ventana.bind('<Configure>', ajustar_resultado)

        def mostrar_resultado(resultado):
            estado = "✅ Activo" if resultado['activo'] == 1 else "🚫 Inactivo"
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
                f"📅 Registro: {resultado['fecha_registro']}\n"
                f"📊 Estado: {estado}"
            )
            label_datos.config(text=texto, fg=COLOR_TEXTO)
        
        def actualizar_sugerencias(event=None):
            texto = entry_dni.get().strip()
            lista_sugerencias.delete(0, tk.END)
            coincidencias.clear()
            lista_sugerencias.pack_forget()
            if not texto:
                label_datos.config(text="Ingrese un DNI y presione Buscar", fg=COLOR_SECUNDARIO)
                return

            coincidencias.extend(buscar_pacientes_por_dni(texto))
            for paciente_id, dni, nombre, apellido, activo in coincidencias:
                estado = 'Activo' if activo == 1 else 'Inactivo'
                lista_sugerencias.insert(tk.END, f"{dni}  ·  {nombre} {apellido}  ({estado})")

            if coincidencias:
                lista_sugerencias.pack(fill='x')

            if not coincidencias:
                label_datos.config(text="No hay pacientes que coincidan con ese DNI.", fg='#B45309')

        def seleccionar_sugerencia(event=None):
            seleccion = lista_sugerencias.curselection()
            if not seleccion:
                return
            paciente = coincidencias[seleccion[0]]
            entry_dni.delete(0, tk.END)
            entry_dni.insert(0, paciente[1])
            lista_sugerencias.delete(0, tk.END)
            resultado = buscar_paciente(paciente[1])
            if resultado:
                mostrar_resultado(resultado)

        def buscar():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI para buscar.")
                return
            
            resultado = buscar_paciente(dni)
            if resultado:
                lista_sugerencias.delete(0, tk.END)
                mostrar_resultado(resultado)
            else:
                label_datos.config(text="❌ Paciente no encontrado.", fg='#f44336')
        
        entry_dni.bind('<KeyRelease>', actualizar_sugerencias)
        entry_dni.bind('<Return>', lambda e: buscar())
        lista_sugerencias.bind('<Double-1>', seleccionar_sugerencia)
        lista_sugerencias.bind('<Return>', seleccionar_sugerencia)
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=10)
        
        BotonRedondeado(
            frame_botones, "🔍  Buscar", buscar, '#2196F3', 125, 42
        ).pack(side='left', padx=10)

        BotonRedondeado(
            frame_botones, "✕  Cerrar", ventana.destroy, '#f44336', 125, 42
        ).pack(side='left', padx=10)
    
    # ---------- MODIFICAR PACIENTE ----------
    def abrir_modificacion(self):
        """Abre ventana para modificar un paciente (buscándolo por DNI)"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Modificar Paciente")
        ventana.geometry("600x560")
        ventana.minsize(520, 500)
        ventana.configure(bg=COLOR_FONDO)
        ventana.grab_set()
        ventana.resizable(True, True)
        
        tk.Label(
            ventana,
            text="✏️ MODIFICAR PACIENTE",
            font=('Segoe UI', 16, 'bold'),
            bg=COLOR_FONDO,
            fg='#FF9800'
        ).pack(pady=10)
        
        frame_buscar = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_buscar.pack(pady=10)
        
        tk.Label(
            frame_buscar,
            text="DNI del paciente:",
            font=('Segoe UI', 11, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_TEXTO
        ).pack(side='left', padx=10)
        
        entry_dni = EntradaRedondeada(frame_buscar, width=185, height=32)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()

        frame_sugerencias = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_sugerencias.pack(fill='x', padx=80, pady=(0, 2))
        lista_sugerencias = tk.Listbox(
            frame_sugerencias, height=4, font=('Segoe UI', 10), bg='white',
            fg=COLOR_TEXTO, selectbackground='#B8D8E8', selectforeground=COLOR_TEXTO,
            relief='flat', highlightthickness=1, highlightbackground='#C7D2DA'
        )
        coincidencias = []
        
        frame_campos = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_campos.pack(pady=8, padx=30, fill='x')
        
        label_nombre = tk.Label(
            frame_campos,
            text="Ingrese un DNI y presione Buscar",
            font=('Segoe UI', 11, 'bold'),
            bg=COLOR_FONDO,
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

        def cargar_paciente(resultado):
            nonlocal paciente_id_actual
            paciente_id_actual = resultado['id']
            label_nombre.config(
                text=f"Paciente: {resultado['nombre']} {resultado['apellido']} (HC: {resultado['id']})",
                fg='#003366'
            )
            entries_mod['telefono'].delete(0, tk.END)
            entries_mod['telefono'].insert(0, resultado['telefono'])
            entries_mod['email'].delete(0, tk.END)
            entries_mod['email'].insert(0, resultado['email'])
            entries_mod['domicilio'].delete(0, tk.END)
            entries_mod['domicilio'].insert(0, resultado['domicilio'])
            entries_mod['obra_social'].delete(0, tk.END)
            entries_mod['obra_social'].insert(0, resultado['obra_social'])
            frame_entries.pack(pady=10)
        
        def buscar_modificar():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI.")
                return
            
            resultado = buscar_paciente(dni)
            if resultado:
                cargar_paciente(resultado)
            else:
                messagebox.showerror("Error", "Paciente no encontrado.")

        def actualizar_sugerencias(event=None):
            texto = entry_dni.get().strip()
            lista_sugerencias.delete(0, tk.END)
            coincidencias.clear()
            lista_sugerencias.pack_forget()
            if not texto:
                return
            coincidencias.extend(buscar_pacientes_por_dni(texto))
            for _, dni, nombre, apellido, activo in coincidencias:
                estado = 'Activo' if activo == 1 else 'Inactivo'
                lista_sugerencias.insert(tk.END, f"{dni}  ·  {nombre} {apellido}  ({estado})")
            if coincidencias:
                lista_sugerencias.pack(fill='x')

        def seleccionar_sugerencia(event=None):
            seleccion = lista_sugerencias.curselection()
            if not seleccion:
                return
            dni = coincidencias[seleccion[0]][1]
            entry_dni.delete(0, tk.END)
            entry_dni.insert(0, dni)
            lista_sugerencias.pack_forget()
            resultado = buscar_paciente(dni)
            if resultado:
                cargar_paciente(resultado)
        
        entry_dni.bind('<KeyRelease>', actualizar_sugerencias)
        entry_dni.bind('<Return>', lambda e: buscar_modificar())
        lista_sugerencias.bind('<Double-1>', seleccionar_sugerencia)
        lista_sugerencias.bind('<Return>', seleccionar_sugerencia)
        
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
                self.ver_pacientes(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")
        
        frame_botones = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_botones.pack(pady=15)
        
        BotonRedondeado(
            frame_botones, "💾  Guardar Cambios", guardar_modificacion, '#FF9800', 175, 42
        ).pack(side='left', padx=10)

        BotonRedondeado(
            frame_botones, "✕  Cancelar", ventana.destroy, '#f44336', 130, 42
        ).pack(side='left', padx=10)
    
    def abrir_modificacion_con_id(self, paciente_id):
        """Abre modificación directa con el ID del paciente"""
        paciente = buscar_paciente_por_id(paciente_id)
        if not paciente:
            messagebox.showerror("Error", "Paciente no encontrado.")
            return
        
        # Reutiliza la ventana de modificación pero con el DNI precargado
        # (versión simplificada)
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Modificar - {paciente['nombre']} {paciente['apellido']}")
        ventana.geometry("500x400")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text=f"✏️ MODIFICAR PACIENTE",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=10)
        
        tk.Label(
            ventana,
            text=f"{paciente['nombre']} {paciente['apellido']} (HC: {paciente['id']})",
            font=('Arial', 11, 'bold'),
            bg='#f0f0f0',
            fg='#003366'
        ).pack(pady=5)
        
        frame_campos = tk.Frame(ventana, bg='#f0f0f0')
        frame_campos.pack(padx=30, pady=10)
        
        campos_mod = [
            ('Teléfono', 'telefono', paciente['telefono']),
            ('Email', 'email', paciente['email']),
            ('Domicilio', 'domicilio', paciente['domicilio']),
            ('Obra Social', 'obra_social', paciente['obra_social'])
        ]
        
        entries_mod = {}
        for label_text, key, valor in campos_mod:
            frame = tk.Frame(frame_campos, bg='#f0f0f0')
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
            entry.insert(0, valor)
            entry.pack(side='right')
            entries_mod[key] = entry
        
        def guardar():
            datos = {
                'telefono': entries_mod['telefono'].get().strip(),
                'email': entries_mod['email'].get().strip(),
                'domicilio': entries_mod['domicilio'].get().strip(),
                'obra_social': entries_mod['obra_social'].get().strip()
            }
            
            resultado, mensaje = modificar_paciente(paciente_id, datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ {mensaje}")
                ventana.destroy()
                self.ver_pacientes(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=15)
        
        BotonRedondeado(
            frame_botones, "💾  Guardar Cambios", guardar, '#FF9800', 175, 42
        ).pack(side='left', padx=10)

        BotonRedondeado(
            frame_botones, "✕  Cancelar", ventana.destroy, '#f44336', 130, 42
        ).pack(side='left', padx=10)
    
    # ---------- BAJA LÓGICA DE PACIENTE ----------
    def dar_baja_paciente(self):
        """Abre ventana para dar de baja un paciente"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Dar de Baja Paciente")
        ventana.geometry("600x500")
        ventana.minsize(520, 430)
        ventana.configure(bg=COLOR_FONDO)
        ventana.grab_set()
        ventana.resizable(True, True)
        
        tk.Label(
            ventana,
            text="🗑️ DAR DE BAJA PACIENTE",
            font=('Segoe UI', 16, 'bold'),
            bg=COLOR_FONDO,
            fg='#f44336'
        ).pack(pady=10)
        
        tk.Label(
            ventana,
              text="La baja es lógica: los datos clínicos se conservan para auditoría.",
              font=('Segoe UI', 10),
              bg=COLOR_FONDO,
              fg=COLOR_SECUNDARIO,
            justify='center'
        ).pack(pady=10)
        
        frame = tk.Frame(ventana, bg=COLOR_FONDO)
        frame.pack(pady=12)
        
        tk.Label(
            frame,
            text="DNI del paciente:",
            font=('Segoe UI', 11, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_TEXTO
        ).pack(side='left', padx=10)
        
        entry_dni = EntradaRedondeada(frame, width=185, height=32)
        entry_dni.pack(side='left', padx=10)
        entry_dni.focus()

        frame_sugerencias = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_sugerencias.pack(fill='x', padx=80, pady=(0, 2))
        lista_sugerencias = tk.Listbox(
            frame_sugerencias, height=4, font=('Segoe UI', 10), bg='white',
            fg=COLOR_TEXTO, selectbackground='#B8D8E8', selectforeground=COLOR_TEXTO,
            relief='flat', highlightthickness=1, highlightbackground='#C7D2DA'
        )
        coincidencias = []
        
        def confirmar_baja():
            dni = entry_dni.get().strip()
            if not dni:
                messagebox.showerror("Error", "Ingrese un DNI.")
                return
            
            paciente = buscar_paciente(dni)
            if not paciente:
                messagebox.showerror("Error", "Paciente no encontrado.")
                return
            
            if paciente['activo'] == 0:
                messagebox.showwarning("Aviso", "El paciente ya está dado de baja.")
                return
            
            # Contar registros asociados
            total_signos = contar_signos_vitales_paciente(paciente['id'])
            total_prescripciones = contar_prescripciones_paciente(paciente['id'])
            
            if messagebox.askyesno(
                "⚠️ Confirmar Baja",
                f"¿Está seguro de dar de baja a {paciente['nombre']} {paciente['apellido']} (HC: {paciente['id']})?\n\n"
                f"📊 Registros asociados:\n"
                f"   ❤️ Signos vitales: {total_signos}\n"
                f"   💊 Prescripciones: {total_prescripciones}\n\n"
                f"⚠️ Signos vitales y Prescripciones debe ser desactivados manualmente\n"
                f"✅ Los datos del paciente SE CONSERVAN (baja lógica)\n"
                f"❌ El paciente no aparecerá en listados activos"
            ):
                resultado, mensaje = dar_baja_paciente(paciente['id'])
                if resultado:
                    messagebox.showinfo("Éxito", f"✅ {mensaje}")
                    ventana.destroy()
                    self.ver_pacientes(activos=True)
                else:
                    messagebox.showerror("Error", f"❌ {mensaje}")
        
        def actualizar_sugerencias(event=None):
            texto = entry_dni.get().strip()
            lista_sugerencias.delete(0, tk.END)
            coincidencias.clear()
            lista_sugerencias.pack_forget()
            if not texto:
                return
            coincidencias.extend(buscar_pacientes_por_dni(texto))
            for _, dni, nombre, apellido, activo in coincidencias:
                estado = 'Activo' if activo == 1 else 'Inactivo'
                lista_sugerencias.insert(tk.END, f"{dni}  ·  {nombre} {apellido}  ({estado})")
            if coincidencias:
                lista_sugerencias.pack(fill='x')

        def seleccionar_sugerencia(event=None):
            seleccion = lista_sugerencias.curselection()
            if not seleccion:
                return
            entry_dni.delete(0, tk.END)
            entry_dni.insert(0, coincidencias[seleccion[0]][1])
            lista_sugerencias.pack_forget()

        entry_dni.bind('<KeyRelease>', actualizar_sugerencias)
        entry_dni.bind('<Return>', lambda e: confirmar_baja())
        lista_sugerencias.bind('<Double-1>', seleccionar_sugerencia)
        lista_sugerencias.bind('<Return>', seleccionar_sugerencia)
        
        BotonRedondeado(
            ventana, "🗑️  Confirmar Baja", confirmar_baja, '#f44336', 175, 42
        ).pack(pady=10)
    
    def baja_con_id(self, paciente_id):
        """Baja directa con ID"""
        paciente = buscar_paciente_por_id(paciente_id)
        if not paciente:
            return
        
        total_signos = contar_signos_vitales_paciente(paciente_id)
        total_prescripciones = contar_prescripciones_paciente(paciente_id)
        
        if messagebox.askyesno(
            "⚠️ Confirmar Baja",
            f"¿Está seguro de dar de baja a {paciente['nombre']} {paciente['apellido']}?\n\n"
            f"📊 Registros asociados:\n"
            f"   ❤️ Signos vitales: {total_signos}\n"
            f"   💊 Prescripciones: {total_prescripciones}\n\n"
            f"⚠️ Signos vitales y Prescripciones debe ser desactivados manualmente\n"
            f"✅ Los datos del paciente SE CONSERVAN (baja lógica)\n"
        ):
            resultado, mensaje = dar_baja_paciente(paciente_id)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ {mensaje}")
                self.ver_pacientes(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")
    
    def reactivar_con_id(self, paciente_id):
        """Reactiva un paciente dado de baja"""
        if messagebox.askyesno(
            "♻️ Reactivar Paciente",
            "¿Está seguro de reactivar este paciente?"
        ):
            resultado, mensaje = reactivar_paciente(paciente_id)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ {mensaje}")
                self.ver_pacientes(activos=True)
            else:
                messagebox.showerror("Error", f"❌ {mensaje}")


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = AppPacientes(root)
    root.mainloop()
