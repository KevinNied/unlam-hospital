# -*- coding: utf-8 -*-
"""
OpenHIS-UNLaM | Sprint 7 - Gestión de Turnos
Requiere: Python 3, Tkinter y la base BD/Salud.db.
Integra la disponibilidad y los bloqueos del Sprint 6.
"""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime, date, timedelta

BASE_DIR = Path(__file__).resolve().parent
RUTA_BD = BASE_DIR / "BD" / "Salud.db"
ESTADOS = ("SOLICITADO", "CONFIRMADO", "CANCELADO", "REPROGRAMADO", "ATENDIDO", "AUSENTE")
ESTADOS_OCUPAN = ("SOLICITADO", "CONFIRMADO")
CANALES = ("TELEFONO", "WHATSAPP")
DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


def conectar():
    if not RUTA_BD.exists():
        raise FileNotFoundError(f"No se encontró la base de datos: {RUTA_BD}")
    con = sqlite3.connect(str(RUTA_BD), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=15000")
    return con


def auditar(tipo, rid, descripcion, datos=None, anteriores=None):
    try:
        from Auditoria_utiles import auditar_alta, auditar_modificacion
        if tipo == "A":
            resultado = auditar_alta("Turnos", rid, descripcion, datos)
        else:
            resultado = auditar_modificacion("Turnos", rid, descripcion, anteriores, datos)
        if isinstance(resultado, tuple) and resultado and resultado[0] is False:
            print("[ADVERTENCIA] Auditoría no registrada:", resultado)
    except Exception as exc:
        print(f"[ADVERTENCIA] No se pudo registrar auditoría: {exc}")


def validar_fecha(s):
    return datetime.strptime(s.strip(), "%Y-%m-%d").date().isoformat()


def validar_hora(s):
    return datetime.strptime(s.strip(), "%H:%M").strftime("%H:%M")


def obtener_catalogos():
    with conectar() as con:
        pacientes = con.execute("""
            SELECT id,dni,apellido,nombre FROM Pacientes
            WHERE activo=1 ORDER BY apellido,nombre
        """).fetchall()
        profesionales = con.execute("""
            SELECT p.id,p.apellido,p.nombre,COALESCE(e.nombre,'Sin especialidad') esp
            FROM Profesionales p LEFT JOIN Especialidades e ON e.id=p.especialidad_id
            WHERE p.activo=1 ORDER BY p.apellido,p.nombre
        """).fetchall()
    return pacientes, profesionales


def intervalos_disponibles(pid, fecha):
    dia = date.fromisoformat(fecha).weekday()
    with conectar() as con:
        disponibilidades = con.execute("""
            SELECT hora_inicio,hora_fin,duracion_minutos
            FROM DisponibilidadProfesional
            WHERE profesional_id=? AND dia_semana=? AND activo=1 ORDER BY hora_inicio
        """, (pid,dia)).fetchall()
        bloqueos = con.execute("""
            SELECT hora_inicio,hora_fin,tipo,motivo FROM BloqueosAgenda
            WHERE profesional_id=? AND fecha=? AND activo=1
        """, (pid,fecha)).fetchall()
        turnos = con.execute("""
            SELECT hora_inicio,hora_fin FROM Turnos
            WHERE profesional_id=? AND fecha=? AND estado IN ('SOLICITADO','CONFIRMADO')
        """, (pid,fecha)).fetchall()
    slots=[]
    for d in disponibilidades:
        cur=datetime.strptime(d["hora_inicio"],"%H:%M")
        fin=datetime.strptime(d["hora_fin"],"%H:%M")
        dur=int(d["duracion_minutos"])
        while cur + timedelta(minutes=dur) <= fin:
            nxt=cur+timedelta(minutes=dur)
            hi, hf=cur.strftime("%H:%M"),nxt.strftime("%H:%M")
            razon=None
            for b in bloqueos:
                if b["hora_inicio"] is None or (hi < b["hora_fin"] and hf > b["hora_inicio"]):
                    razon=f"{b['tipo']}: {b['motivo'] or 'bloqueo'}"; break
            if not razon:
                for t in turnos:
                    if hi < t["hora_fin"] and hf > t["hora_inicio"]:
                        razon="Ocupado por otro turno"; break
            slots.append((hi,hf,razon))
            cur=nxt
    return slots


class TurnosApp:
    def __init__(self, root):
        self.root=root
        self.root.title("OpenHIS-UNLaM | Sprint 7 - Gestión de Turnos")
        self.root.geometry("1250x790")
        self.root.minsize(1050,680)
        self.pacientes,self.profesionales=obtener_catalogos()
        self.pmap={f"{p['id']} | {p['apellido']}, {p['nombre']} ({p['dni']})":p["id"] for p in self.pacientes}
        self.prmap={f"{p['id']} | {p['apellido']}, {p['nombre']} - {p['esp']}":p["id"] for p in self.profesionales}
        self.turno_seleccionado=None
        self.interfaz()
        self.cargar_turnos()
        self.cargar_horarios()

    def interfaz(self):
        head=ttk.Frame(self.root,padding=12); head.pack(fill="x")
        ttk.Label(head,text="GESTIÓN DE TURNOS",font=("Arial",17,"bold")).pack(anchor="w")
        ttk.Label(head,text="OpenHIS-UNLaM | Solicitudes telefónicas y por WhatsApp").pack(anchor="w")
        nb=ttk.Notebook(self.root); nb.pack(fill="both",expand=True,padx=12,pady=(0,12))
        self.tab_alta=ttk.Frame(nb,padding=12); self.tab_lista=ttk.Frame(nb,padding=12)
        nb.add(self.tab_alta,text="Registrar turno"); nb.add(self.tab_lista,text="Consultar y gestionar")
        self._crear_alta(); self._crear_lista()

    def _crear_alta(self):
        f=self.tab_alta
        form=ttk.LabelFrame(f,text="Datos de la solicitud",padding=12); form.pack(fill="x")
        ttk.Label(form,text="Paciente").grid(row=0,column=0,sticky="w",padx=5,pady=6)
        self.cb_pac=ttk.Combobox(form,state="readonly",width=48,values=list(self.pmap))
        self.cb_pac.grid(row=0,column=1,sticky="w",padx=5,pady=6)
        ttk.Label(form,text="Profesional").grid(row=0,column=2,sticky="w",padx=5)
        self.cb_prof=ttk.Combobox(form,state="readonly",width=48,values=list(self.prmap))
        self.cb_prof.grid(row=0,column=3,sticky="w",padx=5,pady=6)
        ttk.Label(form,text="Fecha (AAAA-MM-DD)").grid(row=1,column=0,sticky="w",padx=5,pady=6)
        self.en_fecha=ttk.Entry(form,width=18); self.en_fecha.grid(row=1,column=1,sticky="w",padx=5)
        self.en_fecha.insert(0,date.today().isoformat())
        ttk.Button(form,text="Consultar horarios",command=self.cargar_horarios).grid(row=1,column=2,sticky="w",padx=5)
        ttk.Label(form,text="Horario disponible").grid(row=2,column=0,sticky="w",padx=5,pady=6)
        self.cb_hora=ttk.Combobox(form,state="readonly",width=22); self.cb_hora.grid(row=2,column=1,sticky="w",padx=5)
        ttk.Label(form,text="Canal de solicitud").grid(row=2,column=2,sticky="w",padx=5)
        self.cb_canal=ttk.Combobox(form,state="readonly",values=CANALES,width=18)
        self.cb_canal.grid(row=2,column=3,sticky="w",padx=5); self.cb_canal.current(0)
        ttk.Label(form,text="Motivo de consulta").grid(row=3,column=0,sticky="w",padx=5,pady=6)
        self.en_motivo=ttk.Entry(form,width=55); self.en_motivo.grid(row=3,column=1,columnspan=3,sticky="we",padx=5)
        ttk.Label(form,text="Observaciones administrativas").grid(row=4,column=0,sticky="w",padx=5,pady=6)
        self.en_obs=ttk.Entry(form,width=75); self.en_obs.grid(row=4,column=1,columnspan=3,sticky="we",padx=5)
        ttk.Button(form,text="Registrar solicitud de turno",command=self.registrar).grid(row=5,column=3,sticky="e",padx=5,pady=10)
        form.columnconfigure(1,weight=1); form.columnconfigure(3,weight=1)
        ttk.Label(f,text="El turno queda en estado SOLICITADO. La confirmación se registra posteriormente, indicando el canal utilizado.",wraplength=1050).pack(anchor="w",pady=14)
        ttk.Label(f,text="Importante: solo se ofrecen horarios definidos en disponibilidad y libres de bloqueos y otros turnos.",wraplength=1050).pack(anchor="w")

    def cargar_horarios(self):
        try:
            if not hasattr(self,"cb_hora"): return
            self.cb_hora.set(""); self.cb_hora["values"]=[]
            prof=self.cb_prof.get()
            if prof not in self.prmap: return
            fecha=validar_fecha(self.en_fecha.get())
            slots=intervalos_disponibles(self.prmap[prof],fecha)
            libres=[f"{a} - {b}" for a,b,r in slots if not r]
            self.cb_hora["values"]=libres
            if libres: self.cb_hora.current(0)
            else: self.cb_hora.set("Sin horarios disponibles")
        except Exception as e:
            messagebox.showerror("Disponibilidad",str(e),parent=self.root)

    def registrar(self):
        try:
            pac=self.cb_pac.get(); prof=self.cb_prof.get()
            if pac not in self.pmap: raise ValueError("Seleccione un paciente.")
            if prof not in self.prmap: raise ValueError("Seleccione un profesional.")
            fecha=validar_fecha(self.en_fecha.get())
            hora=self.cb_hora.get()
            if " - " not in hora: raise ValueError("Seleccione un horario disponible.")
            hi,hf=hora.split(" - ")
            canal=self.cb_canal.get()
            if canal not in CANALES: raise ValueError("Seleccione teléfono o WhatsApp.")
            motivo=self.en_motivo.get().strip()
            obs=self.en_obs.get().strip()
            pid=self.prmap[prof]; paciente_id=self.pmap[pac]
            # Revalidación en el momento de guardar para evitar reservas simultáneas.
            with conectar() as con:
                slots=intervalos_disponibles(pid,fecha)
                if not any(a==hi and b==hf and r is None for a,b,r in slots):
                    raise ValueError("Ese horario ya no está disponible. Vuelva a consultar la agenda.")
                cur=con.execute("""
                    INSERT INTO Turnos(paciente_id,profesional_id,fecha,hora_inicio,hora_fin,
                    estado,motivo_consulta,observaciones,canal_solicitud)
                    VALUES(?,?,?,?,?,'SOLICITADO',?,?,?)
                """,(paciente_id,pid,fecha,hi,hf,motivo,obs,canal))
                rid=cur.lastrowid
            auditar("A",rid,"Registro de solicitud de turno",{"paciente_id":paciente_id,"profesional_id":pid,"fecha":fecha,"hora_inicio":hi,"hora_fin":hf,"estado":"SOLICITADO","canal_solicitud":canal})
            messagebox.showinfo("Turno registrado",f"Solicitud registrada correctamente.\nNúmero de turno: {rid}\nEstado: SOLICITADO",parent=self.root)
            self.en_motivo.delete(0,"end"); self.en_obs.delete(0,"end")
            self.cargar_horarios(); self.cargar_turnos()
        except sqlite3.IntegrityError as e:
            messagebox.showerror("Conflicto de agenda","No se pudo registrar: el horario fue ocupado o los datos relacionados ya no están vigentes.\n\n"+str(e),parent=self.root)
        except Exception as e: messagebox.showerror("No se pudo registrar",str(e),parent=self.root)

    def _crear_lista(self):
        f=self.tab_lista
        filt=ttk.LabelFrame(f,text="Filtros de búsqueda",padding=8); filt.pack(fill="x")
        ttk.Label(filt,text="Desde").grid(row=0,column=0,padx=4)
        self.f_desde=ttk.Entry(filt,width=13); self.f_desde.grid(row=0,column=1,padx=4); self.f_desde.insert(0,date.today().isoformat())
        ttk.Label(filt,text="Hasta").grid(row=0,column=2,padx=4)
        self.f_hasta=ttk.Entry(filt,width=13); self.f_hasta.grid(row=0,column=3,padx=4); self.f_hasta.insert(0,date.today().isoformat())
        ttk.Label(filt,text="Profesional").grid(row=0,column=4,padx=4)
        self.f_prof=ttk.Combobox(filt,state="readonly",width=35,values=["Todos"]+list(self.prmap)); self.f_prof.grid(row=0,column=5,padx=4); self.f_prof.current(0)
        ttk.Label(filt,text="Estado").grid(row=0,column=6,padx=4)
        self.f_estado=ttk.Combobox(filt,state="readonly",width=17,values=["Todos"]+list(ESTADOS)); self.f_estado.grid(row=0,column=7,padx=4); self.f_estado.current(0)
        ttk.Button(filt,text="Buscar",command=self.cargar_turnos).grid(row=0,column=8,padx=6)
        cols=("id","fecha","hora","paciente","dni","profesional","estado","canal")
        self.tree=ttk.Treeview(f,columns=cols,show="headings",height=16)
        widths=(55,100,105,190,95,190,120,100)
        heads=("N.º","Fecha","Horario","Paciente","DNI","Profesional","Estado","Canal")
        for c,w,h in zip(cols,widths,heads):
            self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor="w")
        self.tree.pack(fill="both",expand=True,pady=8)
        self.tree.bind("<<TreeviewSelect>>",self.seleccionar)
        actions=ttk.LabelFrame(f,text="Acciones sobre el turno seleccionado",padding=8); actions.pack(fill="x")
        ttk.Label(actions,text="La confirmación se registra por el mismo canal de solicitud.").grid(row=0,column=0,columnspan=2,padx=5)
        ttk.Button(actions,text="Confirmar",command=self.confirmar).grid(row=0,column=2,padx=5)
        ttk.Button(actions,text="Cancelar",command=self.cancelar).grid(row=0,column=3,padx=5)
        ttk.Button(actions,text="Marcar atendido",command=lambda:self.cambiar_estado("ATENDIDO")).grid(row=0,column=4,padx=5)
        ttk.Button(actions,text="Marcar ausente",command=lambda:self.cambiar_estado("AUSENTE")).grid(row=0,column=5,padx=5)
        ttk.Button(actions,text="Reprogramar",command=self.reprogramar).grid(row=0,column=6,padx=5)
        ttk.Button(actions,text="Actualizar",command=self.cargar_turnos).grid(row=0,column=7,padx=5)

    def cargar_turnos(self):
        if not hasattr(self,"tree"): return
        try:
            desde=validar_fecha(self.f_desde.get()); hasta=validar_fecha(self.f_hasta.get())
            if desde>hasta: raise ValueError("La fecha Desde no puede ser posterior a Hasta.")
            prof=self.f_prof.get() if self.f_prof.get() else "Todos"
            estado=self.f_estado.get() if self.f_estado.get() else "Todos"
            sql="""SELECT t.id,t.fecha,t.hora_inicio,t.hora_fin,
                   pa.apellido||', '||pa.nombre paciente,pa.dni,
                   pr.apellido||', '||pr.nombre profesional,t.estado,t.canal_solicitud
                   FROM Turnos t JOIN Pacientes pa ON pa.id=t.paciente_id
                   JOIN Profesionales pr ON pr.id=t.profesional_id
                   WHERE t.fecha BETWEEN ? AND ?"""
            args=[desde,hasta]
            if prof!="Todos": sql+=" AND t.profesional_id=?"; args.append(self.prmap[prof])
            if estado!="Todos": sql+=" AND t.estado=?"; args.append(estado)
            sql+=" ORDER BY t.fecha,t.hora_inicio,pr.apellido,pa.apellido"
            with conectar() as con: rows=con.execute(sql,args).fetchall()
            for x in self.tree.get_children(): self.tree.delete(x)
            for r in rows:
                self.tree.insert("","end",iid=str(r["id"]),values=(r["id"],r["fecha"],f"{r['hora_inicio']} - {r['hora_fin']}",r["paciente"],r["dni"],r["profesional"],r["estado"],r["canal_solicitud"]))
            self.turno_seleccionado=None
        except Exception as e: messagebox.showerror("Consulta de turnos",str(e),parent=self.root)

    def seleccionar(self,event=None):
        sel=self.tree.selection()
        self.turno_seleccionado=int(sel[0]) if sel else None

    def obtener_turno(self):
        if not self.turno_seleccionado: raise ValueError("Seleccione un turno de la lista.")
        with conectar() as con:
            r=con.execute("SELECT * FROM Turnos WHERE id=?",(self.turno_seleccionado,)).fetchone()
        if not r: raise ValueError("El turno ya no existe.")
        return dict(r)

    def confirmar(self):
        try:
            t=self.obtener_turno()
            if t["estado"]!="SOLICITADO": raise ValueError("Solo se pueden confirmar turnos en estado SOLICITADO.")
            canal=t["canal_solicitud"]  # La confirmación debe realizarse por el mismo medio de la solicitud.
            with conectar() as con:
                con.execute("""UPDATE Turnos SET estado='CONFIRMADO',canal_confirmacion=?,
                    fecha_confirmacion=CURRENT_TIMESTAMP,fecha_actualizacion=CURRENT_TIMESTAMP
                    WHERE id=? AND estado='SOLICITADO'""",(canal,t["id"]))
            auditar("M",t["id"],"Confirmación de turno",{"estado":"CONFIRMADO","canal_confirmacion":canal},{"estado":t["estado"]})
            self.cargar_turnos()
            messagebox.showinfo("Turnos","Turno confirmado. Registrar la comunicación con el paciente por el canal indicado.",parent=self.root)
        except Exception as e: messagebox.showerror("No se pudo confirmar",str(e),parent=self.root)

    def cambiar_estado(self,nuevo):
        try:
            t=self.obtener_turno()
            permitidos={"ATENDIDO":("CONFIRMADO",),"AUSENTE":("CONFIRMADO",)}
            if t["estado"] not in permitidos[nuevo]:
                raise ValueError(f"Solo se puede marcar {nuevo.lower()} un turno CONFIRMADO.")
            if not messagebox.askyesno("Confirmar acción",f"¿Desea marcar el turno {t['id']} como {nuevo}?",parent=self.root): return
            with conectar() as con:
                con.execute("UPDATE Turnos SET estado=?,fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?",(nuevo,t["id"]))
            auditar("M",t["id"],f"Cambio de estado a {nuevo}",{"estado":nuevo},{"estado":t["estado"]})
            self.cargar_turnos()
        except Exception as e: messagebox.showerror("No se pudo actualizar",str(e),parent=self.root)

    def cancelar(self):
        try:
            t=self.obtener_turno()
            if t["estado"] not in ("SOLICITADO","CONFIRMADO"): raise ValueError("Solo se pueden cancelar turnos solicitados o confirmados.")
            if not messagebox.askyesno("Cancelar turno",f"¿Confirma la cancelación del turno {t['id']}?",parent=self.root): return
            with conectar() as con:
                con.execute("UPDATE Turnos SET estado='CANCELADO',fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?",(t["id"],))
            auditar("M",t["id"],"Cancelación de turno",{"estado":"CANCELADO"},{"estado":t["estado"]})
            self.cargar_turnos()
        except Exception as e: messagebox.showerror("No se pudo cancelar",str(e),parent=self.root)

    def reprogramar(self):
        try:
            t=self.obtener_turno()
            if t["estado"] not in ("SOLICITADO","CONFIRMADO"): raise ValueError("Solo se pueden reprogramar turnos solicitados o confirmados.")
            dlg=tk.Toplevel(self.root); dlg.title("Reprogramar turno"); dlg.transient(self.root); dlg.grab_set()
            dlg.geometry("440x250")
            ttk.Label(dlg,text=f"Reprogramar turno N.º {t['id']}",font=("Arial",12,"bold")).pack(pady=8)
            box=ttk.Frame(dlg,padding=10); box.pack(fill="x")
            ttk.Label(box,text="Nueva fecha (AAAA-MM-DD)").grid(row=0,column=0,padx=5,pady=6,sticky="w")
            efecha=ttk.Entry(box,width=16); efecha.grid(row=0,column=1); efecha.insert(0,t["fecha"])
            ttk.Label(box,text="Nuevo horario").grid(row=1,column=0,padx=5,pady=6,sticky="w")
            ch=ttk.Combobox(box,state="readonly",width=22); ch.grid(row=1,column=1)
            def horas():
                try:
                    f=validar_fecha(efecha.get())
                    ss=intervalos_disponibles(t["profesional_id"],f)
                    libres=[f"{a} - {b}" for a,b,r in ss if not r]
                    # Si conserva mismo horario y fecha, el turno de origen no debe bloquearse.
                    if f==t["fecha"]:
                        libres.append(f"{t['hora_inicio']} - {t['hora_fin']}")
                    ch["values"]=sorted(set(libres)); ch.set(ch["values"][0] if ch["values"] else "")
                except Exception as ex: messagebox.showerror("Fecha",str(ex),parent=dlg)
            ttk.Button(box,text="Consultar",command=horas).grid(row=0,column=2,padx=5)
            ttk.Label(box,text="La reprogramación conserva el turno anterior en el historial.").grid(row=2,column=0,columnspan=3,pady=8)
            def guardar():
                try:
                    nf=validar_fecha(efecha.get()); hv=ch.get()
                    if " - " not in hv: raise ValueError("Seleccione un nuevo horario.")
                    ni,nf_h=hv.split(" - ")
                    if nf==t["fecha"] and ni==t["hora_inicio"] and nf_h==t["hora_fin"]:
                        raise ValueError("El nuevo horario coincide con el actual.")
                    with conectar() as con:
                        # Revalidar, excluyendo el turno actual.
                        disponibles=intervalos_disponibles(t["profesional_id"],nf)
                        if not any(a==ni and b==nf_h and r is None for a,b,r in disponibles):
                            # En la misma fecha, comprobar si el slot coincide con el propio turno.
                            if not (nf==t["fecha"] and ni==t["hora_inicio"] and nf_h==t["hora_fin"]):
                                raise ValueError("El nuevo horario ya no está disponible.")
                        cur=con.execute("""INSERT INTO Turnos
                            (paciente_id,profesional_id,fecha,hora_inicio,hora_fin,estado,
                             motivo_consulta,observaciones,canal_solicitud,turno_origen_id)
                             VALUES(?,?,?,?,?,'SOLICITADO',?,?,?,?)""",
                            (t["paciente_id"],t["profesional_id"],nf,ni,nf_h,t["motivo_consulta"],t["observaciones"],t["canal_solicitud"],t["id"]))
                        nuevo_id=cur.lastrowid
                        con.execute("UPDATE Turnos SET estado='REPROGRAMADO',fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?",(t["id"],))
                    auditar("M",t["id"],f"Turno reprogramado; nuevo turno {nuevo_id}",{"estado":"REPROGRAMADO","nuevo_turno_id":nuevo_id},{"estado":t["estado"]})
                    auditar("A",nuevo_id,"Alta de turno por reprogramación",{"turno_origen_id":t["id"],"fecha":nf,"hora_inicio":ni,"hora_fin":nf_h})
                    dlg.destroy(); self.cargar_turnos()
                    messagebox.showinfo("Reprogramación",f"Se creó el nuevo turno N.º {nuevo_id} en estado SOLICITADO.",parent=self.root)
                except Exception as ex: messagebox.showerror("No se pudo reprogramar",str(ex),parent=dlg)
            ttk.Button(dlg,text="Guardar reprogramación",command=guardar).pack(pady=8)
            horas()
        except Exception as e: messagebox.showerror("Reprogramar",str(e),parent=self.root)


if __name__=="__main__":
    root=tk.Tk()
    try:
        app=TurnosApp(root)
        root.mainloop()
    except Exception as exc:
        messagebox.showerror("OpenHIS-UNLaM",f"No se pudo iniciar el módulo:\n{exc}")
        raise
