# ================================================================
# INTEROPERABILIDAD FHIR
# OpenHIS-UNLaM | Interfaz gráfica Tkinter
# Archivo: _Interoperabilidad_FHIR.pyw
# ================================================================
import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime, timezone

RUTA_BD = Path("BD/Salud.db")
CARPETA_INTERCAMBIO = Path("intercambio")
CARPETA_INTERCAMBIO.mkdir(exist_ok=True)

def conectar_bd():
    if not RUTA_BD.exists():
        raise FileNotFoundError(f"No se encontró la base de datos: {RUTA_BD}")
    return sqlite3.connect(str(RUTA_BD))

def listar_pacientes():
    con = conectar_bd()
    try:
        return con.execute("""
            SELECT id, dni, apellido, nombre
            FROM Pacientes WHERE activo=1 ORDER BY apellido, nombre
        """).fetchall()
    finally:
        con.close()

def crear_observation_desde_signo(signo_id):
    con = conectar_bd()
    try:
        row = con.execute("""
            SELECT sv.id, sv.paciente_id, sv.fecha_hora, sv.presion_sistolica,
                   sv.presion_diastolica, sv.frecuencia_cardiaca,
                   sv.temperatura, sv.saturacion_oxigeno
            FROM SignosVitales sv WHERE sv.id=?
        """, (signo_id,)).fetchone()
        if not row:
            raise ValueError("No se encontró el registro de signos vitales.")
        sid, paciente_id, fecha, sist, diast, fc, temp, spo2 = row
        # Para fines didácticos se exporta cada dato disponible como Observation.
        recursos = []
        mediciones = [
            ("8480-6", "Systolic blood pressure", sist, "mm[Hg]"),
            ("8462-4", "Diastolic blood pressure", diast, "mm[Hg]"),
            ("8867-4", "Heart rate", fc, "/min"),
            ("8310-5", "Body temperature", temp, "Cel"),
            ("59408-5", "Oxygen saturation", spo2, "%"),
        ]
        for codigo, descripcion, valor, unidad in mediciones:
            if valor is None:
                continue
            recursos.append({
                "resourceType": "Observation",
                "status": "final",
                "subject": {"reference": f"Patient/{paciente_id}"},
                "effectiveDateTime": str(fecha) if fecha else datetime.now(timezone.utc).isoformat(),
                "code": {"coding": [{
                    "system": "http://loinc.org", "code": codigo, "display": descripcion
                }]},
                "valueQuantity": {"value": valor, "unit": unidad}
            })
        if not recursos:
            raise ValueError("El registro no contiene mediciones para exportar.")
        return recursos
    finally:
        con.close()

def validar_recurso_fhir(datos):
    if isinstance(datos, list):
        if not datos:
            raise ValueError("La lista FHIR está vacía.")
        return [validar_recurso_fhir(x) for x in datos]
    if not isinstance(datos, dict):
        raise ValueError("El archivo debe contener un objeto JSON FHIR.")
    tipo = datos.get("resourceType")
    if tipo not in {"Observation", "DiagnosticReport", "Encounter", "Bundle"}:
        raise ValueError(f"Tipo de recurso no contemplado en esta práctica: {tipo}")
    if tipo == "Bundle":
        entradas = datos.get("entry", [])
        for entrada in entradas:
            recurso = entrada.get("resource", {})
            if recurso:
                validar_recurso_fhir(recurso)
    elif not datos.get("status"):
        raise ValueError(f"El recurso {tipo} no contiene el campo status.")
    return datos

