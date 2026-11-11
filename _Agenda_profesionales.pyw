# -*- coding: utf-8 -*-
"""
OpenHIS-UNLaM | Sprint 6
Agenda y disponibilidad profesional.

Este módulo permite:
- Configurar horarios semanales por profesional.
- Registrar bloqueos, vacaciones y licencias.
- Consultar los intervalos disponibles de una fecha.
En Sprint 7 se incorporará la reserva efectiva de turnos.
"""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime, date

BASE_DIR = Path(__file__).resolve().parent
RUTA_BD = BASE_DIR / "BD" / "Salud.db"
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
TIPOS_BLOQUEO = ["BLOQUEO", "VACACIONES", "LICENCIA", "OTRO"]


def conectar_bd():
    if not RUTA_BD.exists():
        raise FileNotFoundError(f"No se encontró la base de datos: {RUTA_BD}")
    con = sqlite3.connect(str(RUTA_BD))
    con.execute("PRAGMA foreign_keys = ON")
    return con

def listar_profesionales():
    with conectar_bd() as con:
        return con.execute("""
            SELECT p.id, p.nombre, p.apellido, COALESCE(e.nombre, 'Sin especialidad')
            FROM Profesionales p
            LEFT JOIN Especialidades e ON e.id = p.especialidad_id
            WHERE p.activo = 1
            ORDER BY p.apellido, p.nombre
        """).fetchall()


def auditar(funcion, tabla, registro_id, descripcion, datos=None, anteriores=None):
    try:
        from Auditoria_utiles import auditar_alta, auditar_modificacion, auditar_baja
        if funcion == "alta":
            auditar_alta(tabla, registro_id, descripcion, datos)
        elif funcion == "modificacion":
            auditar_modificacion(tabla, registro_id, descripcion, anteriores, datos)
        elif funcion == "baja":
            auditar_baja(tabla, registro_id, descripcion, datos)
    except Exception as exc:
        # La operación funcional no se revierte por un problema del módulo auxiliar.
        print(f"[ADVERTENCIA] No se pudo registrar auditoría: {exc}")


