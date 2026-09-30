# ================================================================
# Tablas_maestras.pyw
# MÓDULO DE GESTIÓN DE TABLAS MAESTRAS
# SPRINT 3 - ADMINISTRACIÓN DE DATOS REFERENCIALES
# ================================================================
#
# FUNCIONALIDADES PARA CADA TABLA:
#   ✅ Listar registros
#   ✅ Registrar nuevo (CREATE)
#   ✅ Buscar por código o término (READ)
#   ✅ Modificar (UPDATE)
#   ✅ Activar/Desactivar (DELETE lógico)
#   ✅ Interfaz gráfica con Tkinter
#
# TABLAS GESTIONADAS:
#   1. Especialidades - Usada por Profesionales
#   2. SnomedCT - Terminología clínica (para HCE)
#   3. Farmacos - Medicamentos (para futura farmacia)
# ================================================================

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from ui_helpers import BotonRedondeado, EntradaCuadrada

tk.Button = BotonRedondeado
tk.Entry = EntradaCuadrada

COLOR_FONDO = '#F4F7FB'
COLOR_TEXTO = '#183B56'
COLOR_SECUNDARIO = '#5C7184'

# ================================================================
# CAPA DE ACCESO A DATOS
# ================================================================

def conectar_bd():
    """Establece conexión con la base de datos Salud.db"""
    ruta_bd = Path(__file__).resolve().parent / 'DB' / 'Salud.db'
    return sqlite3.connect(ruta_bd)


# -------------------- FUNCIONES GENÉRICAS --------------------

def tabla_existe(nombre_tabla):
    """Verifica si una tabla existe en la base de datos"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """, (nombre_tabla,))
        existe = cursor.fetchone() is not None
        conexion.close()
        return existe
    except Exception as e:
        return False


def crear_tablas_maestras():
    """Crea las tablas maestras si no existen"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        # Tabla Especialidades
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Especialidades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                activo INTEGER DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla SnomedCT
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SnomedCT (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                termino TEXT NOT NULL,
                descripcion TEXT,
                categoria TEXT,
                activo INTEGER DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla Farmacos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Farmacos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                principio_activo TEXT,
                presentacion TEXT,
                concentracion TEXT,
                via_administracion TEXT,
                activo INTEGER DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ObrasSociales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT UNIQUE NOT NULL,
                telefono TEXT,
                email TEXT,
                activo INTEGER DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conexion.commit()
        conexion.close()
        return True
    except Exception as e:
        print(f"Error al crear tablas maestras: {e}")
        return False


# -------------------- ESPECIALIDADES --------------------

def listar_especialidades(activos=True):
    """Lista todas las especialidades"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        if activos:
            cursor.execute("""
                SELECT id, codigo, nombre, descripcion, activo 
                FROM Especialidades 
                WHERE activo = 1
                ORDER BY nombre
            """)
        else:
            cursor.execute("""
                SELECT id, codigo, nombre, descripcion, activo 
                FROM Especialidades 
                ORDER BY nombre
            """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


def registrar_especialidad(datos):
    """Registra una nueva especialidad"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO Especialidades (codigo, nombre, descripcion, activo)
            VALUES (?, ?, ?, ?)
        """, (datos['codigo'], datos['nombre'], datos['descripcion'], 1))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        return True, nuevo_id
    except sqlite3.IntegrityError:
        return False, "❌ Código duplicado. Ya existe una especialidad con ese código."
    except Exception as e:
        return False, f"❌ Error: {e}"


def modificar_especialidad(especialidad_id, datos):
    """Modifica una especialidad"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            UPDATE Especialidades 
            SET codigo = ?, nombre = ?, descripcion = ?
            WHERE id = ?
        """, (datos['codigo'], datos['nombre'], datos['descripcion'], especialidad_id))
        conexion.commit()
        conexion.close()
        return True, "✅ Especialidad modificada correctamente."
    except sqlite3.IntegrityError:
        return False, "❌ Código duplicado."
    except Exception as e:
        return False, f"❌ Error: {e}"


def eliminar_especialidad(especialidad_id):
    """Elimina lógicamente una especialidad (activo = 0)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("UPDATE Especialidades SET activo = 0 WHERE id = ?", (especialidad_id,))
        conexion.commit()
        conexion.close()
        return True, "✅ Especialidad desactivada correctamente."
    except Exception as e:
        return False, f"❌ Error: {e}"


def obtener_especialidades_selector():
    """Obtiene lista de especialidades para selector (combobox)"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("SELECT id, nombre FROM Especialidades WHERE activo = 1 ORDER BY nombre")
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


# -------------------- SNOMED CT --------------------

