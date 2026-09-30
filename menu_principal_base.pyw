# ================================================================
# Menu_principal_base.pyw
# OPENHIS-UNLaM - MENÚ PRINCIPAL (VERSIÓN SIN SEGURIDAD)
# ================================================================
#
# FUNCIONALIDADES:
#   ✅ Menú central con botones grandes para cada módulo
#   ✅ Categorías desplegables (Administración, Clínica, Maestros)
#   ✅ Abre cada módulo en ventana independiente
#   ✅ Fácil de extender con nuevos módulos
#   ✅ Información del sistema en la barra inferior
#
# MÓDULOS DISPONIBLES:
#   🟦 ADMINISTRACIÓN:
#      • Pacientes
#      • Profesionales
#      • Turnos (futuro)
#      • Facturación (futuro)
#
#   🟩 CLÍNICA:
#      • Signos Vitales
#      • Prescripciones
#      • Historia Clínica (futuro)
#
#   🟨 MAESTROS:
#      • Tablas Maestras
#      • Especialidades
#      • SNOMED CT
#      • Fármacos
#
#   🟥 INTEROPERABILIDAD:
#      • Exportador XML (futuro)
#      • Importador Fleming (futuro)
# ================================================================

import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import sys
import os
from datetime import datetime

COLOR_FONDO = '#F4F7FB'
COLOR_TEXTO = '#183B56'
COLOR_SECUNDARIO = '#5C7184'
COLOR_HEADER = '#123B5D'

# ================================================================
# CONFIGURACIÓN DE MÓDULOS
# ================================================================

# Cada módulo tiene: (nombre_archivo, título, descripción, color)
MODULOS = {
    'ADMINISTRACIÓN': {
        'color': '#2196F3',
        'icono': '🟦',
        'modulos': [
            {
                'nombre': 'Pacientes',
                'archivo': 'Pacientes_def_app.pyw',
                'descripcion': 'Gestión de pacientes: alta, baja, modificación y búsqueda',
                'icono': '👤'
            },
            {
                'nombre': 'Profesionales',
                'archivo': 'Profesionales_def_app.pyw',
                'descripcion': 'Gestión de profesionales de la salud',
                'icono': '👨‍⚕️'
            },
            {
                'nombre': 'Turnos',
                'archivo': None,  # No implementado aún
                'descripcion': 'Gestión de turnos y agenda (próximamente)',
                'icono': '📅'
            }
        ]
    },
    'CLÍNICA': {
        'color': '#4CAF50',
        'icono': '🟩',
        'modulos': [
            {
                'nombre': 'Signos Vitales',
                'archivo': 'Signos_vitales_def_app.pyw',
                'descripcion': 'Registro de signos vitales con médico interviniente',
                'icono': '❤️'
            },
            {
                'nombre': 'Prescripciones',
                'archivo': 'Prescripciones_def_app.pyw',
                'descripcion': 'Prescripción de medicamentos',
                'icono': '💊'
            },
            {
                'nombre': 'Historia Clínica',
                'archivo': None,
                'descripcion': 'Historia Clínica Electrónica (próximamente)',
                'icono': '📋'
            }
        ]
    },
    'TABLAS MAESTRAS': {
        'color': '#FF9800',
        'icono': '🟨',
        'modulos': [
            {
                'nombre': 'Tablas Maestras',
                'archivo': 'Tablas_maestras.pyw',
                'descripcion': 'Especialidades, SNOMED CT y Fármacos',
                'icono': '📚'
            }
        ]
    },
    'INTEROPERABILIDAD': {
        'color': '#E91E63',
        'icono': '🟥',
        'modulos': [
            {
                'nombre': 'Exportar XML',
                'archivo': None,
                'descripcion': 'Exportar datos a FHIR XML (próximamente)',
                'icono': '📤'
            },
            {
                'nombre': 'Hospital Fleming',
                'archivo': None,
                'descripcion': 'Importar datos desde otro hospital (próximamente)',
                'icono': '🏥'
            }
        ]
    }
}


# ================================================================
# FUNCIÓN PARA ABRIR UN MÓDULO
# ================================================================

