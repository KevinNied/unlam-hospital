# -*- coding: utf-8 -*-
"""OpenHIS-UNLaM | Historia Clínica Electrónica.
Línea de tiempo, antecedentes y trazabilidad clínica.
"""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "BD" / "Salud.db"
ROLES_CONSULTA = {"admin", "medico", "enfermero"}
ROLES_REGISTRO = {"admin", "medico"}
ROLES_AUDITORIA = {"admin", "medico"}


def conectar():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"No se encontró la base de datos: {DB_PATH}")
    c = sqlite3.connect(str(DB_PATH), timeout=20)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def obtener_sesion():
    from Auditoria_utiles import obtener_usuario_actual
    sesion = obtener_usuario_actual()
    if isinstance(sesion, (tuple, list)):
        uid = sesion[0] if sesion else None
    elif isinstance(sesion, dict):
        uid = sesion.get("usuario_id") or sesion.get("id")
    else:
        uid = sesion
    if not uid:
        raise PermissionError("No se identificó una sesión válida. Inicie sesión desde el menú principal.")
    with conectar() as c:
        u = c.execute(
            "SELECT id, usuario, nombre_completo, rol FROM Usuarios WHERE id=? AND activo=1",
            (uid,)
        ).fetchone()
    if not u:
        raise PermissionError("La sesión no corresponde a un usuario activo.")
    rol = (u["rol"] or "").lower()
    if rol not in ROLES_CONSULTA:
        raise PermissionError("El perfil no está autorizado para consultar historias clínicas.")
    return dict(u)