def validar_hora(valor, etiqueta):
    try:
        return datetime.strptime(valor.strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        raise ValueError(f"{etiqueta}: use formato HH:MM (por ejemplo, 08:30).")


def validar_fecha(valor):
    try:
        return datetime.strptime(valor.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError("La fecha debe tener formato AAAA-MM-DD (por ejemplo, 2026-11-10).")


class AgendaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OpenHIS-UNLaM | Agenda profesional")
        self.root.geometry("1120x740")
        self.root.minsize(940, 620)
        self.profesionales = listar_profesionales()
        self.prof_map = {}
        self._interfaz()
        self.refrescar_todo()

    def _interfaz(self):
        cab = ttk.Frame(self.root, padding=12)
        cab.pack(fill="x")
        ttk.Label(cab, text="AGENDA Y DISPONIBILIDAD PROFESIONAL",
                  font=("Arial", 16, "bold")).pack(anchor="w")
        ttk.Label(cab, text="OpenHIS-UNLaM",
                  font=("Arial", 10)).pack(anchor="w", pady=(3, 0))

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tab_disp = ttk.Frame(self.tabs, padding=12)
        self.tab_bloq = ttk.Frame(self.tabs, padding=12)
        self.tab_agenda = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.tab_disp, text="Disponibilidad semanal")
        self.tabs.add(self.tab_bloq, text="Bloqueos y excepciones")
        self.tabs.add(self.tab_agenda, text="Agenda del día")
        self._tab_disponibilidad()
        self._tab_bloqueos()
        self._tab_agenda()

    def _combo_profesionales(self, parent):
        cb = ttk.Combobox(parent, state="readonly", width=48)
        cb["values"] = [f"{p[0]} | {p[2]}, {p[1]} | {p[3]}" for p in self.profesionales]
        for p, etiqueta in zip(self.profesionales, cb["values"]):
            self.prof_map[etiqueta] = p[0]
        if cb["values"]:
            cb.current(0)
        return cb

    def _id_prof(self, combo):
        etiqueta = combo.get()
        if etiqueta not in self.prof_map:
            raise ValueError("Seleccione un profesional activo.")
        return self.prof_map[etiqueta]

    def _tab_disponibilidad(self):
        f = self.tab_disp
        form = ttk.LabelFrame(f, text="Definir horario semanal", padding=10)
        form.pack(fill="x")
        ttk.Label(form, text="Profesional").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.disp_prof = self._combo_profesionales(form)
        self.disp_prof.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(form, text="Día").grid(row=0, column=2, sticky="w", padx=4)
        self.disp_dia = ttk.Combobox(form, state="readonly", values=DIAS, width=15)
        self.disp_dia.grid(row=0, column=3, padx=4, pady=4)
        self.disp_dia.current(0)
        ttk.Label(form, text="Desde (HH:MM)").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.disp_inicio = ttk.Entry(form, width=12)
        self.disp_inicio.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        self.disp_inicio.insert(0, "08:00")
        ttk.Label(form, text="Hasta (HH:MM)").grid(row=1, column=2, sticky="w", padx=4)
        self.disp_fin = ttk.Entry(form, width=12)
        self.disp_fin.grid(row=1, column=3, sticky="w", padx=4, pady=4)
        self.disp_fin.insert(0, "12:00")
        ttk.Label(form, text="Duración de cada turno (minutos)").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.disp_duracion = ttk.Spinbox(form, from_=5, to=240, increment=5, width=10)
        self.disp_duracion.grid(row=2, column=1, sticky="w", padx=4, pady=4)
        self.disp_duracion.set("30")
        ttk.Button(form, text="Agregar horario", command=self.agregar_disponibilidad).grid(row=2, column=3, sticky="e", padx=4, pady=4)

        self.tree_disp = ttk.Treeview(f, columns=("prof", "dia", "desde", "hasta", "duracion"), show="headings", height=14)
        for c, t, w in [("prof","Profesional",250),("dia","Día",120),("desde","Desde",100),("hasta","Hasta",100),("duracion","Duración (min)",120)]:
            self.tree_disp.heading(c, text=t); self.tree_disp.column(c, width=w, anchor="w")
        self.tree_disp.pack(fill="both", expand=True, pady=10)
        ttk.Button(f, text="Desactivar horario seleccionado", command=self.desactivar_disponibilidad).pack(anchor="e")

    def _tab_bloqueos(self):
        f = self.tab_bloq
        form = ttk.LabelFrame(f, text="Registrar bloqueo o excepción", padding=10)
        form.pack(fill="x")
        ttk.Label(form, text="Profesional").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.bloq_prof = self._combo_profesionales(form)
        self.bloq_prof.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(form, text="Fecha (AAAA-MM-DD)").grid(row=0, column=2, sticky="w", padx=4)
        self.bloq_fecha = ttk.Entry(form, width=14)
        self.bloq_fecha.grid(row=0, column=3, padx=4, pady=4)
        self.bloq_fecha.insert(0, date.today().isoformat())
        ttk.Label(form, text="Desde (vacío = día completo)").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.bloq_inicio = ttk.Entry(form, width=12)
        self.bloq_inicio.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(form, text="Hasta").grid(row=1, column=2, sticky="w", padx=4)
        self.bloq_fin = ttk.Entry(form, width=12)
        self.bloq_fin.grid(row=1, column=3, padx=4, pady=4)
        ttk.Label(form, text="Tipo").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.bloq_tipo = ttk.Combobox(form, state="readonly", values=TIPOS_BLOQUEO, width=16)
        self.bloq_tipo.grid(row=2, column=1, sticky="w", padx=4, pady=4); self.bloq_tipo.current(0)
        ttk.Label(form, text="Motivo").grid(row=2, column=2, sticky="w", padx=4)
        self.bloq_motivo = ttk.Entry(form, width=34)
        self.bloq_motivo.grid(row=2, column=3, padx=4, pady=4)
        ttk.Button(form, text="Registrar bloqueo", command=self.agregar_bloqueo).grid(row=3, column=3, sticky="e", padx=4, pady=5)

        self.tree_bloq = ttk.Treeview(f, columns=("prof","fecha","desde","hasta","tipo","motivo"), show="headings", height=13)
        for c,t,w in [("prof","Profesional",220),("fecha","Fecha",105),("desde","Desde",85),("hasta","Hasta",85),("tipo","Tipo",110),("motivo","Motivo",230)]:
            self.tree_bloq.heading(c,text=t); self.tree_bloq.column(c,width=w,anchor="w")
        self.tree_bloq.pack(fill="both",expand=True,pady=10)
        ttk.Button(f, text="Desactivar bloqueo seleccionado", command=self.desactivar_bloqueo).pack(anchor="e")

    def _tab_agenda(self):
        f = self.tab_agenda
        filtros = ttk.LabelFrame(f, text="Consultar agenda", padding=10)
        filtros.pack(fill="x")
        ttk.Label(filtros, text="Profesional").grid(row=0,column=0,sticky="w",padx=4,pady=4)
        self.ag_prof = self._combo_profesionales(filtros)
        self.ag_prof.grid(row=0,column=1,sticky="w",padx=4,pady=4)
        ttk.Label(filtros, text="Fecha (AAAA-MM-DD)").grid(row=0,column=2,sticky="w",padx=4)
        self.ag_fecha = ttk.Entry(filtros,width=14)
        self.ag_fecha.grid(row=0,column=3,padx=4,pady=4)
        self.ag_fecha.insert(0,date.today().isoformat())
        ttk.Button(filtros,text="Consultar",command=self.consultar_agenda).grid(row=0,column=4,padx=8)
        self.lbl_agenda = ttk.Label(f,text="Seleccione un profesional y una fecha.")
        self.lbl_agenda.pack(anchor="w",pady=8)
        self.tree_ag = ttk.Treeview(f,columns=("hora","estado","detalle"),show="headings",height=17)
        for c,t,w in [("hora","Horario",140),("estado","Estado",160),("detalle","Detalle",550)]:
            self.tree_ag.heading(c,text=t); self.tree_ag.column(c,width=w,anchor="w")
        self.tree_ag.pack(fill="both",expand=True)
        ttk.Label(f,text="La agenda muestra disponibilidad; la reserva efectiva de turnos se incorporará en el Sprint 7.",
                  foreground="#555").pack(anchor="w",pady=8)

    def refrescar_todo(self):
        for tree in (self.tree_disp,self.tree_bloq):
            for item in tree.get_children(): tree.delete(item)
        with conectar_bd() as con:
            rows = con.execute("""
                SELECT d.id, p.nombre, p.apellido, d.dia_semana, d.hora_inicio, d.hora_fin, d.duracion_minutos
                FROM DisponibilidadProfesional d JOIN Profesionales p ON p.id=d.profesional_id
                WHERE d.activo=1 ORDER BY p.apellido,p.nombre,d.dia_semana,d.hora_inicio
            """).fetchall()
            for r in rows:
                self.tree_disp.insert("", "end", iid=f"d{r[0]}", values=(f"{r[2]}, {r[1]}",DIAS[r[3]],r[4],r[5],r[6]))
            rows = con.execute("""
                SELECT b.id,p.nombre,p.apellido,b.fecha,COALESCE(b.hora_inicio,'Todo el día'),
                       COALESCE(b.hora_fin,'Todo el día'),b.tipo,COALESCE(b.motivo,'')
                FROM BloqueosAgenda b JOIN Profesionales p ON p.id=b.profesional_id
                WHERE b.activo=1 ORDER BY b.fecha,p.apellido,p.nombre
            """).fetchall()
            for r in rows:
                self.tree_bloq.insert("", "end", iid=f"b{r[0]}", values=(f"{r[2]}, {r[1]}",r[3],r[4],r[5],r[6],r[7]))
        self.consultar_agenda(silencioso=True)

    def agregar_disponibilidad(self):
        try:
            pid=self._id_prof(self.disp_prof)
            dia=self.disp_dia.current()
            inicio=validar_hora(self.disp_inicio.get(),"Hora de inicio")
            fin=validar_hora(self.disp_fin.get(),"Hora de fin")
            dur=int(self.disp_duracion.get())
            if dia < 0: raise ValueError("Seleccione un día.")
            if inicio >= fin: raise ValueError("La hora de inicio debe ser anterior a la hora de fin.")
            if not 5 <= dur <= 240: raise ValueError("La duración debe estar entre 5 y 240 minutos.")
            with conectar_bd() as con:
                solapa=con.execute("""
                    SELECT 1 FROM DisponibilidadProfesional
                    WHERE profesional_id=? AND dia_semana=? AND activo=1
                      AND hora_inicio < ? AND hora_fin > ?
                """,(pid,dia,fin,inicio)).fetchone()
                if solapa: raise ValueError("El horario se superpone con otra disponibilidad activa de ese profesional.")
                cur=con.execute("""
                    INSERT INTO DisponibilidadProfesional
                    (profesional_id,dia_semana,hora_inicio,hora_fin,duracion_minutos)
                    VALUES (?,?,?,?,?)
                """,(pid,dia,inicio,fin,dur))
                rid=cur.lastrowid
            auditar("alta","DisponibilidadProfesional",rid,"Alta de disponibilidad semanal",
                    {"profesional_id":pid,"dia_semana":dia,"hora_inicio":inicio,"hora_fin":fin,"duracion_minutos":dur})
            self.refrescar_todo()
            messagebox.showinfo("Disponibilidad","Horario agregado correctamente.",parent=self.root)
        except Exception as e: messagebox.showerror("No se pudo agregar",str(e),parent=self.root)

    def desactivar_disponibilidad(self):
        sel=self.tree_disp.selection()
        if not sel: return messagebox.showwarning("Seleccione","Seleccione un horario.",parent=self.root)
        rid=int(sel[0][1:])
        if not messagebox.askyesno("Confirmar","¿Desea desactivar este horario? No se elimina el registro histórico.",parent=self.root): return
        with conectar_bd() as con:
            row=con.execute("SELECT profesional_id,dia_semana,hora_inicio,hora_fin,duracion_minutos FROM DisponibilidadProfesional WHERE id=? AND activo=1",(rid,)).fetchone()
            if not row: return
            con.execute("UPDATE DisponibilidadProfesional SET activo=0 WHERE id=?",(rid,))
        auditar("baja","DisponibilidadProfesional",rid,"Baja lógica de disponibilidad",{"profesional_id":row[0],"dia_semana":row[1],"hora_inicio":row[2],"hora_fin":row[3],"duracion_minutos":row[4]})
        self.refrescar_todo()

    def agregar_bloqueo(self):
        try:
            pid=self._id_prof(self.bloq_prof)
            fecha=validar_fecha(self.bloq_fecha.get())
            ini=self.bloq_inicio.get().strip(); fin=self.bloq_fin.get().strip()
            if bool(ini) != bool(fin): raise ValueError("Complete ambas horas o deje las dos vacías para bloquear todo el día.")
            if ini:
                ini=validar_hora(ini,"Hora desde"); fin=validar_hora(fin,"Hora hasta")
                if ini>=fin: raise ValueError("La hora desde debe ser anterior a la hora hasta.")
            tipo=self.bloq_tipo.get()
            if tipo not in TIPOS_BLOQUEO: raise ValueError("Seleccione un tipo de bloqueo.")
            motivo=self.bloq_motivo.get().strip()
            with conectar_bd() as con:
                cur=con.execute("""
                    INSERT INTO BloqueosAgenda
                    (profesional_id,fecha,hora_inicio,hora_fin,tipo,motivo)
                    VALUES (?,?,?,?,?,?)
                """,(pid,fecha,ini or None,fin or None,tipo,motivo))
                rid=cur.lastrowid
            auditar("alta","BloqueosAgenda",rid,"Alta de bloqueo o excepción",
                    {"profesional_id":pid,"fecha":fecha,"hora_inicio":ini or None,"hora_fin":fin or None,"tipo":tipo,"motivo":motivo})
            self.refrescar_todo()
            messagebox.showinfo("Agenda","Bloqueo registrado correctamente.",parent=self.root)
        except Exception as e: messagebox.showerror("No se pudo registrar",str(e),parent=self.root)

    def desactivar_bloqueo(self):
        sel=self.tree_bloq.selection()
        if not sel: return messagebox.showwarning("Seleccione","Seleccione un bloqueo.",parent=self.root)
        rid=int(sel[0][1:])
        if not messagebox.askyesno("Confirmar","¿Desea desactivar este bloqueo?",parent=self.root): return
        with conectar_bd() as con:
            row=con.execute("SELECT profesional_id,fecha,tipo,motivo FROM BloqueosAgenda WHERE id=? AND activo=1",(rid,)).fetchone()
            if not row: return
            con.execute("UPDATE BloqueosAgenda SET activo=0 WHERE id=?",(rid,))
        auditar("baja","BloqueosAgenda",rid,"Baja lógica de bloqueo o excepción",
                {"profesional_id":row[0],"fecha":row[1],"tipo":row[2],"motivo":row[3]})
        self.refrescar_todo()

    def consultar_agenda(self, silencioso=False):
        try:
            pid=self._id_prof(self.ag_prof)
            fecha=validar_fecha(self.ag_fecha.get())
            dia=date.fromisoformat(fecha).weekday()
            for item in self.tree_ag.get_children(): self.tree_ag.delete(item)
            with conectar_bd() as con:
                disp=con.execute("""
                    SELECT id,hora_inicio,hora_fin,duracion_minutos
                    FROM DisponibilidadProfesional
                    WHERE profesional_id=? AND dia_semana=? AND activo=1
                    ORDER BY hora_inicio
                """,(pid,dia)).fetchall()
                bloqueos=con.execute("""
                    SELECT hora_inicio,hora_fin,tipo,COALESCE(motivo,'')
                    FROM BloqueosAgenda
                    WHERE profesional_id=? AND fecha=? AND activo=1
                """,(pid,fecha)).fetchall()
            slots=0; bloqueados=0
            for did,ini,fin,duracion in disp:
                h0=datetime.strptime(ini,"%H:%M")
                hfin=datetime.strptime(fin,"%H:%M")
                while h0.timestamp() + duracion*60 <= hfin.timestamp():
                    h1=h0.replace()
                    from datetime import timedelta
                    h1=h0+timedelta(minutes=duracion)
                    sh=h0.strftime("%H:%M"); eh=h1.strftime("%H:%M")
                    motivo=None
                    for bi,bf,tipo,desc in bloqueos:
                        if bi is None or (sh < bf and eh > bi):
                            motivo=f"{tipo}: {desc}".strip(": ")
                            break
                    if motivo:
                        estado="No disponible"; detalle=motivo; bloqueados+=1
                    else:
                        estado="Disponible"; detalle="Intervalo libre (la reserva se implementará en Sprint 7)"
                    self.tree_ag.insert("", "end", values=(f"{sh} - {eh}",estado,detalle))
                    slots+=1
                    h0=h1
            self.lbl_agenda.config(text=f"Fecha: {fecha} | Día: {DIAS[dia]} | Intervalos: {slots} | Bloqueados: {bloqueados}")
            if not disp:
                self.tree_ag.insert("", "end", values=("-", "Sin disponibilidad", "No hay horarios semanales configurados para este día."))
        except Exception as e:
            if not silencioso: messagebox.showerror("Consulta de agenda",str(e),parent=self.root)


if __name__ == "__main__":
    root=tk.Tk()
    try:
        app=AgendaApp(root)
        root.mainloop()
    except Exception as exc:
        messagebox.showerror("OpenHIS-UNLaM",f"No se pudo iniciar el módulo:\n{exc}")
        raise