def abrir_modulo(archivo, nombre):
    """
    Abre un módulo en un proceso independiente.
    Esto permite que cada módulo tenga su propia ventana Tkinter.
    """
    if archivo is None:
        messagebox.showinfo(
            "Módulo no disponible",
            f"El módulo '{nombre}' estará disponible en una próxima versión."
        )
        return
    
    if not os.path.exists(archivo):
        messagebox.showerror(
            "Error",
            f"No se encontró el archivo:\n{archivo}\n\n"
            f"Asegúrese de que el módulo esté en la misma carpeta que este menú."
        )
        return
    
    try:
        # Abrir en un proceso independiente (así no bloquea el menú)
        subprocess.Popen([sys.executable, archivo])
        print(f"[INFO] Módulo abierto: {archivo}")
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo abrir el módulo:\n{e}")


# ================================================================
# APLICACIÓN PRINCIPAL DEL MENÚ
# ================================================================

class MenuPrincipal:
    """Aplicación del menú principal de OpenHIS-UNLaM"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM - Sistema de Información Hospitalaria")
        self.root.geometry("1100x750")
        self.root.configure(bg=COLOR_FONDO)
        self.root.minsize(900, 600)
        self.root.protocol("WM_DELETE_WINDOW", self.salir)

        estilo = ttk.Style(self.root)
        estilo.theme_use('clam')
        estilo.configure('Modern.Vertical.TScrollbar', troughcolor='#E6EDF3', background='#A7BAC9')
        estilo.configure('Modern.TLabelframe', background=COLOR_FONDO)
        estilo.configure('Modern.TLabelframe.Label', background=COLOR_FONDO, foreground=COLOR_TEXTO)

        # Atajos para las acciones de uso frecuente.
        self.root.bind('<Control-p>', lambda event: abrir_modulo('Pacientes_def_app.pyw', 'Pacientes'))
        self.root.bind('<Control-s>', lambda event: abrir_modulo('Signos_vitales_def_app.pyw', 'Signos Vitales'))
        self.root.bind('<Control-r>', lambda event: abrir_modulo('Prescripciones_def_app.pyw', 'Prescripciones'))
        
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
        
        # ---------- ENCABEZADO ----------
        self.crear_encabezado()
        
        # ---------- BIENVENIDA ----------
        self.crear_bienvenida()

        # ---------- ACCESOS RÁPIDOS ----------
        self.crear_accesos_rapidos()
        
        # ---------- MÓDULOS ----------
        self.crear_modulos()
        
        # ---------- BARRA DE ESTADO ----------
        self.crear_barra_estado()
    
    # ------------------------------------------------------------
    # ENCABEZADO
    # ------------------------------------------------------------
    def crear_encabezado(self):
        """Crea el encabezado con el título del sistema"""
        frame_header = tk.Frame(self.frame_principal, bg=COLOR_HEADER, height=80)
        frame_header.pack(fill='x', pady=(0, 15))
        frame_header.pack_propagate(False)
        
        # Título principal
        tk.Label(
            frame_header,
            text="🏥 OpenHIS-UNLaM",
            font=('Segoe UI', 22, 'bold'),
            bg=COLOR_HEADER,
            fg='white'
        ).pack(side='left', padx=20, pady=15)
        
        # Subtítulo
        tk.Label(
            frame_header,
            text="Sistema de Información Hospitalaria",
            font=('Segoe UI', 12),
            bg=COLOR_HEADER,
            fg='#B0C4DE'
        ).pack(side='left', padx=5, pady=20)
        
        # Fecha/hora a la derecha
        self.label_fecha = tk.Label(
            frame_header,
            text="",
            font=('Segoe UI', 10),
            bg=COLOR_HEADER,
            fg='#B0C4DE'
        )
        self.label_fecha.pack(side='right', padx=20)
        self.actualizar_fecha()
    
    def actualizar_fecha(self):
        """Actualiza la fecha y hora cada segundo"""
        ahora = datetime.now()
        texto = ahora.strftime("%A %d/%m/%Y - %H:%M:%S")
        # Capitalizar primera letra del día
        texto = texto.capitalize()
        self.label_fecha.config(text=texto)
        self.root.after(1000, self.actualizar_fecha)
    
    # ------------------------------------------------------------
    # BIENVENIDA
    # ------------------------------------------------------------
    def crear_bienvenida(self):
        """Crea el mensaje de bienvenida"""
        frame_bienvenida = tk.Frame(self.frame_principal, bg=COLOR_FONDO)
        frame_bienvenida.pack(fill='x', pady=(0, 20))
        
        tk.Label(
            frame_bienvenida,
            text="Bienvenido al Sistema",
            font=('Segoe UI', 16, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_TEXTO
        ).pack()
        
        tk.Label(
            frame_bienvenida,
            text="Seleccione un módulo para comenzar a trabajar",
            font=('Segoe UI', 11),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO
        ).pack(pady=3)

    def crear_accesos_rapidos(self):
        """Crea accesos directos para las tareas más frecuentes."""
        frame = tk.LabelFrame(
            self.frame_principal,
            text=" Acciones frecuentes ",
            font=('Segoe UI', 11, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_TEXTO,
            padx=10,
            pady=8
        )
        frame.pack(fill='x', pady=(0, 12))

        acciones = [
            ('➕ Nuevo paciente', 'Pacientes_def_app.pyw', 'Pacientes', '#1976D2'),
            ('❤️ Registrar signos', 'Signos_vitales_def_app.pyw', 'Signos Vitales', '#E91E63'),
            ('💊 Nueva prescripción', 'Prescripciones_def_app.pyw', 'Prescripciones', '#388E3C'),
            ('📚 Tablas maestras', 'Tablas_maestras.pyw', 'Tablas Maestras', '#F57C00')
        ]

        for texto, archivo, nombre, color in acciones:
            boton = tk.Button(
                frame,
                text=texto,
                font=('Segoe UI', 10, 'bold'),
                bg=color,
                fg='white',
                activebackground=self.oscurecer_color(color),
                activeforeground='white',
                relief='flat',
                padx=14,
                pady=7,
                cursor='hand2',
                command=lambda ruta=archivo, titulo=nombre: abrir_modulo(ruta, titulo)
            )
            boton.pack(side='left', padx=5, expand=True, fill='x')
    
    # ------------------------------------------------------------
    # MÓDULOS
    # ------------------------------------------------------------
    def crear_modulos(self):
        """Crea los botones de módulos organizados por categorías"""
        frame_info = tk.Frame(self.frame_principal, bg=COLOR_FONDO)
        frame_info.pack(fill='x', pady=(0, 4))

        tk.Label(
            frame_info,
            text="Módulos del sistema",
            font=('Segoe UI', 12, 'bold'),
            bg=COLOR_FONDO,
            fg=COLOR_TEXTO
        ).pack(side='left')

        tk.Label(
            frame_info,
            text="Ctrl+P pacientes  ·  Ctrl+S signos  ·  Ctrl+R recetas",
            font=('Segoe UI', 9),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO
        ).pack(side='right')

        # Canvas con scrollbar para muchos módulos
        canvas = tk.Canvas(self.frame_principal, bg=COLOR_FONDO, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.frame_principal, orient='vertical', command=canvas.yview)
        frame_scroll = tk.Frame(canvas, bg=COLOR_FONDO)
        
        frame_scroll.bind(
            '<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        
        canvas.create_window((0, 0), window=frame_scroll, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Crear cada categoría
        for categoria, datos in MODULOS.items():
            self.crear_categoria(frame_scroll, categoria, datos)
    
    def crear_categoria(self, parent, nombre_categoria, datos):
        """Crea una categoría con sus módulos"""
        # Frame de categoría
        frame_categoria = tk.LabelFrame(
            parent,
            text=f" {datos['icono']}  {nombre_categoria} ",
            font=('Segoe UI', 13, 'bold'),
            bg=COLOR_FONDO,
            fg=datos['color'],
            padx=15,
            pady=15,
            relief='flat',
            bd=1
        )
        frame_categoria.pack(fill='x', padx=10, pady=10)
        
        # Frame para botones en grid
        frame_botones = tk.Frame(frame_categoria, bg=COLOR_FONDO)
        frame_botones.pack(fill='x')
        
        # Crear botones de módulos (3 por fila)
        for i, modulo in enumerate(datos['modulos']):
            fila = i // 3
            columna = i % 3
            
            self.crear_boton_modulo(
                frame_botones,
                modulo,
                datos['color'],
                fila,
                columna
            )
    
    def crear_boton_modulo(self, parent, modulo, color, fila, columna):
        """Crea un botón individual de módulo"""
        # Determinar si está disponible
        disponible = modulo['archivo'] is not None and os.path.exists(modulo['archivo']) if modulo['archivo'] else False
        
        # Colores según disponibilidad
        if disponible:
            bg_color = color
            fg_color = 'white'
            estado = 'normal'
        else:
            bg_color = '#BDBDBD'
            fg_color = '#666666'
            estado = 'normal'  # Igual se puede hacer clic para ver el mensaje
        
        # Frame contenedor del botón
        frame = tk.Frame(parent, bg=COLOR_FONDO, padx=8, pady=8)
        frame.grid(row=fila, column=columna, sticky='nsew', padx=5, pady=5)
        
        # Botón principal
        btn = tk.Button(
            frame,
            text=f"{modulo['icono']}\n\n{modulo['nombre']}",
            font=('Segoe UI', 11, 'bold'),
            bg=bg_color,
            fg=fg_color,
            width=18,
            height=4,
            relief='flat',
            bd=0,
            cursor='hand2' if disponible else 'arrow',
            command=lambda: abrir_modulo(modulo['archivo'], modulo['nombre'])
        )
        btn.pack()
        
        # Efecto hover
        if disponible:
            def on_enter(e):
                btn.config(bg=self.oscurecer_color(color))
            def on_leave(e):
                btn.config(bg=color)
            btn.bind('<Enter>', on_enter)
            btn.bind('<Leave>', on_leave)
        
        # Descripción debajo
        desc = modulo['descripcion']
        if len(desc) > 40:
            desc = desc[:37] + '...'
        
        tk.Label(
            frame,
            text=desc,
            font=('Segoe UI', 8),
            bg=COLOR_FONDO,
            fg=COLOR_SECUNDARIO,
            wraplength=160,
            justify='center'
        ).pack(pady=(3, 0))
        
        # Configurar grid responsive
        parent.grid_columnconfigure(columna, weight=1)
    
    def oscurecer_color(self, color_hex):
        """Oscurece un color hex para el efecto hover"""
        # Convertir hex a RGB
        color_hex = color_hex.lstrip('#')
        r, g, b = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
        # Oscurecer un 15%
        r = max(0, int(r * 0.85))
        g = max(0, int(g * 0.85))
        b = max(0, int(b * 0.85))
        return f'#{r:02x}{g:02x}{b:02x}'
    
    # ------------------------------------------------------------
    # BARRA DE ESTADO
    # ------------------------------------------------------------
    def crear_barra_estado(self):
        """Crea la barra inferior con información del sistema"""
        frame_estado = tk.Frame(self.frame_principal, bg='#003366', height=30)
        frame_estado.pack(fill='x', pady=(15, 0))
        frame_estado.pack_propagate(False)
        
        # Info del sistema
        tk.Label(
            frame_estado,
            text="✅ OpenHIS-UNLaM v0.3 - Sprint 3",
            font=('Segoe UI', 9),
            bg='#003366',
            fg='white'
        ).pack(side='left', padx=15)
        
        # Hospital
        tk.Label(
            frame_estado,
            text="🏥 Hospital Universitario San Justo",
            font=('Segoe UI', 9),
            bg='#003366',
            fg='#B0C4DE'
        ).pack(side='left', padx=15)
        
        # Botón salir
        tk.Button(
            frame_estado,
            text="❌ Salir",
            bg='#f44336',
            fg='white',
            font=('Segoe UI', 9, 'bold'),
            padx=10,
            pady=2,
            command=self.salir
        ).pack(side='right', padx=10, pady=4)
    
    def salir(self):
        """Cierra el menú principal"""
        if messagebox.askyesno("Confirmar", "¿Está seguro de cerrar el sistema?"):
            self.root.destroy()


# ================================================================
# PUNTO DE ENTRADA
# ================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = MenuPrincipal(root)
    root.mainloop()
