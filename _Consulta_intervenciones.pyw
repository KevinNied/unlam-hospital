# ================================================================
# CONSULTA DE INTERVENCIONES CLINICAS
# OpenHIS-UNLaM | Interfaz gráfica Tkinter
# Archivo: _Consulta_intervenciones.pyw
# ================================================================
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RUTA_BD = BASE_DIR / "BD" / "Salud.db"
RUTA_SESION = BASE_DIR / ".sesion"
ROLES_PERMITIDOS = {"admin", "medico", "enfermero"}


def verificar_acceso(conexion):
    try:
        usuario_id = int(RUTA_SESION.read_text(encoding="utf-8").split("|", 1)[0])
    except (OSError, ValueError):
        raise PermissionError("Inicie sesión desde el menú principal.") from None
    usuario = conexion.execute(
        "SELECT id, nombre_completo, rol FROM Usuarios WHERE id = ? AND activo = 1",
        (usuario_id,)
    ).fetchone()
    if not usuario or usuario[2] not in ROLES_PERMITIDOS:
        raise PermissionError("No tiene permisos para consultar intervenciones.")
    return usuario


def valor_clinico(valor):
    return "-" if valor is None else valor


def conectar_bd():
    if not RUTA_BD.exists():
        raise FileNotFoundError(
            f"No se encontró {RUTA_BD}. Ejecute el programa desde la carpeta principal "
            "del proyecto, donde se encuentra la carpeta BD."
        )
    conexion = sqlite3.connect(RUTA_BD.as_uri() + "?mode=rw", uri=True)
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion

def obtener_pacientes(texto=""):
    conexion = conectar_bd()
    try:
        cursor = conexion.cursor()
        verificar_acceso(conexion)
        texto = texto.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        patron = f"%{texto}%"
        cursor.execute("""
            SELECT id, dni, apellido, nombre, fecha_nacimiento, sexo
            FROM Pacientes
            WHERE activo = 1
              AND (dni LIKE ? ESCAPE '!' OR apellido LIKE ? ESCAPE '!' OR nombre LIKE ? ESCAPE '!')
            ORDER BY apellido, nombre
        """, (patron, patron, patron))
        return cursor.fetchall()
    finally:
        conexion.close()

def obtener_intervenciones(paciente_id):
    conexion = conectar_bd()
    try:
        conexion.execute("BEGIN IMMEDIATE")
        usuario = verificar_acceso(conexion)
        cursor = conexion.cursor()
        if not cursor.execute("SELECT 1 FROM Pacientes WHERE id = ? AND activo = 1", (paciente_id,)).fetchone():
            raise ValueError("El paciente no existe o está inactivo.")
        cursor.execute("""
            SELECT sv.id, sv.fecha_hora, sv.presion_sistolica,
                   sv.presion_diastolica, sv.frecuencia_cardiaca,
                   sv.temperatura, sv.saturacion_oxigeno,
                   sv.motivo_consulta, p.nombre, p.apellido
            FROM SignosVitales sv
            LEFT JOIN Profesionales p ON p.id = sv.medico_id
            WHERE sv.paciente_id = ? AND sv.activo = 1
            ORDER BY sv.fecha_hora DESC
        """, (paciente_id,))
        signos = cursor.fetchall()

        cursor.execute("""
            SELECT pr.id, pr.fecha_prescripcion, f.nombre,
                   pr.dosis, pr.via_administracion, pr.frecuencia,
                   pr.duracion, pr.indicaciones, prof.nombre, prof.apellido
            FROM Prescripciones pr
            LEFT JOIN Farmacos f ON f.id = pr.farmaco_id
            LEFT JOIN Profesionales prof ON prof.id = pr.profesional_id
            WHERE pr.paciente_id = ? AND pr.activo = 1
            ORDER BY pr.fecha_prescripcion DESC
        """, (paciente_id,))
        prescripciones = cursor.fetchall()
        # C es el código utilizado para consultas también en _HCE.pyw.
        cursor.execute("""
            INSERT INTO Auditoria (usuario_id, usuario_nombre, tabla_afectada,
                registro_id, tipo_accion, descripcion, origen_sistema)
            VALUES (?, ?, 'Pacientes', ?, 'C', 'Consulta de intervenciones clínicas', 'OpenHIS-UNLaM')
        """, (usuario[0], usuario[1], paciente_id))
        conexion.commit()
        return signos, prescripciones
    finally:
        conexion.close()