def listar_snomed(categoria=None):
    """Lista términos SNOMED CT"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        if categoria:
            cursor.execute("""
                SELECT id, codigo, termino, descripcion, categoria, activo 
                FROM SnomedCT 
                WHERE categoria = ? AND activo = 1
                ORDER BY termino
            """, (categoria,))
        else:
            cursor.execute("""
                SELECT id, codigo, termino, descripcion, categoria, activo 
                FROM SnomedCT 
                WHERE activo = 1
                ORDER BY termino
            """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


def registrar_snomed(datos):
    """Registra un término SNOMED CT"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO SnomedCT (codigo, termino, descripcion, categoria, activo)
            VALUES (?, ?, ?, ?, ?)
        """, (datos['codigo'], datos['termino'], datos['descripcion'], 
              datos['categoria'], 1))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        return True, nuevo_id
    except sqlite3.IntegrityError:
        return False, "❌ Código duplicado."
    except Exception as e:
        return False, f"❌ Error: {e}"


def buscar_snomed_por_termino(termino):
    """Busca términos SNOMED CT por texto"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, codigo, termino, descripcion, categoria 
            FROM SnomedCT 
            WHERE termino LIKE ? AND activo = 1
            ORDER BY termino
            LIMIT 20
        """, (f'%{termino}%',))
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


# -------------------- FÁRMACOS --------------------

def listar_farmacos():
    """Lista todos los fármacos activos"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id, codigo, nombre, principio_activo, presentacion, 
                   concentracion, via_administracion, activo 
            FROM Farmacos 
            WHERE activo = 1
            ORDER BY nombre
        """)
        resultados = cursor.fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


def registrar_farmaco(datos):
    """Registra un nuevo fármaco"""
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO Farmacos 
            (codigo, nombre, principio_activo, presentacion, concentracion, via_administracion, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datos['codigo'], datos['nombre'], datos['principio_activo'],
            datos['presentacion'], datos['concentracion'], datos['via_administracion'], 1
        ))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        return True, nuevo_id
    except sqlite3.IntegrityError:
        return False, "❌ Código duplicado."
    except Exception as e:
        return False, f"❌ Error: {e}"


def listar_obras_sociales():
    """Lista obras sociales activas e inactivas."""
    try:
        conexion = conectar_bd()
        resultados = conexion.execute("""
            SELECT id, codigo, nombre, telefono, email, activo
            FROM ObrasSociales ORDER BY nombre
        """).fetchall()
        conexion.close()
        return resultados
    except Exception as e:
        return []


def registrar_obra_social(datos):
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO ObrasSociales (codigo, nombre, telefono, email, activo)
            VALUES (?, ?, ?, ?, 1)
        """, (datos['codigo'], datos['nombre'], datos['telefono'], datos['email']))
        conexion.commit()
        nuevo_id = cursor.lastrowid
        conexion.close()
        return True, nuevo_id
    except sqlite3.IntegrityError:
        return False, "❌ El código o nombre ya existe."
    except Exception as e:
        return False, f"❌ Error: {e}"


def modificar_obra_social(obra_id, datos):
    try:
        conexion = conectar_bd()
        conexion.execute("""
            UPDATE ObrasSociales SET codigo=?, nombre=?, telefono=?, email=? WHERE id=?
        """, (datos['codigo'], datos['nombre'], datos['telefono'], datos['email'], obra_id))
        conexion.commit()
        conexion.close()
        return True, "✅ Obra social modificada correctamente."
    except sqlite3.IntegrityError:
        return False, "❌ El código o nombre ya existe."
    except Exception as e:
        return False, f"❌ Error: {e}"


def desactivar_obra_social(obra_id):
    try:
        conexion = conectar_bd()
        conexion.execute("UPDATE ObrasSociales SET activo=0 WHERE id=?", (obra_id,))
        conexion.commit()
        conexion.close()
        return True, "✅ Obra social desactivada correctamente."
    except Exception as e:
        return False, f"❌ Error: {e}"


# ================================================================
# CAPA DE PRESENTACIÓN - APPLET GENERAL PARA TABLAS MAESTRAS
# ================================================================