def asegurar_estructura():
    """Migración aditiva: crea antecedentes sin alterar tablas existentes."""
    with conectar() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS AntecedentesClinicos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_id INTEGER NOT NULL REFERENCES Pacientes(id),
                tipo TEXT NOT NULL CHECK(tipo IN ('PERSONAL','FAMILIAR')),
                descripcion TEXT NOT NULL CHECK(length(trim(descripcion)) > 0),
                profesional_id INTEGER REFERENCES Profesionales(id),
                usuario_registro_id INTEGER NOT NULL REFERENCES Usuarios(id),
                fecha_registro TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TEXT,
                activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0,1))
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_antecedentes_paciente
            ON AntecedentesClinicos(paciente_id, activo, fecha_registro DESC)
        """)


def registrar_auditoria(c, uid, tabla, registro_id, accion, descripcion, antes=None, despues=None):
    """Inserta auditoría usando exclusivamente los códigos admitidos por Auditoria."""
    c.execute("""
        INSERT INTO Auditoria
        (usuario_id, usuario_nombre, tabla_afectada, registro_id, tipo_accion,
         descripcion, datos_anteriores, datos_nuevos, origen_sistema)
        VALUES (?, (SELECT nombre_completo FROM Usuarios WHERE id=?), ?, ?, ?, ?, ?, ?, ?)
    """, (
        uid, uid, tabla, registro_id, accion, descripcion,
        None if antes is None else __import__("json").dumps(antes, ensure_ascii=False, default=str),
        None if despues is None else __import__("json").dumps(despues, ensure_ascii=False, default=str),
        "OpenHIS-UNLaM"
    ))


def auditar_lectura(uid, paciente_id):
    try:
        with conectar() as c:
            registrar_auditoria(c, uid, "Pacientes", paciente_id, "C",
                                "Consulta de Historia Clínica Electrónica")
    except Exception:
        # La consulta clínica no se bloquea por un fallo de auditoría de lectura.
        # El incidente se muestra en consola para diagnóstico técnico.
        import traceback
        traceback.print_exc()


def obtener_linea_tiempo(pid):
    eventos = []
    with conectar() as c:
        rows = c.execute("""
            SELECT cc.id, cc.fecha_hora AS fecha, 'Consulta médica' AS tipo,
                   cc.motivo_consulta AS resumen,
                   pr.apellido || ', ' || pr.nombre AS profesional,
                   cc.evaluacion, cc.evolucion
            FROM ConsultasClinicas cc
            LEFT JOIN Profesionales pr ON pr.id=cc.profesional_id
            WHERE cc.paciente_id=?
        """, (pid,)).fetchall()
        for r in rows:
            eventos.append({
                "fecha": r["fecha"] or "", "tipo": r["tipo"],
                "resumen": r["resumen"] or "", "profesional": r["profesional"] or "No informado",
                "detalle": f"Motivo: {r['resumen'] or '-'}\n\nEvaluación: {r['evaluacion'] or '-'}\n\nEvolución: {r['evolucion'] or '-'}"
            })

        rows = c.execute("""
            SELECT sv.id, sv.fecha_hora AS fecha, sv.motivo_consulta,
                   sv.presion_sistolica, sv.presion_diastolica, sv.frecuencia_cardiaca,
                   sv.temperatura, sv.saturacion_oxigeno,
                   p.apellido || ', ' || p.nombre AS profesional
            FROM SignosVitales sv
            LEFT JOIN Profesionales p ON p.id=sv.medico_id
            WHERE sv.paciente_id=? AND COALESCE(sv.activo,1)=1
        """, (pid,)).fetchall()
        for r in rows:
            resumen = r["motivo_consulta"] or "Registro de signos vitales"
            detalle = (
                f"Motivo: {resumen}\n\nPresión arterial: {r['presion_sistolica'] or '-'} / {r['presion_diastolica'] or '-'} mmHg"
                f"\nFrecuencia cardíaca: {r['frecuencia_cardiaca'] or '-'} lpm"
                f"\nTemperatura: {r['temperatura'] if r['temperatura'] is not None else '-'} °C"
                f"\nSaturación de oxígeno: {r['saturacion_oxigeno'] or '-'} %"
            )
            eventos.append({"fecha": r["fecha"] or "", "tipo": "Signos vitales",
                            "resumen": resumen, "profesional": r["profesional"] or "No informado",
                            "detalle": detalle})

        rows = c.execute("""
            SELECT rx.id, rx.fecha_prescripcion AS fecha, f.nombre AS farmaco,
                   rx.dosis, rx.via_administracion, rx.frecuencia, rx.duracion,
                   rx.indicaciones, p.apellido || ', ' || p.nombre AS profesional
            FROM Prescripciones rx
            LEFT JOIN Farmacos f ON f.id=rx.farmaco_id
            LEFT JOIN Profesionales p ON p.id=rx.profesional_id
            WHERE rx.paciente_id=? AND COALESCE(rx.activo,1)=1
        """, (pid,)).fetchall()
        for r in rows:
            resumen = f"{r['farmaco'] or 'Fármaco'} — {r['dosis'] or ''}"
            detalle = (
                f"Medicamento: {r['farmaco'] or '-'}\nDosis: {r['dosis'] or '-'}"
                f"\nVía: {r['via_administracion'] or '-'}\nFrecuencia: {r['frecuencia'] or '-'}"
                f"\nDuración: {r['duracion'] or '-'}\nIndicaciones: {r['indicaciones'] or '-'}"
            )
            eventos.append({"fecha": r["fecha"] or "", "tipo": "Prescripción",
                            "resumen": resumen, "profesional": r["profesional"] or "No informado",
                            "detalle": detalle})

        # Integración tolerante de prácticas/intervenciones si el proyecto tiene una tabla compatible.
        tablas = {x["name"] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        candidatos = [t for t in ("Intervenciones", "Procedimientos", "Practicas", "Prácticas") if t in tablas]
        for tabla in candidatos:
            cols = {x["name"] for x in c.execute(f'PRAGMA table_info("{tabla}")')}
            pid_col = next((x for x in ("paciente_id", "id_paciente") if x in cols), None)
            fecha_col = next((x for x in ("fecha_hora", "fecha", "fecha_intervencion", "fecha_registro") if x in cols), None)
            id_col = "id" if "id" in cols else None
            if not pid_col or not fecha_col or not id_col:
                continue
            desc_col = next((x for x in ("descripcion", "nombre", "tipo", "procedimiento", "detalle") if x in cols), None)
            prof_col = next((x for x in ("profesional_id", "medico_id") if x in cols), None)
            select_desc = f'"{desc_col}"' if desc_col else "'Práctica registrada'"
            join = f' LEFT JOIN Profesionales p ON p.id=t."{prof_col}"' if prof_col else ""
            select_prof = "p.apellido || ', ' || p.nombre" if prof_col else "'No informado'"
            try:
                q = f'SELECT t."{fecha_col}" AS fecha, {select_desc} AS resumen, {select_prof} AS profesional FROM "{tabla}" t{join} WHERE t."{pid_col}"=?'
                for r in c.execute(q, (pid,)).fetchall():
                    eventos.append({"fecha": r["fecha"] or "", "tipo": "Práctica",
                                    "resumen": r["resumen"] or "Práctica registrada",
                                    "profesional": r["profesional"] or "No informado",
                                    "detalle": f"Práctica/intervención: {r['resumen'] or '-'}"})
            except sqlite3.Error:
                continue

    eventos.sort(key=lambda x: x["fecha"], reverse=True)
    return eventos


def obtener_antecedentes(pid):
    with conectar() as c:
        return c.execute("""
            SELECT a.*, p.apellido || ', ' || p.nombre AS profesional
            FROM AntecedentesClinicos a
            LEFT JOIN Profesionales p ON p.id=a.profesional_id
            WHERE a.paciente_id=? AND a.activo=1
            ORDER BY a.fecha_registro DESC, a.id DESC
        """, (pid,)).fetchall()


def guardar_antecedente(uid, pid, tipo, descripcion, profesional_id, antecedente_id=None):
    descripcion = descripcion.strip()
    if tipo not in ("PERSONAL", "FAMILIAR") or not descripcion:
        raise ValueError("Seleccione el tipo e ingrese una descripción.")
    with conectar() as c:
        c.execute("BEGIN IMMEDIATE")
        if antecedente_id:
            anterior = c.execute("""
                SELECT tipo, descripcion, profesional_id FROM AntecedentesClinicos
                WHERE id=? AND paciente_id=? AND activo=1
            """, (antecedente_id, pid)).fetchone()
            if not anterior:
                raise ValueError("El antecedente seleccionado ya no está disponible.")
            antes = dict(anterior)
            c.execute("""
                UPDATE AntecedentesClinicos
                SET tipo=?, descripcion=?, profesional_id=?, fecha_actualizacion=CURRENT_TIMESTAMP
                WHERE id=? AND paciente_id=?
            """, (tipo, descripcion, profesional_id, antecedente_id, pid))
            despues = {"tipo": tipo, "descripcion": descripcion, "profesional_id": profesional_id}
            registrar_auditoria(c, uid, "AntecedentesClinicos", antecedente_id, "M",
                                "Modificación de antecedente clínico", antes, despues)
            return antecedente_id
        cur = c.execute("""
            INSERT INTO AntecedentesClinicos
            (paciente_id, tipo, descripcion, profesional_id, usuario_registro_id)
            VALUES (?,?,?,?,?)
        """, (pid, tipo, descripcion, profesional_id, uid))
        aid = cur.lastrowid
        registrar_auditoria(c, uid, "AntecedentesClinicos", aid, "A",
                            "Alta de antecedente clínico", None,
                            {"paciente_id": pid, "tipo": tipo, "descripcion": descripcion,
                             "profesional_id": profesional_id})
        return aid


def obtener_auditoria(pid=None, usuario=None, desde=None, hasta=None):
    """Consulta auditoría HCE asociada al paciente; no expone datos sensibles completos."""
    filtros = []
    args = []
    joins = """
        LEFT JOIN ConsultasClinicas cc
          ON a.tabla_afectada='ConsultasClinicas' AND cc.id=a.registro_id
        LEFT JOIN AntecedentesClinicos ac
          ON a.tabla_afectada='AntecedentesClinicos' AND ac.id=a.registro_id
        LEFT JOIN SignosVitales sv
          ON a.tabla_afectada='SignosVitales' AND sv.id=a.registro_id
        LEFT JOIN Prescripciones rx
          ON a.tabla_afectada='Prescripciones' AND rx.id=a.registro_id
    """
    paciente_expr = """
        CASE
          WHEN a.tabla_afectada='Pacientes' THEN a.registro_id
          WHEN a.tabla_afectada='ConsultasClinicas' THEN cc.paciente_id
          WHEN a.tabla_afectada='AntecedentesClinicos' THEN ac.paciente_id
          WHEN a.tabla_afectada='SignosVitales' THEN sv.paciente_id
          WHEN a.tabla_afectada='Prescripciones' THEN rx.paciente_id
          ELSE NULL
        END
    """
    filtros.append(f"({paciente_expr}) IS NOT NULL")
    if pid:
        filtros.append(f"({paciente_expr})=?")
        args.append(pid)
    if usuario:
        filtros.append("a.usuario_nombre LIKE ?")
        args.append(f"%{usuario}%")
    if desde:
        filtros.append("date(a.fecha_hora)>=date(?)")
        args.append(desde)
    if hasta:
        filtros.append("date(a.fecha_hora)<=date(?)")
        args.append(hasta)
    with conectar() as c:
        return c.execute(f"""
            SELECT a.id, a.fecha_hora, a.usuario_nombre, a.tabla_afectada,
                   a.registro_id, a.tipo_accion, a.descripcion,
                   ({paciente_expr}) AS paciente_id
            FROM Auditoria a
            {joins}
            WHERE {' AND '.join(filtros)}
            ORDER BY a.fecha_hora DESC, a.id DESC
            LIMIT 1000
        """, args).fetchall()


class HCE(tk.Tk):
    def __init__(self, usuario):
        super().__init__()
        self.usuario = usuario
        self.paciente_id = None
        self.paciente_nombre = ""
        self.antecedente_seleccionado = None
        self.profesionales = {}
        self.title("OpenHIS-UNLaM | Historia Clínica Electrónica")
        self.geometry("1380x900")
        self.minsize(1120, 740)
        self.configure(bg="#eef3f8")
        self.buscar_txt = tk.StringVar()
        self.fecha_desde = tk.StringVar()
        self.fecha_hasta = tk.StringVar()
        self.filtro_usuario = tk.StringVar()
        self.tipo_antecedente = tk.StringVar(value="PERSONAL")
        self._estilos()
        self.armar()
        self.buscar()
        self.cargar_profesionales()

    def _estilos(self):
        st = ttk.Style(self)
        try: st.theme_use("clam")
        except tk.TclError: pass
        st.configure("TFrame", background="#eef3f8")
        st.configure("Card.TFrame", background="#ffffff")
        st.configure("TLabel", background="#eef3f8", foreground="#243447", font=("Segoe UI", 10))
        st.configure("Card.TLabel", background="#ffffff", foreground="#243447", font=("Segoe UI", 10))
        st.configure("Title.TLabel", background="#123456", foreground="white", font=("Segoe UI", 19, "bold"))
        st.configure("SubTitle.TLabel", background="#123456", foreground="#d8e7f5", font=("Segoe UI", 10))
        st.configure("Section.TLabel", background="#ffffff", foreground="#123456", font=("Segoe UI", 12, "bold"))
        st.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 7), background="#087e8b", foreground="white")
        st.map("Accent.TButton", background=[("active", "#066873")], foreground=[("active", "white")])
        st.configure("Treeview", font=("Segoe UI", 9), rowheight=27, background="white", fieldbackground="white")
        st.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#dce8f2", foreground="#123456", padding=6)
        st.map("Treeview", background=[("selected", "#c8e6eb")], foreground=[("selected", "#123456")])

    def card(self, parent, padding=10):
        return ttk.Frame(parent, style="Card.TFrame", padding=padding)

    def armar(self):
        header = tk.Frame(self, bg="#123456", height=82)
        header.pack(fill="x"); header.pack_propagate(False)
        left = tk.Frame(header, bg="#123456"); left.pack(side="left", padx=22, pady=12)
        ttk.Label(left, text="Historia Clínica Electrónica", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="Información asistencial integrada y trazable", style="SubTitle.TLabel").pack(anchor="w", pady=(3,0))
        tk.Label(header, text="OpenHIS\nUNLaM", bg="#123456", fg="white", font=("Segoe UI", 11, "bold")).pack(side="right", padx=24)
        bar = tk.Frame(self, bg="#dce8f2", height=32); bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text=f"  Sesión: {self.usuario['usuario']}   •   Perfil: {self.usuario['rol']}   •   Información confidencial",
                 bg="#dce8f2", fg="#34506b", font=("Segoe UI", 9)).pack(side="left", pady=6)

        body = ttk.Frame(self, padding=14); body.pack(fill="both", expand=True)
        search = self.card(body); search.pack(fill="x", pady=(0,9))
        ttk.Label(search, text="Buscar paciente", style="Section.TLabel").pack(anchor="w")
        row = ttk.Frame(search, style="Card.TFrame"); row.pack(fill="x", pady=(7,0))
        ttk.Label(row, text="DNI, apellido o nombre:", style="Card.TLabel").pack(side="left")
        ent = ttk.Entry(row, textvariable=self.buscar_txt, width=38); ent.pack(side="left", padx=8)
        ent.bind("<Return>", lambda _e: self.buscar())
        ttk.Button(row, text="Buscar", style="Accent.TButton", command=self.buscar).pack(side="left")
        ttk.Button(row, text="Limpiar", command=self.limpiar_busqueda).pack(side="left", padx=6)

        result = self.card(body, 8); result.pack(fill="x", pady=(0,9))
        ttk.Label(result, text="Resultados", style="Section.TLabel").pack(anchor="w", pady=(0,5))
        self.pacientes = ttk.Treeview(result, columns=("dni","paciente","nacimiento"), show="headings", height=3)
        for col,title,width in [("dni","DNI",140),("paciente","Paciente",430),("nacimiento","Fecha de nacimiento",170)]:
            self.pacientes.heading(col,text=title); self.pacientes.column(col,width=width,anchor="w")
        self.pacientes.pack(fill="x")
        self.pacientes.bind("<<TreeviewSelect>>", self.seleccionar_paciente)

        self.banner = tk.Label(body, text="Seleccione un paciente para consultar su historia clínica.",
                               bg="#e3f2f4", fg="#14505a", font=("Segoe UI",10,"bold"), anchor="w", padx=12,pady=9)
        self.banner.pack(fill="x", pady=(0,9))

        self.tabs = ttk.Notebook(body); self.tabs.pack(fill="both",expand=True)
        self.tab_timeline = ttk.Frame(self.tabs,padding=9)
        self.tab_antecedentes = ttk.Frame(self.tabs,padding=9)
        self.tabs.add(self.tab_timeline,text="Línea de tiempo")
        self.tabs.add(self.tab_antecedentes,text="Antecedentes")
        if self.usuario["rol"].lower() in ROLES_REGISTRO:
            self.tab_consulta = ttk.Frame(self.tabs,padding=12)
            self.tabs.add(self.tab_consulta,text="Registrar consulta")
        if self.usuario["rol"].lower() in ROLES_AUDITORIA:
            self.tab_auditoria = ttk.Frame(self.tabs,padding=9)
            self.tabs.add(self.tab_auditoria,text="Trazabilidad")
        self.armar_timeline()
        self.armar_antecedentes()
        if hasattr(self,"tab_consulta"): self.armar_consulta()
        if hasattr(self,"tab_auditoria"): self.armar_auditoria()

    def armar_timeline(self):
        top=ttk.Frame(self.tab_timeline); top.pack(fill="x")
        ttk.Label(top,text="Registros asistenciales ordenados por fecha",font=("Segoe UI",11,"bold")).pack(side="left")
        ttk.Button(top,text="Actualizar",command=self.cargar_timeline).pack(side="right")
        pan=ttk.Panedwindow(self.tab_timeline,orient="vertical");pan.pack(fill="both",expand=True,pady=(8,0))
        upper=ttk.Frame(pan);lower=ttk.Frame(pan)
        pan.add(upper,weight=3);pan.add(lower,weight=2)
        self.timeline=ttk.Treeview(upper,columns=("fecha","tipo","resumen","profesional"),show="headings")
        for col,title,width in [("fecha","Fecha y hora",155),("tipo","Tipo de registro",145),("resumen","Descripción",440),("profesional","Profesional responsable",220)]:
            self.timeline.heading(col,text=title);self.timeline.column(col,width=width,anchor="w")
        self.timeline.pack(fill="both",expand=True)
        self.timeline.bind("<<TreeviewSelect>>",self.ver_evento)
        ttk.Label(lower,text="Detalle del registro",font=("Segoe UI",10,"bold")).pack(anchor="w",pady=(4,3))
        self.timeline_detail=tk.Text(lower,height=7,wrap="word",state="disabled",bg="#f7f9fc",relief="flat",font=("Segoe UI",10),padx=9,pady=7)
        self.timeline_detail.pack(fill="both",expand=True)

    def armar_antecedentes(self):
        pan=ttk.Panedwindow(self.tab_antecedentes,orient="horizontal");pan.pack(fill="both",expand=True)
        left=ttk.Frame(pan,padding=4);right=ttk.Frame(pan,padding=10)
        pan.add(left,weight=3);pan.add(right,weight=2)
        ttk.Label(left,text="Antecedentes registrados",font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(0,6))
        self.antecedentes=ttk.Treeview(left,columns=("tipo","descripcion","fecha","profesional"),show="headings")
        for col,title,width in [("tipo","Tipo",100),("descripcion","Descripción",310),("fecha","Fecha",145),("profesional","Profesional",180)]:
            self.antecedentes.heading(col,text=title);self.antecedentes.column(col,width=width,anchor="w")
        self.antecedentes.pack(fill="both",expand=True)
        self.antecedentes.bind("<<TreeviewSelect>>",self.seleccionar_antecedente)
        ttk.Label(right,text="Registrar o actualizar antecedente",font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(0,9))
        ttk.Label(right,text="Categoría").pack(anchor="w")
        self.tipo_combo=ttk.Combobox(right,textvariable=self.tipo_antecedente,values=("PERSONAL","FAMILIAR"),state="readonly")
        self.tipo_combo.pack(fill="x",pady=(3,8))
        ttk.Label(right,text="Descripción").pack(anchor="w")
        self.antecedente_text=tk.Text(right,height=10,wrap="word",font=("Segoe UI",10),padx=7,pady=6)
        self.antecedente_text.pack(fill="both",expand=True,pady=(3,8))
        self.prof_antecedente=ttk.Combobox(right,state="readonly")
        ttk.Label(right,text="Profesional responsable").pack(anchor="w")
        self.prof_antecedente.pack(fill="x",pady=(3,8))
        actions=ttk.Frame(right);actions.pack(fill="x")
        ttk.Button(actions,text="Nuevo",command=self.nuevo_antecedente).pack(side="left")
        ttk.Button(actions,text="Guardar",style="Accent.TButton",command=self.guardar_antecedente_ui).pack(side="right")

    def armar_consulta(self):
        ttk.Label(self.tab_consulta,text="Registrar consulta y evolución clínica",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(0,10))
        form=ttk.Frame(self.tab_consulta);form.pack(fill="both",expand=True)
        ttk.Label(form,text="Profesional responsable").grid(row=0,column=0,sticky="w",pady=5)
        self.prof_consulta=ttk.Combobox(form,state="readonly",width=48)
        self.prof_consulta.grid(row=0,column=1,sticky="ew",padx=8,pady=5)
        ttk.Label(form,text="Fecha y hora (AAAA-MM-DD HH:MM)").grid(row=1,column=0,sticky="w",pady=5)
        self.fecha_consulta=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d %H:%M"))
        ttk.Entry(form,textvariable=self.fecha_consulta,width=25).grid(row=1,column=1,sticky="w",padx=8,pady=5)
        self.campos_consulta={}
        for fila,(clave,titulo) in enumerate((("motivo","Motivo de consulta"),("evaluacion","Evaluación"),("evolucion","Evolución")),2):
            ttk.Label(form,text=titulo).grid(row=fila,column=0,sticky="nw",pady=6)
            campo=tk.Text(form,height=4,wrap="word",font=("Segoe UI",10),padx=7,pady=5)
            campo.grid(row=fila,column=1,sticky="nsew",padx=8,pady=6)
            self.campos_consulta[clave]=campo
        form.columnconfigure(1,weight=1)
        for fila in (2,3,4):form.rowconfigure(fila,weight=1)
        ttk.Button(form,text="Guardar consulta",style="Accent.TButton",command=self.guardar_consulta_ui).grid(row=5,column=1,sticky="e",pady=10)

    def guardar_consulta_ui(self):
        try:
            if not self.paciente_id:raise ValueError("Seleccione primero un paciente.")
            profid=self.profesionales.get(self.prof_consulta.get())
            if not profid:raise ValueError("Seleccione el profesional responsable.")
            fecha=datetime.strptime(self.fecha_consulta.get().strip(),"%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
            datos={k:w.get("1.0","end").strip() for k,w in self.campos_consulta.items()}
            if not all(datos.values()):raise ValueError("Motivo, evaluación y evolución son obligatorios.")
            with conectar() as c:
                c.execute("BEGIN IMMEDIATE")
                cur=c.execute("""INSERT INTO ConsultasClinicas
                    (paciente_id,profesional_id,fecha_hora,motivo_consulta,evaluacion,evolucion,usuario_registro_id)
                    VALUES (?,?,?,?,?,?,?)""",
                    (self.paciente_id,profid,fecha,datos["motivo"],datos["evaluacion"],datos["evolucion"],self.usuario["id"]))
                cid=cur.lastrowid
                registrar_auditoria(c,self.usuario["id"],"ConsultasClinicas",cid,"A",
                                    "Registro de consulta/evolución clínica",None,
                                    {"paciente_id":self.paciente_id,"profesional_id":profid,"fecha_hora":fecha,**datos})
            for w in self.campos_consulta.values():w.delete("1.0","end")
            self.cargar_timeline()
            messagebox.showinfo("Consulta registrada","La consulta clínica se guardó correctamente.",parent=self)
        except Exception as exc:messagebox.showerror("No se pudo guardar",str(exc),parent=self)

    def armar_auditoria(self):
        top=ttk.Frame(self.tab_auditoria);top.pack(fill="x",pady=(0,8))
        ttk.Label(top,text="Trazabilidad de accesos y modificaciones",font=("Segoe UI",11,"bold")).pack(anchor="w")
        filters=ttk.Frame(self.tab_auditoria);filters.pack(fill="x",pady=5)
        ttk.Label(filters,text="Usuario").pack(side="left")
        ttk.Entry(filters,textvariable=self.filtro_usuario,width=18).pack(side="left",padx=5)
        ttk.Label(filters,text="Desde (AAAA-MM-DD)").pack(side="left")
        ttk.Entry(filters,textvariable=self.fecha_desde,width=13).pack(side="left",padx=5)
        ttk.Label(filters,text="Hasta").pack(side="left")
        ttk.Entry(filters,textvariable=self.fecha_hasta,width=13).pack(side="left",padx=5)
        ttk.Button(filters,text="Filtrar",style="Accent.TButton",command=self.cargar_auditoria).pack(side="left",padx=5)
        ttk.Button(filters,text="Limpiar",command=self.limpiar_filtros_auditoria).pack(side="left")
        self.audit_tree=ttk.Treeview(self.tab_auditoria,columns=("fecha","usuario","accion","tabla","registro","descripcion"),show="headings")
        for col,title,width in [("fecha","Fecha y hora",150),("usuario","Usuario",140),("accion","Acción",100),("tabla","Origen",150),("registro","Registro",80),("descripcion","Descripción",420)]:
            self.audit_tree.heading(col,text=title);self.audit_tree.column(col,width=width,anchor="w")
        self.audit_tree.pack(fill="both",expand=True)
        ttk.Label(self.tab_auditoria,text="La consulta se limita a los registros vinculados al paciente seleccionado.",
                  foreground="#52677c").pack(anchor="w",pady=(6,0))

    def cargar_profesionales(self):
        with conectar() as c:
            rows=c.execute("SELECT id,apellido,nombre,matricula FROM Profesionales WHERE activo=1 ORDER BY apellido,nombre").fetchall()
        self.profesionales={f"{r['apellido']}, {r['nombre']} | Matrícula {r['matricula']}":r["id"] for r in rows}
        if hasattr(self,"prof_antecedente"): self.prof_antecedente["values"]=list(self.profesionales)
        if hasattr(self,"prof_consulta"): self.prof_consulta["values"]=list(self.profesionales)

    def buscar(self):
        term="%"+self.buscar_txt.get().strip()+"%"
        self.pacientes.delete(*self.pacientes.get_children())
        with conectar() as c:
            rows=c.execute("""SELECT id,dni,apellido,nombre,fecha_nacimiento FROM Pacientes
                              WHERE activo=1 AND (dni LIKE ? OR apellido LIKE ? OR nombre LIKE ?)
                              ORDER BY apellido,nombre LIMIT 100""",(term,term,term)).fetchall()
        for r in rows:
            self.pacientes.insert("","end",iid=str(r["id"]),values=(r["dni"],r["apellido"]+", "+r["nombre"],r["fecha_nacimiento"]))

    def limpiar_busqueda(self):
        self.buscar_txt.set("");self.buscar()

    def seleccionar_paciente(self,_=None):
        sel=self.pacientes.selection()
        if not sel:return
        pid=int(sel[0])
        try:
            with conectar() as c:
                p=c.execute("SELECT * FROM Pacientes WHERE id=? AND activo=1",(pid,)).fetchone()
            if not p: raise ValueError("El paciente ya no está activo.")
            self.paciente_id=pid;self.paciente_nombre=f"{p['apellido']}, {p['nombre']}"
            self.banner.config(text=f"PACIENTE: {self.paciente_nombre}   |   DNI: {p['dni']}   |   Nacimiento: {p['fecha_nacimiento']}   |   Sexo: {p['sexo']}")
            auditar_lectura(self.usuario["id"],pid)
            self.cargar_timeline();self.cargar_antecedentes()
            if hasattr(self,"tab_auditoria"):self.cargar_auditoria()
        except Exception as exc:messagebox.showerror("Historia Clínica",str(exc),parent=self)

    def cargar_timeline(self):
        if not self.paciente_id:return
        self.timeline.delete(*self.timeline.get_children());self.eventos={}
        for i,e in enumerate(obtener_linea_tiempo(self.paciente_id)):
            iid=str(i);self.eventos[iid]=e
            self.timeline.insert("","end",iid=iid,values=(e["fecha"],e["tipo"],e["resumen"],e["profesional"]))
        self.detalle_timeline("Seleccione un registro para ver el detalle.")

    def detalle_timeline(self,texto):
        self.timeline_detail.config(state="normal");self.timeline_detail.delete("1.0","end")
        self.timeline_detail.insert("1.0",texto);self.timeline_detail.config(state="disabled")

    def ver_evento(self,_=None):
        sel=self.timeline.selection()
        if sel:self.detalle_timeline(self.eventos[sel[0]]["detalle"])

    def cargar_antecedentes(self):
        if not self.paciente_id:return
        self.antecedentes.delete(*self.antecedentes.get_children());self.antecedente_rows={}
        for r in obtener_antecedentes(self.paciente_id):
            iid=str(r["id"]);self.antecedente_rows[iid]=dict(r)
            self.antecedentes.insert("","end",iid=iid,values=(r["tipo"],r["descripcion"],r["fecha_registro"],r["profesional"] or "No informado"))

    def seleccionar_antecedente(self,_=None):
        sel=self.antecedentes.selection()
        if not sel:return
        r=self.antecedente_rows[sel[0]];self.antecedente_seleccionado=int(sel[0])
        self.tipo_antecedente.set(r["tipo"])
        self.antecedente_text.delete("1.0","end");self.antecedente_text.insert("1.0",r["descripcion"])
        for nombre,pid in self.profesionales.items():
            if pid==r["profesional_id"]:self.prof_antecedente.set(nombre);break

    def nuevo_antecedente(self):
        self.antecedente_seleccionado=None;self.tipo_antecedente.set("PERSONAL")
        self.antecedente_text.delete("1.0","end");self.prof_antecedente.set("")

    def guardar_antecedente_ui(self):
        try:
            if not self.paciente_id:raise ValueError("Seleccione un paciente.")
            if self.usuario["rol"].lower() not in ROLES_REGISTRO:raise PermissionError("Su perfil no puede registrar antecedentes.")
            profid=self.profesionales.get(self.prof_antecedente.get())
            aid=guardar_antecedente(self.usuario["id"],self.paciente_id,self.tipo_antecedente.get(),
                                    self.antecedente_text.get("1.0","end"),profid,self.antecedente_seleccionado)
            self.antecedente_seleccionado=aid;self.cargar_antecedentes()
            messagebox.showinfo("Antecedentes","El antecedente se guardó correctamente.",parent=self)

        except Exception as exc:messagebox.showerror("No se pudo guardar",str(exc),parent=self)

    def cargar_auditoria(self):
        if not self.paciente_id:return
        self.audit_tree.delete(*self.audit_tree.get_children())
        rows=obtener_auditoria(self.paciente_id,self.filtro_usuario.get().strip(),
                               self.fecha_desde.get().strip(),self.fecha_hasta.get().strip())
        for r in rows:
            accion={"A":"Alta","M":"Modificación","B":"Baja","R":"Reactivación",
                    "L":"Inicio de sesión","X":"Cierre de sesión","E":"Exportación",
                    "I":"Importación","C":"Consulta/otro evento"}.get(r["tipo_accion"],r["tipo_accion"])
            self.audit_tree.insert("","end",values=(r["fecha_hora"],r["usuario_nombre"] or "No informado",
                accion,r["tabla_afectada"],r["registro_id"],r["descripcion"] or ""))

    def limpiar_filtros_auditoria(self):
        self.filtro_usuario.set("");self.fecha_desde.set("");self.fecha_hasta.set("");self.cargar_auditoria()


def iniciar():
    try:
        usuario=obtener_sesion()
        asegurar_estructura()
        with conectar() as c:
            existe=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ConsultasClinicas'").fetchone()
        if not existe:raise RuntimeError("Primero debe instalarse la Historia Clínica Electrónica.")
    except Exception as exc:
        root=tk.Tk();root.withdraw();messagebox.showerror("OpenHIS-UNLaM | Historia Clínica",str(exc));root.destroy();return
    HCE(usuario).mainloop()


if __name__=="__main__":
    iniciar()