class AppConsulta:
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM | HU-08 - Consulta de intervenciones")
        self.root.geometry("1180x720")
        self.root.minsize(900, 560)
        self.pacientes = []
        self._crear_interfaz()
        self.buscar_pacientes()

    def _crear_interfaz(self):
        encabezado = ttk.Frame(self.root, padding=(14, 12))
        encabezado.pack(fill="x")
        ttk.Label(encabezado, text="CONSULTA DE INTERVENCIONES CLÍNICAS",
                  font=("Arial", 16, "bold")).pack(anchor="w")
        ttk.Label(encabezado, text="HU-08 | OpenHIS-UNLaM",
                  font=("Arial", 10)).pack(anchor="w", pady=(3, 0))

        busqueda = ttk.LabelFrame(self.root, text="Buscar paciente activo", padding=10)
        busqueda.pack(fill="x", padx=14, pady=(0, 10))
        self.var_busqueda = tk.StringVar()
        ttk.Label(busqueda, text="DNI, apellido o nombre:").pack(side="left")
        entrada = ttk.Entry(busqueda, textvariable=self.var_busqueda, width=35)
        entrada.pack(side="left", padx=8)
        entrada.bind("<Return>", lambda _e: self.buscar_pacientes())
        ttk.Button(busqueda, text="Buscar", command=self.buscar_pacientes).pack(side="left")
        ttk.Button(busqueda, text="Limpiar", command=self.limpiar).pack(side="left", padx=6)

        cuerpo = ttk.Panedwindow(self.root, orient="horizontal")
        cuerpo.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        izquierda = ttk.Frame(cuerpo, padding=5)
        derecha = ttk.Frame(cuerpo, padding=5)
        cuerpo.add(izquierda, weight=1)
        cuerpo.add(derecha, weight=3)

        ttk.Label(izquierda, text="Resultados").pack(anchor="w", pady=(0, 5))
        self.lista = ttk.Treeview(izquierda, columns=("dni", "apellido", "nombre"),
                                  show="headings", height=18, selectmode="browse")
        for col, titulo, ancho in [
            ("dni", "DNI", 95), ("apellido", "Apellido", 120), ("nombre", "Nombre", 110)
        ]:
            self.lista.heading(col, text=titulo)
            self.lista.column(col, width=ancho, anchor="w")
        self.lista.pack(fill="both", expand=True)
        self.lista.bind("<<TreeviewSelect>>", self.seleccionar_paciente)

        self.lbl_paciente = ttk.Label(derecha, text="Seleccione un paciente para ver sus intervenciones.",
                                      font=("Arial", 11, "bold"), wraplength=760)
        self.lbl_paciente.pack(anchor="w", pady=(0, 8))
        self.tabs = ttk.Notebook(derecha)
        self.tabs.pack(fill="both", expand=True)
        tab_signos = ttk.Frame(self.tabs, padding=5)
        tab_rx = ttk.Frame(self.tabs, padding=5)
        self.tabs.add(tab_signos, text="Signos vitales / admisiones")
        self.tabs.add(tab_rx, text="Prescripciones")

        self.tv_signos = self._crear_tabla(tab_signos, [
            ("fecha", "Fecha y hora", 140), ("pa", "Presión", 90),
            ("fc", "FC", 55), ("temp", "Temp. °C", 70),
            ("spo2", "SpO₂ %", 70), ("motivo", "Motivo de consulta", 230),
            ("prof", "Profesional", 160)
        ])
        self.tv_rx = self._crear_tabla(tab_rx, [
            ("fecha", "Fecha", 140), ("farmaco", "Fármaco", 150),
            ("dosis", "Dosis", 100), ("via", "Vía", 100),
            ("frecuencia", "Frecuencia", 110), ("duracion", "Duración", 100),
            ("indicaciones", "Indicaciones", 210), ("prof", "Profesional", 150)
        ])
        ttk.Label(self.root, text="Uso académico. Acceso sujeto a los permisos del sistema.",
                  anchor="w").pack(fill="x", padx=14, pady=(0, 8))

    def _crear_tabla(self, parent, columnas):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        ids = [x[0] for x in columnas]
        tv = ttk.Treeview(frame, columns=ids, show="headings")
        for col, titulo, ancho in columnas:
            tv.heading(col, text=titulo)
            tv.column(col, width=ancho, minwidth=60, anchor="w")
        vs = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        tv.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tv

    def buscar_pacientes(self):
        self.pacientes = []
        self.lista.delete(*self.lista.get_children())
        self._vaciar_tablas()
        self.lbl_paciente.config(text="Seleccione un paciente para ver sus intervenciones.")
        try:
            self.pacientes = obtener_pacientes(self.var_busqueda.get())
            self.lista.delete(*self.lista.get_children())
            for p in self.pacientes:
                self.lista.insert("", "end", iid=str(p[0]), values=(p[1], p[2], p[3]))
            self._vaciar_tablas()
            self.lbl_paciente.config(text=f"Pacientes encontrados: {len(self.pacientes)}. Seleccione uno.")
        except Exception as exc:
            messagebox.showerror("Error de base de datos", str(exc), parent=self.root)

    def seleccionar_paciente(self, _evento=None):
        seleccion = self.lista.selection()
        if not seleccion:
            self._vaciar_tablas()
            self.lbl_paciente.config(text="Seleccione un paciente para ver sus intervenciones.")
            return
        paciente_id = int(seleccion[0])
        fila = next((p for p in self.pacientes if p[0] == paciente_id), None)
        if not fila:
            self._vaciar_tablas()
            self.lbl_paciente.config(text="Seleccione un paciente válido.")
            return
        self._vaciar_tablas()
        try:
            signos, rx = obtener_intervenciones(paciente_id)
            self.lbl_paciente.config(
                text=f"Paciente: {fila[2]}, {fila[3]} | DNI: {fila[1]} | "
                     f"Nacimiento: {fila[4]} | Sexo: {fila[5]}"
            )
            for s in signos:
                pa = f"{valor_clinico(s[2])} / {valor_clinico(s[3])}"
                profesional = " ".join(x for x in (s[8], s[9]) if x) or "No informado"
                self.tv_signos.insert("", "end", values=(
                    s[1] or "", pa, valor_clinico(s[4]), valor_clinico(s[5]),
                    valor_clinico(s[6]), s[7] or "", profesional
                ))
            for r in rx:
                profesional = " ".join(x for x in (r[8], r[9]) if x) or "No informado"
                self.tv_rx.insert("", "end", values=(
                    r[1] or "", r[2] or "No informado", r[3] or "", r[4] or "",
                    r[5] or "", r[6] or "", r[7] or "", profesional
                ))
        except Exception as exc:
            self._vaciar_tablas()
            self.lbl_paciente.config(text="No se pudo consultar al paciente.")
            messagebox.showerror("Error al consultar", str(exc), parent=self.root)

    def _vaciar_tablas(self):
        for tv in (getattr(self, "tv_signos", None), getattr(self, "tv_rx", None)):
            if tv:
                tv.delete(*tv.get_children())

    def limpiar(self):
        self.var_busqueda.set("")
        self.buscar_pacientes()

if __name__ == "__main__":
    root = tk.Tk()
    AppConsulta(root)
    root.mainloop()
