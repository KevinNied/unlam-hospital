# -*- coding: utf-8 -*-
"""OpenHIS-UNLaM | Sprint 8: asignación sugerida, cola de recordatorios y asistencia."""
import sqlite3, tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime, date, timedelta

BASE_DIR=Path(__file__).resolve().parent
RUTA_BD=BASE_DIR/"BD"/"Salud.db"
CANALES=("TELEFONO","WHATSAPP")
ESTADOS=("SOLICITADO","CONFIRMADO","CANCELADO","REPROGRAMADO","ATENDIDO","AUSENTE")

def db():
    if not RUTA_BD.exists(): raise FileNotFoundError(f"No se encontró {RUTA_BD}")
    c=sqlite3.connect(str(RUTA_BD),timeout=20); c.row_factory=sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA busy_timeout=20000")
    return c

def fecha_ok(s): return datetime.strptime(s.strip(),"%Y-%m-%d").date().isoformat()
def hora_ok(s): return datetime.strptime(s.strip(),"%H:%M").strftime("%H:%M")

def asegurar():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS DisponibilidadProfesional(
          id INTEGER PRIMARY KEY AUTOINCREMENT, profesional_id INTEGER NOT NULL,
          dia_semana INTEGER NOT NULL CHECK(dia_semana BETWEEN 0 AND 6),
          hora_inicio TEXT NOT NULL,hora_fin TEXT NOT NULL,
          duracion_minutos INTEGER NOT NULL DEFAULT 30,activo INTEGER NOT NULL DEFAULT 1,
          fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(profesional_id) REFERENCES Profesionales(id));
        CREATE TABLE IF NOT EXISTS BloqueosAgenda(
          id INTEGER PRIMARY KEY AUTOINCREMENT,profesional_id INTEGER NOT NULL,fecha TEXT NOT NULL,
          hora_inicio TEXT,hora_fin TEXT,tipo TEXT NOT NULL DEFAULT 'BLOQUEO',motivo TEXT,
          activo INTEGER NOT NULL DEFAULT 1,fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(profesional_id) REFERENCES Profesionales(id));
        CREATE TABLE IF NOT EXISTS Turnos(
          id INTEGER PRIMARY KEY AUTOINCREMENT,paciente_id INTEGER NOT NULL,profesional_id INTEGER NOT NULL,
          fecha TEXT NOT NULL,hora_inicio TEXT NOT NULL,hora_fin TEXT NOT NULL,
          estado TEXT NOT NULL DEFAULT 'SOLICITADO',motivo_consulta TEXT,observaciones TEXT,
          canal_solicitud TEXT NOT NULL,canal_confirmacion TEXT,fecha_confirmacion TIMESTAMP,
          turno_origen_id INTEGER,fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(paciente_id) REFERENCES Pacientes(id),
          FOREIGN KEY(profesional_id) REFERENCES Profesionales(id),
          FOREIGN KEY(turno_origen_id) REFERENCES Turnos(id));
        CREATE TABLE IF NOT EXISTS ColaNotificaciones(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          turno_id INTEGER NOT NULL,
          tipo TEXT NOT NULL DEFAULT 'RECORDATORIO_24H',
          destinatario TEXT,
          mensaje TEXT NOT NULL,
          programada_para TIMESTAMP NOT NULL,
          estado TEXT NOT NULL DEFAULT 'PENDIENTE'
            CHECK(estado IN ('PENDIENTE','ENVIADA','ERROR','CANCELADA')),
          fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          fecha_procesamiento TIMESTAMP,
          resultado TEXT,
          UNIQUE(turno_id,tipo),
          FOREIGN KEY(turno_id) REFERENCES Turnos(id));
        CREATE INDEX IF NOT EXISTS idx_cola_estado_fecha ON ColaNotificaciones(estado,programada_para);
        CREATE INDEX IF NOT EXISTS idx_turnos_sprint8_fecha_estado ON Turnos(fecha,estado);
        """)

def auditar(tipo, rid, desc, nuevos=None, anteriores=None):
    try:
        import Auditoria_utiles as au
        if tipo=="A": au.auditar_alta("ColaNotificaciones" if "recordatorio" in desc.lower() else "Turnos",rid,desc,nuevos)
        else: au.auditar_modificacion("Turnos",rid,desc,anteriores,nuevos)
    except Exception as e: print("[ADVERTENCIA auditoría]",e)

def profesionales():
    with db() as c:
        return c.execute("""SELECT p.id,p.nombre,p.apellido,p.especialidad_id,
          COALESCE(e.nombre,'Sin especialidad') especialidad,p.telefono
          FROM Profesionales p LEFT JOIN Especialidades e ON e.id=p.especialidad_id
          WHERE p.activo=1 ORDER BY e.nombre,p.apellido,p.nombre""").fetchall()

def especialidades():
    with db() as c: return c.execute("SELECT id,nombre FROM Especialidades WHERE activo=1 ORDER BY nombre").fetchall()

def slots_libres(pid,fecha):
    dia=date.fromisoformat(fecha).weekday()
    with db() as c:
        ds=c.execute("""SELECT hora_inicio,hora_fin,duracion_minutos FROM DisponibilidadProfesional
          WHERE profesional_id=? AND dia_semana=? AND activo=1 ORDER BY hora_inicio""",(pid,dia)).fetchall()
        bs=c.execute("""SELECT hora_inicio,hora_fin,tipo FROM BloqueosAgenda
          WHERE profesional_id=? AND fecha=? AND activo=1""",(pid,fecha)).fetchall()
        ts=c.execute("""SELECT hora_inicio,hora_fin FROM Turnos
          WHERE profesional_id=? AND fecha=? AND estado IN ('SOLICITADO','CONFIRMADO')""",(pid,fecha)).fetchall()
    out=[]
    for d in ds:
        cur=datetime.strptime(d["hora_inicio"],"%H:%M"); end=datetime.strptime(d["hora_fin"],"%H:%M")
        dur=int(d["duracion_minutos"])
        while cur+timedelta(minutes=dur)<=end:
            nxt=cur+timedelta(minutes=dur); a,b=cur.strftime("%H:%M"),nxt.strftime("%H:%M")
            blocked=any(x["hora_inicio"] is None or (a<x["hora_fin"] and b>x["hora_inicio"]) for x in bs)
            busy=any(a<x["hora_fin"] and b>x["hora_inicio"] for x in ts)
            if not blocked and not busy: out.append((a,b))
            cur=nxt
    return out

class App:
 def __init__(self,root):
    self.root=root; root.title("OpenHIS-UNLaM")
    root.geometry("1190x760"); root.minsize(980,620)
    asegurar(); self.profs=profesionales(); self.esp=especialidades()
    self.pmap={f"{p['id']} - {p['apellido']}, {p['nombre']} ({p['especialidad']})":p for p in self.profs}
    self.emap={e["nombre"]:e["id"] for e in self.esp}
    self.interfaz()
 def interfaz(self):
    ttk.Label(self.root,text="TURNOS-ASIGNACIÓN, RECORDATORIOS Y ASISTENCIA",
      font=("Arial",16,"bold"),padding=12).pack(anchor="w")
    nb=ttk.Notebook(self.root); nb.pack(fill="both",expand=True,padx=12,pady=8)
    self.t1=ttk.Frame(nb,padding=12); self.t2=ttk.Frame(nb,padding=12); self.t3=ttk.Frame(nb,padding=12)
    nb.add(self.t1,text="Asignación sugerida")
    nb.add(self.t2,text="Cola de recordatorios")
    nb.add(self.t3,text="Asistencia")
    self.tab_asignacion(); self.tab_recordatorios(); self.tab_asistencia()
 def tab_asignacion(self):
    f=self.t1
    g=ttk.LabelFrame(f,text="Criterios de búsqueda",padding=10); g.pack(fill="x")
    ttk.Label(g,text="Especialidad").grid(row=0,column=0,padx=5,pady=5)
    self.eesp=ttk.Combobox(g,state="readonly",values=list(self.emap),width=32); self.eesp.grid(row=0,column=1,padx=5)
    ttk.Label(g,text="Fecha (AAAA-MM-DD)").grid(row=0,column=2,padx=5)
    self.ef=ttk.Entry(g,width=14); self.ef.grid(row=0,column=3,padx=5); self.ef.insert(0,date.today().isoformat())
    ttk.Label(g,text="Franja horaria").grid(row=0,column=4,padx=5)
    self.franja=ttk.Combobox(g,state="readonly",values=["Cualquiera","Mañana (antes de 12)","Tarde (12 o después)"],width=23); self.franja.grid(row=0,column=5,padx=5); self.franja.current(0)
    ttk.Button(g,text="Buscar profesionales y horarios",command=self.buscar_sugerencias).grid(row=0,column=6,padx=8)
    ttk.Label(f,text="El sistema propone opciones según especialidad, disponibilidad semanal, bloqueos y turnos existentes. La asignación requiere confirmación administrativa.",wraplength=1050).pack(anchor="w",pady=8)
    cols=("prof","especialidad","fecha","horario","telefono")
    self.sug=ttk.Treeview(f,columns=cols,show="headings",height=15)
    for c,w,h in zip(cols,(260,190,110,130,150),("Profesional","Especialidad","Fecha","Horario","Contacto")):
      self.sug.heading(c,text=h); self.sug.column(c,width=w)
    self.sug.pack(fill="both",expand=True,pady=8)
    self.sug.bind("<<TreeviewSelect>>",self.sel_sugerencia)
    b=ttk.Frame(f); b.pack(fill="x")
    ttk.Label(b,text="Paciente (para registrar la solicitud)").pack(side="left")
    with db() as c: pats=c.execute("SELECT id,apellido,nombre,dni FROM Pacientes WHERE activo=1 ORDER BY apellido,nombre").fetchall()
    self.pmapac={f"{p['id']} - {p['apellido']}, {p['nombre']} ({p['dni']})":p["id"] for p in pats}
    self.epac=ttk.Combobox(b,state="readonly",values=list(self.pmapac),width=45); self.epac.pack(side="left",padx=8)
    ttk.Button(b,text="Registrar solicitud con esta sugerencia",command=self.registrar_sugerencia).pack(side="left",padx=8)
    self.sel=None
 def buscar_sugerencias(self):
    try:
      if self.eesp.get() not in self.emap: raise ValueError("Seleccione una especialidad.")
      f=fecha_ok(self.ef.get()); eid=self.emap[self.eesp.get()]
      for i in self.sug.get_children(): self.sug.delete(i)
      fr=self.franja.get()
      count=0
      for p in self.profs:
        if p["especialidad_id"]!=eid: continue
        for a,b in slots_libres(p["id"],f):
          h=int(a[:2])
          if fr=="Mañana (antes de 12)" and h>=12: continue
          if fr=="Tarde (12 o después)" and h<12: continue
          iid=f"{p['id']}|{f}|{a}"
          self.sug.insert("","end",iid=iid,values=(f"{p['apellido']}, {p['nombre']}",p["especialidad"],f,f"{a} - {b}",p["telefono"] or "Sin teléfono"))
          count+=1
      if not count: messagebox.showinfo("Asignación sugerida","No se encontraron opciones disponibles para esos criterios.",parent=self.root)
    except Exception as e: messagebox.showerror("Búsqueda",str(e),parent=self.root)
 def sel_sugerencia(self,event=None):
    s=self.sug.selection(); self.sel=self.sug.item(s[0],"values") if s else None
 def registrar_sugerencia(self):
    try:
      if not self.sel: raise ValueError("Seleccione una sugerencia.")
      if self.epac.get() not in self.pmapac: raise ValueError("Seleccione un paciente.")
      prof_txt=self.sel[0]; fecha=self.sel[2]; hi,hf=self.sel[3].split(" - ")
      p=next(x for x in self.profs if (x["apellido"] + ", " + x["nombre"]) == prof_txt)
      # Revalidar inmediatamente antes de crear solicitud.
      if (hi,hf) not in slots_libres(p["id"],fecha): raise ValueError("La opción dejó de estar disponible. Busque nuevamente.")
      with db() as c:
        cur=c.execute("""INSERT INTO Turnos(paciente_id,profesional_id,fecha,hora_inicio,hora_fin,
          estado,motivo_consulta,observaciones,canal_solicitud)
          VALUES(?,?,?,?,?,'SOLICITADO','Asignación sugerida por especialidad',?,'TELEFONO')""",
          (self.pmapac[self.epac.get()],p["id"],fecha,hi,hf,"Origen: HU-16"))
        rid=cur.lastrowid
      auditar("A",rid,"Registro de turno mediante asignación sugerida",{"fecha":fecha,"hora_inicio":hi,"profesional_id":p["id"]})
      messagebox.showinfo("Turno solicitado",f"Se registró la solicitud N.º {rid} en estado SOLICITADO.\nEl administrativo debe completar la confirmación.",parent=self.root)
      self.buscar_sugerencias()
    except sqlite3.IntegrityError as e: messagebox.showerror("Conflicto",f"No se pudo registrar la sugerencia: {e}",parent=self.root)
    except Exception as e: messagebox.showerror("Asignación",str(e),parent=self.root)
 def tab_recordatorios(self):
    f=self.t2
    ttk.Label(f,text="Generación de recordatorios para turnos CONFIRMADOS cuya atención será dentro de las próximas 24 horas.",wraplength=1050).pack(anchor="w")
    bar=ttk.Frame(f); bar.pack(fill="x",pady=10)
    ttk.Button(bar,text="Generar recordatorios pendientes",command=self.generar_cola).pack(side="left")
    ttk.Button(bar,text="Actualizar cola",command=self.cargar_cola).pack(side="left",padx=8)
    ttk.Label(f,text="Los mensajes quedan en cola PENDIENTE. No se envían SMS reales en esta etapa; la integración con un proveedor se realizará posteriormente.",wraplength=1050).pack(anchor="w",pady=5)
    cols=("id","turno","fecha","hora","paciente","telefono","estado","programada")
    self.cola=ttk.Treeview(f,columns=cols,show="headings",height=17)
    for c,w,h in zip(cols,(55,70,100,80,190,130,110,160),("ID","Turno","Fecha","Hora","Paciente","Teléfono","Estado","Creado para")):
      self.cola.heading(c,text=h); self.cola.column(c,width=w)
    self.cola.pack(fill="both",expand=True,pady=8); self.cargar_cola()
 def generar_cola(self):
    try:
      ahora=datetime.now(); limite=ahora+timedelta(hours=24); agregados=0
      with db() as c:
        rows=c.execute("""SELECT t.id,t.fecha,t.hora_inicio,pa.nombre,pa.apellido,pa.telefono
          FROM Turnos t JOIN Pacientes pa ON pa.id=t.paciente_id
          WHERE t.estado='CONFIRMADO'""").fetchall()
        for t in rows:
          try: dt=datetime.strptime(t["fecha"]+" "+t["hora_inicio"],"%Y-%m-%d %H:%M")
          except ValueError: continue
          if ahora < dt <= limite:
            mensaje=f"Recordatorio: tiene un turno el {t['fecha']} a las {t['hora_inicio']}."
            cur=c.execute("""INSERT OR IGNORE INTO ColaNotificaciones
              (turno_id,tipo,destinatario,mensaje,programada_para,estado)
              VALUES(?,'RECORDATORIO_24H',?,?,?,'PENDIENTE')""",
              (t["id"],t["telefono"],mensaje,ahora.strftime("%Y-%m-%d %H:%M:%S")))
            if cur.rowcount: agregados+=1
      self.cargar_cola()
      messagebox.showinfo("Cola de recordatorios",f"Se incorporaron {agregados} recordatorios nuevos.\nLos registros permanecen PENDIENTES; no se envió ningún SMS.",parent=self.root)
    except Exception as e: messagebox.showerror("Recordatorios",str(e),parent=self.root)
 def cargar_cola(self):
    if not hasattr(self,"cola"): return
    with db() as c:
      rows=c.execute("""SELECT n.id,n.turno_id,t.fecha,t.hora_inicio,pa.apellido||', '||pa.nombre paciente,
        n.destinatario,n.estado,n.programada_para
        FROM ColaNotificaciones n JOIN Turnos t ON t.id=n.turno_id
        JOIN Pacientes pa ON pa.id=t.paciente_id ORDER BY n.programada_para DESC,n.id DESC""").fetchall()
    for i in self.cola.get_children(): self.cola.delete(i)
    for r in rows:self.cola.insert("","end",iid=str(r["id"]),values=(r["id"],r["turno_id"],r["fecha"],r["hora_inicio"],r["paciente"],r["destinatario"] or "Sin teléfono",r["estado"],r["programada_para"]))
 def tab_asistencia(self):
    f=self.t3
    bar=ttk.Frame(f);bar.pack(fill="x")
    ttk.Label(bar,text="Fecha (AAAA-MM-DD)").pack(side="left")
    self.af=ttk.Entry(bar,width=14);self.af.pack(side="left",padx=6);self.af.insert(0,date.today().isoformat())
    ttk.Button(bar,text="Consultar turnos",command=self.cargar_asistencia).pack(side="left",padx=6)
    cols=("id","hora","paciente","dni","prof","estado")
    self.att=ttk.Treeview(f,columns=cols,show="headings",height=17)
    for c,w,h in zip(cols,(55,100,220,110,220,130),("N.º","Hora","Paciente","DNI","Profesional","Estado")):
      self.att.heading(c,text=h);self.att.column(c,width=w)
    self.att.pack(fill="both",expand=True,pady=10)
    actions=ttk.Frame(f);actions.pack(fill="x")
    ttk.Button(actions,text="Registrar asistencia",command=lambda:self.estado_asistencia("ATENDIDO")).pack(side="left",padx=4)
    ttk.Button(actions,text="Registrar ausencia",command=lambda:self.estado_asistencia("AUSENTE")).pack(side="left",padx=4)
    ttk.Button(actions,text="Cancelar turno",command=lambda:self.estado_asistencia("CANCELADO")).pack(side="left",padx=4)
    ttk.Label(f,text="La operación queda asociada al usuario activo mediante el módulo de auditoría.",wraplength=1000).pack(anchor="w",pady=8)
 def cargar_asistencia(self):
    try:
      f=fecha_ok(self.af.get())
      with db() as c:
        rows=c.execute("""SELECT t.id,t.hora_inicio,pa.apellido||', '||pa.nombre paciente,pa.dni,
          pr.apellido||', '||pr.nombre profesional,t.estado
          FROM Turnos t JOIN Pacientes pa ON pa.id=t.paciente_id
          JOIN Profesionales pr ON pr.id=t.profesional_id WHERE t.fecha=?
          ORDER BY t.hora_inicio,pr.apellido""",(f,)).fetchall()
      for i in self.att.get_children():self.att.delete(i)
      for r in rows:self.att.insert("","end",iid=str(r["id"]),values=(r["id"],r["hora_inicio"],r["paciente"],r["dni"],r["profesional"],r["estado"]))
    except Exception as e:messagebox.showerror("Asistencia",str(e),parent=self.root)
 def estado_asistencia(self,nuevo):
    try:
      sel=self.att.selection()
      if not sel: raise ValueError("Seleccione un turno.")
      rid=int(sel[0])
      with db() as c:
        t=c.execute("SELECT estado FROM Turnos WHERE id=?",(rid,)).fetchone()
        if not t:raise ValueError("El turno no existe.")
        permitidos={"ATENDIDO":("CONFIRMADO",),"AUSENTE":("CONFIRMADO",),"CANCELADO":("SOLICITADO","CONFIRMADO")}
        if t["estado"] not in permitidos[nuevo]:raise ValueError(f"No se puede pasar de {t['estado']} a {nuevo}.")
        if not messagebox.askyesno("Confirmar",f"¿Registrar el estado {nuevo} para el turno {rid}?",parent=self.root):return
        c.execute("UPDATE Turnos SET estado=?,fecha_actualizacion=CURRENT_TIMESTAMP WHERE id=?",(nuevo,rid))
      auditar("M",rid,f"Registro de estado de turno: {nuevo}",{"estado":nuevo},{"estado":t["estado"]})
      self.cargar_asistencia()
    except Exception as e:messagebox.showerror("Asistencia",str(e),parent=self.root)

if __name__=="__main__":
 root=tk.Tk()
 try: App(root); root.mainloop()
 except Exception as e: messagebox.showerror("OpenHIS-UNLaM",str(e)); raise