class AppTablasMaestras:
    """Aplicación principal para gestionar tablas maestras"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Tablas Maestras")
        self.root.geometry("900x650")
        self.root.minsize(700, 520)
        self.root.resizable(True, True)
        self.root.configure(bg=COLOR_FONDO)

        estilo = ttk.Style(self.root)
        estilo.theme_use('clam')
        estilo.configure('Masters.Treeview', background='#FFFFFF', fieldbackground='#FFFFFF',
                 foreground=COLOR_TEXTO, rowheight=32, font=('Segoe UI', 10))
        estilo.configure('Masters.Treeview.Heading', background='#1B4965', foreground='white',
                 font=('Segoe UI', 10, 'bold'), padding=(8, 8))
        estilo.map('Masters.Treeview', background=[('selected', '#B8D8E8')],
               foreground=[('selected', COLOR_TEXTO)])
        
        # Verificar/Crear tablas
        crear_tablas_maestras()
        
        # ---------- FRAME PRINCIPAL ----------
        self.frame_principal = tk.Frame(self.root, bg=COLOR_FONDO)
        self.frame_principal.pack(fill='both', expand=True, padx=20, pady=20)
        
        # ---------- TÍTULO ----------
        titulo = tk.Label(
            self.frame_principal,
            text="📚 TABLAS MAESTRAS",
            font=('Segoe UI', 18, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_TEXTO
        )
        titulo.pack(pady=10)
        
        subtitulo = tk.Label(
            self.frame_principal,
            text="Gestión de Especialidades, SNOMED CT, Fármacos y Obras Sociales",
            font=('Segoe UI', 11),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO
        )
        subtitulo.pack(pady=5)
        
        tk.Frame(self.frame_principal, height=1, bg='#D8E2EA').pack(fill='x', pady=10)
        
        # ---------- BOTONES DE SELECCIÓN DE TABLA ----------
        frame_tablas = tk.Frame(self.frame_principal, bg=COLOR_FONDO)
        frame_tablas.pack(pady=10)
        
        estilo_boton = {
            'font': ('Segoe UI', 11, 'bold'),
            'padx': 20,
            'pady': 8,
            'relief': 'flat',
            'bd': 0,
            'cursor': 'hand2'
        }
        
        self.btn_especialidades = tk.Button(
            frame_tablas,
            text="🏥 Especialidades",
            bg='#4CAF50',
            fg='white',
            command=self.mostrar_especialidades,
            **estilo_boton
        )
        self.btn_especialidades.pack(side='left', padx=5)
        
        self.btn_snomed = tk.Button(
            frame_tablas,
            text="📋 SNOMED CT",
            bg='#2196F3',
            fg='white',
            command=self.mostrar_snomed,
            **estilo_boton
        )
        self.btn_snomed.pack(side='left', padx=5)
        
        self.btn_farmacos = tk.Button(
            frame_tablas,
            text="💊 Fármacos",
            bg='#FF9800',
            fg='white',
            command=self.mostrar_farmacos,
            **estilo_boton
        )
        self.btn_farmacos.pack(side='left', padx=5)

        self.btn_obras_sociales = tk.Button(
            frame_tablas,
            text="🏢 Obras Sociales",
            bg='#7B1FA2',
            fg='white',
            command=self.mostrar_obras_sociales,
            **estilo_boton
        )
        self.btn_obras_sociales.pack(side='left', padx=5)
        
        tk.Frame(self.frame_principal, height=1, bg='#D8E2EA').pack(fill='x', pady=10)
        
        # ---------- ÁREA DE CONTENIDO ----------
        self.frame_contenido = tk.Frame(self.frame_principal, bg=COLOR_FONDO)
        self.frame_contenido.pack(fill='both', expand=True, pady=10)
        
        # Mensaje inicial
        self.label_mensaje = tk.Label(
            self.frame_contenido,
            text="Seleccione una tabla para comenzar la gestión",
            font=('Segoe UI', 14),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO
        )
        self.label_mensaje.pack(expand=True)
        
        # ---------- ESTADO ----------
        self.label_estado = tk.Label(
            self.frame_principal,
            text="✅ Sistema listo",
            font=('Segoe UI', 9),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO
        )
        self.label_estado.pack(side='bottom', pady=5)
    
    # ============================================================
    # MÉTODOS PARA MOSTRAR TABLAS
    # ============================================================
    
    def limpiar_contenido(self):
        """Limpia el área de contenido"""
        for widget in self.frame_contenido.winfo_children():
            widget.destroy()

    def mostrar_obras_sociales(self):
        """Muestra el CRUD de obras sociales."""
        self.limpiar_contenido()
        tk.Label(self.frame_contenido, text='🏢 GESTIÓN DE OBRAS SOCIALES',
                 font=('Segoe UI', 16, 'bold'), bg=COLOR_FONDO, fg='#7B1FA2').pack(pady=5)

        frame_acciones = tk.Frame(self.frame_contenido, bg=COLOR_FONDO)
        frame_acciones.pack(pady=5)
        tk.Button(frame_acciones, text='➕ Agregar Obra Social', bg='#7B1FA2', fg='white',
                  command=self.agregar_obra_social, padx=15, pady=6).pack(side='left', padx=5)
        tk.Button(frame_acciones, text='🔄 Actualizar', bg='#2196F3', fg='white',
                  command=self.mostrar_obras_sociales, padx=15, pady=6).pack(side='left', padx=5)

        frame_tabla = tk.Frame(self.frame_contenido, bg=COLOR_FONDO)
        frame_tabla.pack(fill='both', expand=True, pady=10)
        tree = ttk.Treeview(frame_tabla, columns=('ID', 'Código', 'Nombre', 'Teléfono', 'Email', 'Estado'),
                            show='headings', style='Masters.Treeview')
        for columna, ancho in (('ID', 50), ('Código', 100), ('Nombre', 220),
                               ('Teléfono', 140), ('Email', 220), ('Estado', 100)):
            tree.heading(columna, text=columna)
            tree.column(columna, width=ancho, anchor='w')
        tree.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)

        for indice, obra in enumerate(listar_obras_sociales()):
            tree.insert('', 'end', values=(obra[0], obra[1], obra[2], obra[3] or '',
                                          obra[4] or '', 'Activo' if obra[5] else 'Inactivo'),
                         tags=('par' if indice % 2 == 0 else 'impar',))
        tree.bind('<Double-1>', lambda event: self.editar_obra_social(tree))
        tree.bind('<Button-3>', lambda event: self.menu_obra_social(tree, event))

    def menu_obra_social(self, tree, event):
        seleccion = tree.identify_row(event.y)
        if not seleccion:
            return
        tree.selection_set(seleccion)
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label='✏️ Editar', command=lambda: self.editar_obra_social(tree))
        menu.add_command(label='🚫 Desactivar', command=lambda: self.desactivar_obra_social(tree))
        menu.post(event.x_root, event.y_root)

    def desactivar_obra_social(self, tree):
        seleccion = tree.selection()
        if not seleccion:
            return
        obra_id = tree.item(seleccion[0])['values'][0]
        if messagebox.askyesno('Confirmar', '¿Desactivar esta obra social?'):
            resultado, mensaje = desactivar_obra_social(obra_id)
            if resultado:
                self.mostrar_obras_sociales()
            else:
                messagebox.showerror('Error', mensaje)

    def agregar_obra_social(self):
        self._formulario_obra_social()

    def editar_obra_social(self, tree):
        seleccion = tree.selection()
        if not seleccion:
            return
        valores = tree.item(seleccion[0])['values']
        self._formulario_obra_social(valores)

    def _formulario_obra_social(self, valores=None):
        editar = valores is not None
        ventana = tk.Toplevel(self.root)
        ventana.title('Editar Obra Social' if editar else 'Agregar Obra Social')
        ventana.geometry('560x360')
        ventana.minsize(500, 320)
        ventana.configure(bg=COLOR_FONDO)
        ventana.grab_set()

        tk.Label(ventana, text=('✏️ EDITAR OBRA SOCIAL' if editar else '➕ AGREGAR OBRA SOCIAL'),
                 font=('Segoe UI', 16, 'bold'), bg=COLOR_FONDO, fg='#7B1FA2').pack(pady=(10, 5))
        campos = [('Código *', 'codigo'), ('Nombre *', 'nombre'), ('Teléfono', 'telefono'), ('Email', 'email')]
        frame = tk.Frame(ventana, bg=COLOR_FONDO)
        frame.pack(padx=35, pady=8, fill='x')
        entradas = {}
        for indice, (etiqueta, clave) in enumerate(campos):
            tk.Label(frame, text=etiqueta, width=16, anchor='w', bg=COLOR_FONDO,
                     fg=COLOR_TEXTO, font=('Segoe UI', 10, 'bold')).grid(row=indice, column=0, pady=5, sticky='w')
            entrada = tk.Entry(frame, width=32, font=('Segoe UI', 10))
            if editar:
                entrada.insert(0, valores[{'codigo': 1, 'nombre': 2, 'telefono': 3, 'email': 4}[clave]] or '')
            entrada.grid(row=indice, column=1, pady=5, sticky='ew')
            entradas[clave] = entrada
        frame.columnconfigure(1, weight=1)

        def guardar():
            datos = {clave: entradas[clave].get().strip() for _, clave in campos}
            if not datos['codigo'] or not datos['nombre']:
                messagebox.showerror('Error', 'Código y nombre son obligatorios.')
                return
            resultado = modificar_obra_social(valores[0], datos) if editar else registrar_obra_social(datos)
            if resultado[0]:
                ventana.destroy()
                self.mostrar_obras_sociales()
            else:
                messagebox.showerror('Error', resultado[1])

        frame_botones = tk.Frame(ventana, bg=COLOR_FONDO)
        frame_botones.pack(pady=12)
        tk.Button(frame_botones, text='💾 Guardar', bg='#7B1FA2', fg='white', command=guardar,
                  padx=20, pady=7).pack(side='left', padx=8)
        tk.Button(frame_botones, text='✕ Cancelar', bg='#F44336', fg='white', command=ventana.destroy,
                  padx=20, pady=7).pack(side='left', padx=8)
    
    def mostrar_especialidades(self):
        """Muestra la gestión de especialidades"""
        self.limpiar_contenido()
        
        # Título
        tk.Label(
            self.frame_contenido,
            text="🏥 GESTIÓN DE ESPECIALIDADES",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#4CAF50'
        ).pack(pady=5)
        
        # Botón Agregar
        frame_botones = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_botones.pack(pady=5)
        
        tk.Button(
            frame_botones,
            text="➕ Agregar Especialidad",
            bg='#4CAF50',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.agregar_especialidad
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="🔄 Actualizar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.mostrar_especialidades
        ).pack(side='left', padx=5)
        
        # Tabla
        frame_tabla = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Código', 'Nombre', 'Descripción', 'Estado'),
            show='headings',
            height=15
        )
        tree.configure(style='Masters.Treeview')
        tree.tag_configure('par', background='#F2F7FA')
        tree.tag_configure('impar', background='#FFFFFF')
        tree.heading('ID', text='ID')
        tree.heading('Código', text='Código')
        tree.heading('Nombre', text='Nombre')
        tree.heading('Descripción', text='Descripción')
        tree.heading('Estado', text='Estado')
        tree.column('ID', width=40, anchor='center')
        tree.column('Código', width=80, anchor='center')
        tree.column('Nombre', width=200)
        tree.column('Descripción', width=300)
        tree.column('Estado', width=80, anchor='center')
        tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Cargar datos
        especialidades = listar_especialidades(activos=False)
        for indice, esp in enumerate(especialidades):
            estado = "Activo" if esp[4] == 1 else "Inactivo"
            etiqueta = 'par' if indice % 2 == 0 else 'impar'
            tree.insert('', 'end', values=(esp[0], esp[1], esp[2], esp[3], estado), tags=(etiqueta,))
        
        # Eventos
        tree.bind('<Double-1>', lambda e: self.editar_especialidad(tree))
        tree.bind('<Button-3>', lambda e: self.menu_contextual_especialidad(tree, e))
    
    # ---------- AGREGAR ESPECIALIDAD ----------
    def agregar_especialidad(self):
        """Abre ventana para agregar una especialidad"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Agregar Especialidad")
        ventana.geometry("560x340")
        ventana.minsize(500, 300)
        ventana.configure(bg=COLOR_FONDO)
        ventana.grab_set()
        ventana.resizable(True, True)
        
        tk.Label(
            ventana,
            text="➕ AGREGAR ESPECIALIDAD",
            font=('Segoe UI', 16, 'bold'),
            bg=COLOR_FONDO,
            fg='#4CAF50'
        ).pack(pady=10)
        
        frame = tk.Frame(ventana, bg=COLOR_FONDO)
        frame.pack(padx=30, pady=10)
        
        campos = [
            ('Código *', 'codigo'),
            ('Nombre *', 'nombre'),
            ('Descripción', 'descripcion')
        ]
        
        entries = {}
        for label_text, key in campos:
            f = tk.Frame(frame, bg=COLOR_FONDO)
            f.pack(fill='x', pady=3)
            tk.Label(f, text=label_text, width=15, anchor='w', bg=COLOR_FONDO, fg=COLOR_TEXTO, font=('Segoe UI', 10, 'bold')).pack(side='left')
            entry = tk.Entry(f, width=30, font=('Arial', 10))
            entry.pack(side='right')
            entries[key] = entry
        
        def guardar():
            if not entries['codigo'].get().strip() or not entries['nombre'].get().strip():
                messagebox.showerror("Error", "Código y Nombre son obligatorios.")
                return
            
            datos = {
                'codigo': entries['codigo'].get().strip(),
                'nombre': entries['nombre'].get().strip(),
                'descripcion': entries['descripcion'].get().strip()
            }
            
            resultado, info = registrar_especialidad(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Especialidad agregada con éxito.\nID: {info}")
                ventana.destroy()
                self.mostrar_especialidades()
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        tk.Button(frame_botones, text="💾 Guardar", bg='#4CAF50', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=ventana.destroy).pack(side='left', padx=10)
    
    # ---------- EDITAR ESPECIALIDAD ----------
    def editar_especialidad(self, tree):
        """Abre ventana para editar una especialidad"""
        seleccion = tree.selection()
        if not seleccion:
            return
        
        item = tree.item(seleccion[0])
        valores = item['values']
        if not valores:
            return
        
        especialidad_id = valores[0]
        
        ventana = tk.Toplevel(self.root)
        ventana.title("Editar Especialidad")
        ventana.geometry("550x300")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text="✏️ EDITAR ESPECIALIDAD",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=10)
        
        frame = tk.Frame(ventana, bg='#f0f0f0')
        frame.pack(padx=30, pady=10)
        
        campos = [
            ('Código *', 'codigo', valores[1]),
            ('Nombre *', 'nombre', valores[2]),
            ('Descripción', 'descripcion', valores[3] or '')
        ]
        
        entries = {}
        for label_text, key, default in campos:
            f = tk.Frame(frame, bg='#f0f0f0')
            f.pack(fill='x', pady=3)
            tk.Label(f, text=label_text, width=15, anchor='w', bg='#f0f0f0', font=('Arial', 10)).pack(side='left')
            entry = tk.Entry(f, width=30, font=('Arial', 10))
            entry.insert(0, default)
            entry.pack(side='right')
            entries[key] = entry
        
        def guardar():
            if not entries['codigo'].get().strip() or not entries['nombre'].get().strip():
                messagebox.showerror("Error", "Código y Nombre son obligatorios.")
                return
            
            datos = {
                'codigo': entries['codigo'].get().strip(),
                'nombre': entries['nombre'].get().strip(),
                'descripcion': entries['descripcion'].get().strip()
            }
            
            resultado, mensaje = modificar_especialidad(especialidad_id, datos)
            if resultado:
                messagebox.showinfo("Éxito", mensaje)
                ventana.destroy()
                self.mostrar_especialidades()
            else:
                messagebox.showerror("Error", mensaje)
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        tk.Button(frame_botones, text="💾 Guardar Cambios", bg='#FF9800', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="🗑️ Desactivar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, 
                 command=lambda: self.desactivar_especialidad(especialidad_id, ventana)).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#9E9E9E', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=ventana.destroy).pack(side='left', padx=10)
    
    def desactivar_especialidad(self, especialidad_id, ventana):
        """Desactiva una especialidad"""
        if messagebox.askyesno("Confirmar", "¿Está seguro de desactivar esta especialidad?"):
            resultado, mensaje = eliminar_especialidad(especialidad_id)
            if resultado:
                messagebox.showinfo("Éxito", mensaje)
                ventana.destroy()
                self.mostrar_especialidades()
            else:
                messagebox.showerror("Error", mensaje)
    
    # ---------- MENÚ CONTEXTUAL ----------
    def menu_contextual_especialidad(self, tree, event):
        """Muestra menú contextual para especialidades"""
        seleccion = tree.selection()
        if seleccion:
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="✏️ Editar", command=lambda: self.editar_especialidad(tree))
            menu.add_command(label="🗑️ Desactivar", 
                           command=lambda: self.desactivar_especialidad(int(tree.item(seleccion[0])['values'][0]), None))
            menu.post(event.x_root, event.y_root)
    
    # ============================================================
    # SNOMED CT (Simplificado - Mismo patrón que Especialidades)
    # ============================================================
    
    def mostrar_snomed(self):
        """Muestra la gestión de SNOMED CT"""
        self.limpiar_contenido()
        
        tk.Label(
            self.frame_contenido,
            text="📋 GESTIÓN DE SNOMED CT",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#2196F3'
        ).pack(pady=5)
        
        frame_botones = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_botones.pack(pady=5)
        
        tk.Button(
            frame_botones,
            text="➕ Agregar Término",
            bg='#2196F3',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.agregar_snomed
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="🔍 Buscar",
            bg='#4CAF50',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.buscar_snomed
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="🔄 Actualizar",
            bg='#FF9800',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.mostrar_snomed
        ).pack(side='left', padx=5)
        
        frame_tabla = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Código', 'Término', 'Categoría', 'Descripción'),
            show='headings',
            height=15
        )
        tree.configure(style='Masters.Treeview')
        tree.tag_configure('par', background='#F2F7FA')
        tree.tag_configure('impar', background='#FFFFFF')
        tree.heading('ID', text='ID')
        tree.heading('Código', text='Código')
        tree.heading('Término', text='Término')
        tree.heading('Categoría', text='Categoría')
        tree.heading('Descripción', text='Descripción')
        tree.column('ID', width=40, anchor='center')
        tree.column('Código', width=100, anchor='center')
        tree.column('Término', width=200)
        tree.column('Categoría', width=120)
        tree.column('Descripción', width=300)
        tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        
        snomed = listar_snomed()
        for s in snomed:
            tree.insert('', 'end', values=(s[0], s[1], s[2], s[4], s[3]))
    
    def agregar_snomed(self):
        """Abre ventana para agregar un término SNOMED CT"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Agregar Término SNOMED CT")
        ventana.geometry("520x390")
        ventana.minsize(460, 340)
        ventana.configure(bg=COLOR_FONDO)
        ventana.grab_set()
        ventana.resizable(True, True)
        
        tk.Label(
            ventana,
            text="➕ AGREGAR TÉRMINO SNOMED CT",
            font=('Segoe UI', 16, 'bold'),
            bg=COLOR_FONDO,
            fg='#2196F3'
        ).pack(pady=10)
        
        frame = tk.Frame(ventana, bg=COLOR_FONDO)
        frame.pack(padx=30, pady=10)
        
        campos = [
            ('Código *', 'codigo'),
            ('Término *', 'termino'),
            ('Categoría *', 'categoria'),
            ('Descripción', 'descripcion')
        ]
        
        entries = {}
        for label_text, key in campos:
            f = tk.Frame(frame, bg=COLOR_FONDO)
            f.pack(fill='x', pady=3)
            tk.Label(f, text=label_text, width=15, anchor='w', bg=COLOR_FONDO, fg=COLOR_TEXTO, font=('Segoe UI', 10, 'bold')).pack(side='left')
            entry = tk.Entry(f, width=30, font=('Arial', 10))
            entry.pack(side='right')
            entries[key] = entry
        
        def guardar():
            obligatorios = ['codigo', 'termino', 'categoria']
            for campo in obligatorios:
                if not entries[campo].get().strip():
                    messagebox.showerror("Error", f"El campo {campo} es obligatorio.")
                    return
            
            datos = {
                'codigo': entries['codigo'].get().strip(),
                'termino': entries['termino'].get().strip(),
                'categoria': entries['categoria'].get().strip(),
                'descripcion': entries['descripcion'].get().strip()
            }
            
            resultado, info = registrar_snomed(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Término agregado con éxito.\nID: {info}")
                ventana.destroy()
                self.mostrar_snomed()
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        tk.Button(frame_botones, text="💾 Guardar", bg='#2196F3', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=ventana.destroy).pack(side='left', padx=10)
    
    def buscar_snomed(self):
        """Abre ventana para buscar términos SNOMED CT"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar SNOMED CT")
        ventana.geometry("600x400")
        ventana.configure(bg='#f0f0f0')
        ventana.grab_set()
        
        tk.Label(
            ventana,
            text="🔍 BUSCAR TÉRMINOS SNOMED CT",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#2196F3'
        ).pack(pady=10)
        
        frame_buscar = tk.Frame(ventana, bg='#f0f0f0')
        frame_buscar.pack(pady=10)
        
        tk.Label(frame_buscar, text="Buscar:", font=('Arial', 11), bg='#f0f0f0').pack(side='left', padx=10)
        entry_buscar = tk.Entry(frame_buscar, font=('Arial', 11), width=30)
        entry_buscar.pack(side='left', padx=10)
        
        frame_resultados = tk.Frame(ventana, bg='#f0f0f0')
        frame_resultados.pack(fill='both', expand=True, padx=20, pady=10)
        
        tree = ttk.Treeview(
            frame_resultados,
            columns=('Código', 'Término', 'Categoría', 'Descripción'),
            show='headings',
            height=10
        )
        tree.configure(style='Masters.Treeview')
        tree.tag_configure('par', background='#F2F7FA')
        tree.tag_configure('impar', background='#FFFFFF')
        tree.heading('Código', text='Código')
        tree.heading('Término', text='Término')
        tree.heading('Categoría', text='Categoría')
        tree.heading('Descripción', text='Descripción')
        tree.column('Código', width=100)
        tree.column('Término', width=200)
        tree.column('Categoría', width=120)
        tree.column('Descripción', width=200)
        tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_resultados, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        
        def buscar():
            for item in tree.get_children():
                tree.delete(item)
            
            termino = entry_buscar.get().strip()
            if not termino:
                messagebox.showerror("Error", "Ingrese un término para buscar.")
                return
            
            resultados = buscar_snomed_por_termino(termino)
            for r in resultados:
                tree.insert('', 'end', values=(r[1], r[2], r[4], r[3]))
            
            if not resultados:
                messagebox.showinfo("Sin resultados", "No se encontraron términos que coincidan.")
        
        entry_buscar.bind('<Return>', lambda e: buscar())
        
        tk.Button(
            ventana,
            text="🔍 Buscar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=8,
            command=buscar
        ).pack(pady=10)
    
    # ============================================================
    # FÁRMACOS (Simplificado - Mismo patrón)
    # ============================================================
    
    def mostrar_farmacos(self):
        """Muestra la gestión de fármacos"""
        self.limpiar_contenido()
        
        tk.Label(
            self.frame_contenido,
            text="💊 GESTIÓN DE FÁRMACOS",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
            fg='#FF9800'
        ).pack(pady=5)
        
        frame_botones = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_botones.pack(pady=5)
        
        tk.Button(
            frame_botones,
            text="➕ Agregar Fármaco",
            bg='#FF9800',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.agregar_farmaco
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="🔄 Actualizar",
            bg='#2196F3',
            fg='white',
            font=('Arial', 10, 'bold'),
            padx=15,
            pady=5,
            command=self.mostrar_farmacos
        ).pack(side='left', padx=5)
        
        frame_tabla = tk.Frame(self.frame_contenido, bg='#f0f0f0')
        frame_tabla.pack(fill='both', expand=True, pady=10)
        
        tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Código', 'Nombre', 'Principio Activo', 'Presentación', 'Concentración', 'Vía'),
            show='headings',
            height=15
        )
        tree.configure(style='Masters.Treeview')
        tree.tag_configure('par', background='#F2F7FA')
        tree.tag_configure('impar', background='#FFFFFF')
        tree.heading('ID', text='ID')
        tree.heading('Código', text='Código')
        tree.heading('Nombre', text='Nombre')
        tree.heading('Principio Activo', text='Principio Activo')
        tree.heading('Presentación', text='Presentación')
        tree.heading('Concentración', text='Concentración')
        tree.heading('Vía', text='Vía Adm.')
        tree.column('ID', width=40, anchor='center')
        tree.column('Código', width=80, anchor='center')
        tree.column('Nombre', width=180)
        tree.column('Principio Activo', width=150)
        tree.column('Presentación', width=100)
        tree.column('Concentración', width=100)
        tree.column('Vía', width=100)
        tree.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        
        farmacos = listar_farmacos()
        for f in farmacos:
            tree.insert('', 'end', values=(f[0], f[1], f[2], f[3] or '', f[4] or '', f[5] or '', f[6] or ''))
    
    def agregar_farmaco(self):
        """Abre ventana para agregar un fármaco"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Agregar Fármaco")
        ventana.geometry("560x500")
        ventana.minsize(500, 430)
        ventana.configure(bg=COLOR_FONDO)
        ventana.grab_set()
        ventana.resizable(True, True)
        
        tk.Label(
            ventana,
            text="➕ AGREGAR FÁRMACO",
            font=('Segoe UI', 16, 'bold'),
            bg=COLOR_FONDO,
            fg='#FF9800'
        ).pack(pady=10)
        
        frame = tk.Frame(ventana, bg=COLOR_FONDO)
        frame.pack(padx=30, pady=10)
        
        campos = [
            ('Código *', 'codigo'),
            ('Nombre *', 'nombre'),
            ('Principio Activo', 'principio_activo'),
            ('Presentación', 'presentacion'),
            ('Concentración', 'concentracion'),
            ('Vía Administración', 'via_administracion')
        ]
        
        entries = {}
        for label_text, key in campos:
            f = tk.Frame(frame, bg=COLOR_FONDO)
            f.pack(fill='x', pady=3)
            tk.Label(f, text=label_text, width=18, anchor='w', bg=COLOR_FONDO, fg=COLOR_TEXTO, font=('Segoe UI', 10, 'bold')).pack(side='left')
            entry = tk.Entry(f, width=28, font=('Arial', 10))
            entry.pack(side='right')
            entries[key] = entry
        
        def guardar():
            if not entries['codigo'].get().strip() or not entries['nombre'].get().strip():
                messagebox.showerror("Error", "Código y Nombre son obligatorios.")
                return
            
            datos = {
                'codigo': entries['codigo'].get().strip(),
                'nombre': entries['nombre'].get().strip(),
                'principio_activo': entries['principio_activo'].get().strip(),
                'presentacion': entries['presentacion'].get().strip(),
                'concentracion': entries['concentracion'].get().strip(),
                'via_administracion': entries['via_administracion'].get().strip()
            }
            
            resultado, info = registrar_farmaco(datos)
            if resultado:
                messagebox.showinfo("Éxito", f"✅ Fármaco agregado con éxito.\nID: {info}")
                ventana.destroy()
                self.mostrar_farmacos()
            else:
                messagebox.showerror("Error", f"❌ {info}")
        
        frame_botones = tk.Frame(ventana, bg='#f0f0f0')
        frame_botones.pack(pady=20)
        tk.Button(frame_botones, text="💾 Guardar", bg='#FF9800', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=guardar).pack(side='left', padx=10)
        tk.Button(frame_botones, text="❌ Cancelar", bg='#f44336', fg='white',
                 font=('Arial', 11, 'bold'), padx=20, pady=8, command=ventana.destroy).pack(side='left', padx=10)


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = AppTablasMaestras(root)
    root.mainloop()
