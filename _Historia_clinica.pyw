# -*- coding: utf-8 -*-
"""OpenHIS-UNLaM | Sprint 9 | HU-19 y HU-20.
Consulta de HCE y registro de consultas/evoluciones. No reemplaza los módulos anteriores.
"""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / 'BD' / 'Salud.db'
ROLES_CONSULTA = {'admin', 'medico', 'enfermero'}
ROLES_REGISTRO = {'admin', 'medico'}


def conectar():
    if not DB_PATH.exists():
        raise FileNotFoundError(f'No se encontró la base de datos: {DB_PATH}')
    c = sqlite3.connect(str(DB_PATH), timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c


def sesion_autorizada():
    # Se obtiene el ID del usuario de la sesión creada por el menú principal.
    from Auditoria_utiles import obtener_usuario_actual
    sesion = obtener_usuario_actual()
    if isinstance(sesion, dict):
        uid = sesion.get('usuario_id') or sesion.get('id')
    elif isinstance(sesion, (tuple, list)):
        uid = sesion[0] if sesion else None
    else:
        uid = sesion if isinstance(sesion, int) else None
    if not uid:
        raise PermissionError('No se identificó una sesión válida. Inicie sesión desde el menú principal.')
    with conectar() as c:
        u = c.execute('SELECT id, usuario, rol FROM Usuarios WHERE id=? AND activo=1', (uid,)).fetchone()
    if not u or u['rol'].lower() not in ROLES_CONSULTA:
        raise PermissionError('Usuario sin permiso para consultar historias clínicas.')
    return dict(u)


def auditar_acceso(uid, pid):
    # La HU-23 incorporará la auditoría clínica específica en Sprint 10.
    # Aquí dejamos un registro básico de lectura en la tabla Auditoria existente.
    with conectar() as c:
        c.execute('''INSERT INTO Auditoria(usuario_id,usuario_nombre,tabla_afectada,registro_id,
                     tipo_accion,descripcion,origen_sistema)
                     VALUES (?,(SELECT nombre_completo FROM Usuarios WHERE id=?),?,?,?,?,?)''',
                  (uid, uid, 'Pacientes', pid, 'C', 'Acceso a HCE de paciente', 'OpenHIS-UNLaM'))


def guardar_consulta(uid, pid, profid, fecha_hora, motivo, evaluacion, evolucion):
    fecha_hora = datetime.strptime(fecha_hora.strip(), '%Y-%m-%d %H:%M').strftime('%Y-%m-%d %H:%M')
    campos = [motivo.strip(), evaluacion.strip(), evolucion.strip()]
    if not all(campos):
        raise ValueError('Motivo, evaluación y evolución son obligatorios.')
    with conectar() as c:
        c.execute('BEGIN IMMEDIATE')
        p = c.execute('SELECT id FROM Pacientes WHERE id=? AND activo=1', (pid,)).fetchone()
        pr = c.execute('SELECT id FROM Profesionales WHERE id=? AND activo=1', (profid,)).fetchone()
        u = c.execute('SELECT rol FROM Usuarios WHERE id=? AND activo=1', (uid,)).fetchone()
        if not p or not pr or not u or u['rol'].lower() not in ROLES_REGISTRO:
            raise PermissionError('Paciente, profesional o usuario no habilitado.')
        cur = c.execute('''INSERT INTO ConsultasClinicas
             (paciente_id, profesional_id, fecha_hora, motivo_consulta, evaluacion, evolucion, usuario_registro_id)
             VALUES (?,?,?,?,?,?,?)''', (pid, profid, fecha_hora, *campos, uid))
        cid = cur.lastrowid
        c.execute('''INSERT INTO Auditoria(usuario_id,usuario_nombre,tabla_afectada,registro_id,
                     tipo_accion,descripcion,origen_sistema)
                     VALUES (?,(SELECT nombre_completo FROM Usuarios WHERE id=?),?,?,?,?,?)''',
                  (uid, uid, 'ConsultasClinicas', cid, 'A', 'Registro de consulta/evolución clínica', 'OpenHIS-UNLaM'))
    return cid


class HCE(tk.Tk):
    # Interfaz clínica: las referencias de desarrollo quedan en el código,
    # pero no se muestran al usuario final.
    def __init__(self, usuario):
        super().__init__()
        self.usuario = usuario
        self.paciente_id = None
        self.title('OpenHIS-UNLaM | Historia Clínica Electrónica')
        self.geometry('1280x850')
        self.minsize(1050, 720)
        self.configure(bg='#eef3f8')
        self.buscar_txt = tk.StringVar()
        self.fecha_txt = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d %H:%M'))
        self.profesionales = {}
        self._estilos()
        self.armar()
        self.buscar()
        self.cargar_profesionales()

    def _estilos(self):
        st = ttk.Style(self)
        try: st.theme_use('clam')
        except tk.TclError: pass
        st.configure('TFrame', background='#eef3f8')
        st.configure('Card.TFrame', background='#ffffff')
        st.configure('TLabel', background='#eef3f8', foreground='#243447', font=('Segoe UI', 10))
        st.configure('Card.TLabel', background='#ffffff', foreground='#243447', font=('Segoe UI', 10))
        st.configure('Title.TLabel', background='#123456', foreground='white', font=('Segoe UI', 19, 'bold'))
        st.configure('SubTitle.TLabel', background='#123456', foreground='#d8e7f5', font=('Segoe UI', 10))
        st.configure('Section.TLabel', background='#ffffff', foreground='#123456', font=('Segoe UI', 12, 'bold'))
        st.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'), padding=(14, 8), background='#087e8b', foreground='white')
        st.map('Accent.TButton', background=[('active', '#066873')], foreground=[('active', 'white')])
        st.configure('TButton', font=('Segoe UI', 9), padding=(10, 6))
        st.configure('Treeview', font=('Segoe UI', 9), rowheight=29, background='white', fieldbackground='white')
        st.configure('Treeview.Heading', font=('Segoe UI', 9, 'bold'), background='#dce8f2', foreground='#123456', padding=7)
        st.map('Treeview', background=[('selected', '#c8e6eb')], foreground=[('selected', '#123456')])
        st.configure('TEntry', padding=7)
        st.configure('TCombobox', padding=6)

    def _card(self, parent, padding=12):
        return ttk.Frame(parent, style='Card.TFrame', padding=padding)

    def armar(self):
        # Encabezado institucional
        header = tk.Frame(self, bg='#123456', height=88)
        header.pack(fill='x')
        header.pack_propagate(False)
        left = tk.Frame(header, bg='#123456')
        left.pack(side='left', fill='y', padx=24, pady=13)
        ttk.Label(left, text='Historia Clínica Electrónica', style='Title.TLabel').pack(anchor='w')
        ttk.Label(left, text='Registro y consulta segura de información clínica', style='SubTitle.TLabel').pack(anchor='w', pady=(3, 0))
        tk.Label(header, text='OpenHIS\nUNLaM', bg='#123456', fg='#ffffff', font=('Segoe UI', 11, 'bold'), justify='right').pack(side='right', padx=25)

        userbar = tk.Frame(self, bg='#dce8f2', height=34)
        userbar.pack(fill='x'); userbar.pack_propagate(False)
        tk.Label(userbar, text=f"  Sesión: {self.usuario['usuario']}   •   Perfil: {self.usuario['rol']}   •   Información confidencial",
                 bg='#dce8f2', fg='#34506b', font=('Segoe UI', 9)).pack(side='left', pady=7)

        body = ttk.Frame(self, padding=(18, 14, 18, 14))
        body.pack(fill='both', expand=True)

        # Búsqueda y resultados de pacientes
        search_card = self._card(body, 12)
        search_card.pack(fill='x', pady=(0, 12))
        ttk.Label(search_card, text='Buscar paciente', style='Section.TLabel').pack(anchor='w')
        searchrow = ttk.Frame(search_card, style='Card.TFrame')
        searchrow.pack(fill='x', pady=(8, 0))
        ttk.Label(searchrow, text='DNI, apellido o nombre:', style='Card.TLabel').pack(side='left')
        ent = ttk.Entry(searchrow, textvariable=self.buscar_txt, width=42)
        ent.pack(side='left', padx=10)
        ent.bind('<Return>', lambda _e: self.buscar())
        ttk.Button(searchrow, text='Buscar', style='Accent.TButton', command=self.buscar).pack(side='left')
        ttk.Button(searchrow, text='Limpiar', command=self.limpiar_busqueda).pack(side='left', padx=7)

        patient_card = self._card(body, 10)
        patient_card.pack(fill='x', pady=(0, 12))
        ttk.Label(patient_card, text='Resultados', style='Section.TLabel').pack(anchor='w', pady=(0, 7))
        self.pacientes = ttk.Treeview(patient_card, columns=('dni','paciente','nacimiento'), show='headings', height=4)
        for col, title, width in [('dni','DNI',150),('paciente','Paciente',520),('nacimiento','Fecha de nacimiento',180)]:
            self.pacientes.heading(col, text=title); self.pacientes.column(col, width=width, anchor='w')
        self.pacientes.pack(fill='x')
        self.pacientes.bind('<<TreeviewSelect>>', self.seleccionar_paciente)

        # Datos e historial
        self.patient_banner = tk.Frame(body, bg='#e3f2f4', padx=14, pady=10)
        self.patient_banner.pack(fill='x', pady=(0, 12))
        self.datos = tk.Label(self.patient_banner, text='Seleccione un paciente para consultar su historia clínica.',
                              bg='#e3f2f4', fg='#14505a', font=('Segoe UI', 10, 'bold'), anchor='w', justify='left')
        self.datos.pack(fill='x')

        mid = ttk.Frame(body)
        mid.pack(fill='both', expand=True, pady=(0, 12))
        history_card = self._card(mid, 10)
        history_card.pack(side='left', fill='both', expand=True, padx=(0, 7))
        ttk.Label(history_card, text='Antecedentes de consultas', style='Section.TLabel').pack(anchor='w', pady=(0, 7))
        self.historial = ttk.Treeview(history_card, columns=('fecha','profesional','motivo'), show='headings', height=7)
        for col, title, width in [('fecha','Fecha y hora',155),('profesional','Profesional',220),('motivo','Motivo de consulta',420)]:
            self.historial.heading(col, text=title); self.historial.column(col, width=width, anchor='w')
        self.historial.pack(fill='both', expand=True)
        self.historial.bind('<<TreeviewSelect>>', self.ver_consulta)

        detail_card = self._card(mid, 10)
        detail_card.pack(side='left', fill='both', expand=True, padx=(7, 0))
        ttk.Label(detail_card, text='Detalle clínico', style='Section.TLabel').pack(anchor='w', pady=(0, 7))
        self.detalle = tk.Text(detail_card, height=9, wrap='word', state='disabled', relief='flat',
                               bg='#f7f9fc', fg='#263746', font=('Segoe UI', 10), padx=10, pady=9)
        self.detalle.pack(fill='both', expand=True)

        # Formulario de registro
        if self.usuario['rol'].lower() in ROLES_REGISTRO:
            f = self._card(body, 12)
            f.pack(fill='x')
            ttk.Label(f, text='Registrar consulta y evolución', style='Section.TLabel').grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 9))
            ttk.Label(f, text='Profesional', style='Card.TLabel').grid(row=1, column=0, sticky='w')
            self.prof = ttk.Combobox(f, state='readonly', width=42)
            self.prof.grid(row=1, column=1, sticky='ew', padx=(8, 18))
            ttk.Label(f, text='Fecha y hora', style='Card.TLabel').grid(row=1, column=2, sticky='w')
            ttk.Entry(f, textvariable=self.fecha_txt, width=21).grid(row=1, column=3, sticky='ew', padx=(8, 0))
            self.campos = {}
            for i, (clave, titulo) in enumerate([('motivo','Motivo de consulta'),('evaluacion','Evaluación'),('evolucion','Evolución')], 2):
                ttk.Label(f, text=titulo, style='Card.TLabel').grid(row=i, column=0, sticky='nw', pady=5)
                w = tk.Text(f, height=2, wrap='word', relief='solid', bd=1, bg='#fbfcfe',
                            fg='#263746', font=('Segoe UI', 10), padx=7, pady=5)
                w.grid(row=i, column=1, columnspan=3, sticky='ew', padx=(8, 0), pady=4)
                self.campos[clave] = w
            actions = ttk.Frame(f, style='Card.TFrame')
            actions.grid(row=5, column=0, columnspan=4, sticky='e', pady=(7, 0))
            ttk.Button(actions, text='Guardar consulta', style='Accent.TButton', command=self.guardar).pack(side='right')
            f.columnconfigure(1, weight=1); f.columnconfigure(3, weight=0)

    def limpiar_busqueda(self):
        self.buscar_txt.set('')
        self.buscar()

    def buscar(self):
        term = '%' + self.buscar_txt.get().strip() + '%'
        for item in self.pacientes.get_children(): self.pacientes.delete(item)
        with conectar() as c:
            rows = c.execute('''SELECT id,dni,apellido,nombre,fecha_nacimiento FROM Pacientes
                                WHERE activo=1 AND (dni LIKE ? OR apellido LIKE ? OR nombre LIKE ?)
                                ORDER BY apellido,nombre LIMIT 100''', (term,term,term)).fetchall()
        for r in rows:
            self.pacientes.insert('', 'end', iid=str(r['id']), values=(r['dni'],r['apellido']+', '+r['nombre'],r['fecha_nacimiento']))

    def seleccionar_paciente(self, _=None):
        sel = self.pacientes.selection()
        if not sel: return
        pid = int(sel[0])
        try:
            auditar_acceso(self.usuario['id'], pid)
            with conectar() as c:
                p = c.execute('SELECT * FROM Pacientes WHERE id=?', (pid,)).fetchone()
                rows = c.execute('''SELECT c.id,c.fecha_hora,c.motivo_consulta,
                    pr.apellido || ', ' || pr.nombre AS profesional
                    FROM ConsultasClinicas c JOIN Profesionales pr ON pr.id=c.profesional_id
                    WHERE c.paciente_id=? ORDER BY c.fecha_hora DESC,c.id DESC''', (pid,)).fetchall()
            self.paciente_id = pid
            self.datos.config(text=f"PACIENTE: {p['apellido']}, {p['nombre']}     |     DNI: {p['dni']}     |     Nacimiento: {p['fecha_nacimiento']}     |     Sexo: {p['sexo']}     |     Obra social: {p['obra_social'] or '-'}")
            for item in self.historial.get_children(): self.historial.delete(item)
            for r in rows: self.historial.insert('', 'end', iid=str(r['id']), values=(r['fecha_hora'],r['profesional'],r['motivo_consulta']))
            self.mostrar_detalle('Seleccione un registro del historial para visualizar la evaluación y evolución.')
        except Exception as exc: messagebox.showerror('Historia Clínica', str(exc))

    def mostrar_detalle(self, texto):
        self.detalle.config(state='normal'); self.detalle.delete('1.0','end')
        self.detalle.insert('1.0', texto); self.detalle.config(state='disabled')

    def ver_consulta(self, _=None):
        sel = self.historial.selection()
        if not sel or self.paciente_id is None: return
        with conectar() as c:
            r = c.execute('''SELECT c.*,p.apellido || ', ' || p.nombre AS profesional
                             FROM ConsultasClinicas c JOIN Profesionales p ON p.id=c.profesional_id
                             WHERE c.id=? AND c.paciente_id=?''', (int(sel[0]),self.paciente_id)).fetchone()
        if r: self.mostrar_detalle(f"Fecha: {r['fecha_hora']}\nProfesional: {r['profesional']}\n\nMotivo: {r['motivo_consulta']}\n\nEvaluación: {r['evaluacion']}\n\nEvolución: {r['evolucion']}")

    def cargar_profesionales(self):
        if not hasattr(self, 'prof'): return
        with conectar() as c:
            rows = c.execute('SELECT id,apellido,nombre,matricula FROM Profesionales WHERE activo=1 ORDER BY apellido,nombre').fetchall()
        self.profesionales = {f"{r['apellido']}, {r['nombre']} | Matrícula {r['matricula']} | ID {r['id']}":r['id'] for r in rows}
        self.prof['values'] = list(self.profesionales)

    def guardar(self):
        try:
            if self.paciente_id is None: raise ValueError('Seleccione primero un paciente.')
            profid = self.profesionales.get(self.prof.get())
            if profid is None: raise ValueError('Seleccione un profesional.')
            cid = guardar_consulta(self.usuario['id'], self.paciente_id, profid, self.fecha_txt.get(),
                    self.campos['motivo'].get('1.0','end'), self.campos['evaluacion'].get('1.0','end'),
                    self.campos['evolucion'].get('1.0','end'))
            messagebox.showinfo('Consulta registrada', 'La consulta clínica se guardó correctamente.')
            for w in self.campos.values(): w.delete('1.0','end')
            self.seleccionar_paciente()
        except Exception as exc: messagebox.showerror('No se pudo guardar', str(exc))

def iniciar():
    try:
        usuario=sesion_autorizada()
        with conectar() as c:
            existe=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ConsultasClinicas'").fetchone()
        if not existe: raise RuntimeError('Primero debe instalar la estructura de Historia Clínica en la base de datos.')
    except Exception as exc:
        root=tk.Tk();root.withdraw();messagebox.showerror('OpenHIS-UNLaM | Historia Clínica',str(exc));root.destroy();return
    HCE(usuario).mainloop()

if __name__=='__main__': iniciar()