class AppFHIR:
    def __init__(self, root):
        self.root = root
        root.title("OpenHIS-UNLaM | HU-09 - Interoperabilidad FHIR")
        root.geometry("1000x690")
        root.minsize(820, 560)
        self.pacientes = []
        self._crear_interfaz()
        self.cargar_pacientes()

    def _crear_interfaz(self):
        cab = ttk.Frame(self.root, padding=14)
        cab.pack(fill="x")
        ttk.Label(cab, text="INTEROPERABILIDAD EN SALUD — FHIR",
                  font=("Arial", 16, "bold")).pack(anchor="w")
        ttk.Label(cab, text="HU-09 | Exportación e importación de recursos de ejemplo",
                  font=("Arial", 10)).pack(anchor="w", pady=(3, 0))

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        exportar = ttk.Frame(self.tabs, padding=12)
        importar = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(exportar, text="Exportar signos vitales")
        self.tabs.add(importar, text="Importar / validar archivo")

        ttk.Label(exportar, text="Paciente activo:").grid(row=0, column=0, sticky="w", pady=5)
        self.cb_paciente = ttk.Combobox(exportar, state="readonly", width=60)
        self.cb_paciente.grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        self.cb_paciente.bind("<<ComboboxSelected>>", lambda _e: self.cargar_signos())
        ttk.Label(exportar, text="Registro de signos vitales:").grid(row=1, column=0, sticky="w", pady=5)
        self.cb_signos = ttk.Combobox(exportar, state="readonly", width=60)
        self.cb_signos.grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(exportar, text="Actualizar pacientes", command=self.cargar_pacientes).grid(
            row=2, column=1, sticky="w", padx=8, pady=8)
        ttk.Button(exportar, text="Exportar FHIR JSON", command=self.exportar).grid(
            row=3, column=1, sticky="w", padx=8, pady=8)
        self.txt_export = tk.Text(exportar, height=20, wrap="none", font=("Lucida Console", 9))
        self.txt_export.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=8)
        exportar.columnconfigure(1, weight=1)
        exportar.rowconfigure(4, weight=1)

        fila = ttk.Frame(importar)
        fila.pack(fill="x")
        ttk.Button(fila, text="Seleccionar JSON", command=self.seleccionar_archivo).pack(side="left")
        ttk.Button(fila, text="Validar archivo", command=self.validar_archivo).pack(side="left", padx=8)
        self.lbl_archivo = ttk.Label(importar, text="No se seleccionó ningún archivo.")
        self.lbl_archivo.pack(anchor="w", pady=8)
        self.txt_import = tk.Text(importar, wrap="none", font=("Lucida Console", 9))
        self.txt_import.pack(fill="both", expand=True)
        self.archivo_importar = None
        ttk.Label(importar, text="La validación es didáctica; no incorpora datos a la historia clínica.",
                  foreground="#8A4B08").pack(anchor="w", pady=(8, 0))

    def cargar_pacientes(self):
        try:
            self.pacientes = listar_pacientes()
            self.cb_paciente["values"] = [
                f"{p[0]} | {p[2]}, {p[3]} | DNI {p[1]}" for p in self.pacientes
            ]
            if self.pacientes:
                self.cb_paciente.current(0)
                self.cargar_signos()
            else:
                self.cb_signos["values"] = []
        except Exception as exc:
            messagebox.showerror("Base de datos", str(exc), parent=self.root)

    def cargar_signos(self):
        idx = self.cb_paciente.current()
        if idx < 0:
            return
        paciente_id = self.pacientes[idx][0]
        con = conectar_bd()
        try:
            rows = con.execute("""
                SELECT id, fecha_hora, motivo_consulta FROM SignosVitales
                WHERE paciente_id=? AND activo=1 ORDER BY fecha_hora DESC
            """, (paciente_id,)).fetchall()
            self.signos = rows
            self.cb_signos["values"] = [
                f"{r[0]} | {r[1] or 'sin fecha'} | {r[2] or 'sin motivo'}" for r in rows
            ]
            if rows:
                self.cb_signos.current(0)
        finally:
            con.close()

    def exportar(self):
        idx = self.cb_signos.current()
        if idx < 0:
            messagebox.showwarning("Seleccione un registro", "Seleccione un registro de signos vitales.", parent=self.root)
            return
        signo_id = self.signos[idx][0]
        try:
            recursos = crear_observation_desde_signo(signo_id)
            destino = filedialog.asksaveasfilename(
                parent=self.root, title="Guardar recursos FHIR",
                initialdir=str(CARPETA_INTERCAMBIO),
                initialfile=f"signos_{signo_id}_fhir.json",
                defaultextension=".json", filetypes=[("JSON", "*.json")]
            )
            if not destino:
                return
            salida = {"resourceType": "Bundle", "type": "collection",
                      "entry": [{"resource": r} for r in recursos]}
            Path(destino).write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
            self.txt_export.delete("1.0", "end")
            self.txt_export.insert("1.0", json.dumps(salida, ensure_ascii=False, indent=2))
            messagebox.showinfo("Exportación finalizada",
                                f"Se exportaron {len(recursos)} recursos Observation.\n\n{destino}",
                                parent=self.root)
        except Exception as exc:
            messagebox.showerror("Error de exportación", str(exc), parent=self.root)

    def seleccionar_archivo(self):
        ruta = filedialog.askopenfilename(
            parent=self.root, title="Seleccionar archivo FHIR JSON",
            filetypes=[("JSON", "*.json"), ("Todos los archivos", "*.*")]
        )
        if ruta:
            self.archivo_importar = Path(ruta)
            self.lbl_archivo.config(text=str(self.archivo_importar))
            self.validar_archivo()

    def validar_archivo(self):
        if not self.archivo_importar:
            messagebox.showwarning("Archivo requerido", "Seleccione primero un archivo JSON.", parent=self.root)
            return
        try:
            datos = json.loads(self.archivo_importar.read_text(encoding="utf-8"))
            validar_recurso_fhir(datos)
            self.txt_import.delete("1.0", "end")
            self.txt_import.insert("1.0", json.dumps(datos, ensure_ascii=False, indent=2))
            messagebox.showinfo("Validación", "La estructura pasó las validaciones básicas de esta práctica. No se importó a la base clínica.", parent=self.root)
        except Exception as exc:
            messagebox.showerror("Archivo no válido", str(exc), parent=self.root)

if __name__ == "__main__":
    root = tk.Tk()
    AppFHIR(root)
    root.mainloop()
