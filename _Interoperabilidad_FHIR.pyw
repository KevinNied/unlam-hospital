# -*- coding: utf-8 -*-
"""OpenHIS-UNLaM | Interoperabilidad FHIR JSON
Importador con previsualización y confirmación explícita antes de escribir en Salud.db.
Requiere Python 3 estándar (tkinter, sqlite3, json). No requiere paquetes externos.
"""
import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
RUTA_BD = BASE_DIR / "BD" / "Salud.db"
CARPETA_INTERCAMBIO = BASE_DIR / "intercambio"
CARPETA_INTERCAMBIO.mkdir(exist_ok=True)

LOINC = {
    "8480-6": ("presion_sistolica", "mm[Hg]"),
    "8462-4": ("presion_diastolica", "mm[Hg]"),
    "8867-4": ("frecuencia_cardiaca", "/min"),
    "8310-5": ("temperatura", "Cel"),
    "59408-5": ("saturacion_oxigeno", "%"),
}


def conectar_bd():
    if not RUTA_BD.exists():
        raise FileNotFoundError(
            f"No se encontró la base de datos:\n{RUTA_BD}\n\n"
            "Coloque este programa en la carpeta del proyecto que contiene BD/Salud.db."
        )
    con = sqlite3.connect(str(RUTA_BD))
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _entries(datos):
    """Normaliza un recurso, una lista o un Bundle FHIR a una lista de recursos."""
    if isinstance(datos, list):
        recursos = []
        for item in datos:
            recursos.extend(_entries(item))
        return recursos
    if not isinstance(datos, dict):
        raise ValueError("El JSON debe contener un recurso FHIR, una lista o un Bundle.")
    tipo = datos.get("resourceType")
    if tipo == "Bundle":
        entradas = datos.get("entry")
        if not isinstance(entradas, list):
            raise ValueError("El Bundle no contiene una lista 'entry'.")
        recursos = []
        for i, entrada in enumerate(entradas, 1):
            if not isinstance(entrada, dict) or not isinstance(entrada.get("resource"), dict):
                raise ValueError(f"La entrada {i} del Bundle no contiene un recurso válido.")
            recursos.extend(_entries(entrada["resource"]))
        return recursos
    return [datos]


def _first_coding(resource):
    try:
        return resource["code"]["coding"][0]
    except (KeyError, IndexError, TypeError):
        return {}


def _identifier(resource):
    """Devuelve primer identifier.value y system si existe."""
    for ident in resource.get("identifier", []) or []:
        if isinstance(ident, dict) and ident.get("value"):
            return str(ident["value"]).strip(), ident.get("system", "")
    return "", ""


def _human_name(resource):
    names = resource.get("name") or []
    if isinstance(names, dict):
        names = [names]
    if not names:
        return "", ""
    n = names[0] if isinstance(names[0], dict) else {}
    given = n.get("given") or []
    if isinstance(given, str):
        given = [given]
    first = " ".join(str(x) for x in given if x)
    family = str(n.get("family") or "").strip()
    # Fallback for a text-only HumanName.
    if not first and not family and n.get("text"):
        parts = str(n["text"]).strip().split()
        if len(parts) > 1:
            first, family = " ".join(parts[:-1]), parts[-1]
        elif parts:
            first = parts[0]
    return first, family


def _resource_ref(resource, key):
    ref = (resource.get(key) or {}).get("reference", "")
    if not isinstance(ref, str):
        return ""
    return ref.split("/")[-1] if "/" in ref else ref


def _parse_date(value):
    """Normaliza fechas ISO a YYYY-MM-DD; no inventa fechas faltantes."""
    if not value:
        return ""
    value = str(value).strip()
    try:
        if len(value) == 4 and value.isdigit():
            return value + "-01-01"
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10] if len(value) >= 10 else ""


def _resource_index(resources, kind):
    return {str(r.get("id")): r for r in resources
            if r.get("resourceType") == kind and r.get("id")}


def preparar_importacion(datos, con):
    """Analiza JSON, arma resumen y señala faltantes antes de tocar la BD."""
    recursos = _entries(datos)
    permitidos = {"Patient", "Practitioner", "Observation", "MedicationRequest"}
    desconocidos = sorted({r.get("resourceType", "(sin resourceType)") for r in recursos
                           if r.get("resourceType") not in permitidos})
    if desconocidos:
        raise ValueError("Tipos de recurso aún no admitidos por este importador: " + ", ".join(desconocidos))
    for i, r in enumerate(recursos, 1):
        if not r.get("resourceType"):
            raise ValueError(f"El recurso {i} no declara resourceType.")
        if r["resourceType"] in {"Observation", "MedicationRequest"} and not r.get("status"):
            raise ValueError(f"El recurso {i} ({r['resourceType']}) no contiene status.")

    patients = _resource_index(recursos, "Patient")
    practitioners = _resource_index(recursos, "Practitioner")
    con.row_factory = sqlite3.Row
    issues, actions = [], []
    patient_map, practitioner_map = {}, {}

    # Resolver pacientes existentes por DNI/identifier; crear solo si hay campos mínimos.
    for rid, p in patients.items():
        ident, _system = _identifier(p)
        first, family = _human_name(p)
        gender = str(p.get("gender") or "unknown").upper()
        sex_map = {"MALE": "M", "FEMALE": "F", "OTHER": "O", "UNKNOWN": "N"}
        sex = sex_map.get(gender, "N")
        birth = _parse_date(p.get("birthDate"))
        found = None
        if ident:
            found = con.execute("SELECT id FROM Pacientes WHERE dni=?", (ident,)).fetchone()
        if found:
            patient_map[rid] = int(found["id"])
            actions.append(("Paciente existente", f"Patient/{rid}: coincide con DNI/identifier {ident}; se reutiliza ID {found['id']}.", "info"))
        else:
            missing = [label for label, val in [("identifier/DNI", ident), ("nombre", first), ("apellido", family), ("birthDate", birth)] if not val]
            if missing:
                issues.append(f"Patient/{rid}: no se puede crear paciente nuevo; faltan {', '.join(missing)}.")
            else:
                actions.append(("Crear paciente", f"{family}, {first} | identificador {ident} | nacimiento {birth} | sexo {sex}", "create_patient"))
                patient_map[rid] = None

    # Profesionales: el esquema de Salud.db exige DNI, nombre, apellido, fecha nacimiento, sexo M/F y matrícula.
    for rid, pr in practitioners.items():
        ident, _system = _identifier(pr)
        first, family = _human_name(pr)
        gender = str(pr.get("gender") or "").upper()
        sex = {"MALE": "M", "FEMALE": "F"}.get(gender, "")
        birth = _parse_date(pr.get("birthDate"))
        quals = pr.get("qualification") or []
        matricula = ""
        especialidad_txt = ""
        for q in quals:
            if not isinstance(q, dict):
                continue
            for qi in q.get("identifier", []) or []:
                if qi.get("value"):
                    matricula = str(qi["value"]).strip(); break
            if not especialidad_txt:
                try: especialidad_txt = q["code"]["text"] or q["code"]["coding"][0]["display"]
                except (KeyError, IndexError, TypeError): pass
            if matricula: break
        found = con.execute("SELECT id FROM Profesionales WHERE dni=?", (ident,)).fetchone() if ident else None
        if found:
            practitioner_map[rid] = int(found["id"])
            actions.append(("Profesional existente", f"Practitioner/{rid}: coincide con identificador {ident}; se reutiliza ID {found['id']}.", "info"))
        else:
            missing = [label for label, val in [("identifier/DNI", ident), ("nombre", first), ("apellido", family), ("birthDate", birth), ("gender M/F", sex), ("matrícula", matricula)] if not val]
            if missing:
                issues.append(f"Practitioner/{rid}: no se puede crear profesional nuevo; faltan {', '.join(missing)}. El esquema local los exige.")
            else:
                actions.append(("Crear profesional", f"{family}, {first} | DNI/identifier {ident} | matrícula {matricula} | nacimiento {birth} | sexo {sex}", "create_practitioner"))
                practitioner_map[rid] = None

    # Preflight de observaciones y prescripciones.
    obs_count = rx_count = 0
    for r in recursos:
        tipo = r.get("resourceType")
        if tipo == "Observation":
            patient_ref = _resource_ref(r, "subject")
            if not patient_ref:
                issues.append("Observation sin subject.reference: no se puede asociar a un paciente.")
                continue
            if patient_ref not in patients:
                try: exists = con.execute("SELECT id FROM Pacientes WHERE CAST(id AS TEXT)=? OR dni=?", (patient_ref, patient_ref)).fetchone()
                except sqlite3.Error: exists = None
                if not exists:
                    issues.append(f"Observation: Patient/{patient_ref} no está incluido en el archivo ni se reconoce como ID/DNI local.")
            coding = _first_coding(r)
            code = str(coding.get("code") or "")
            if code not in LOINC:
                issues.append(f"Observation: código {code or '(sin código)'} no está mapeado a las columnas de SignosVitales; no se importará automáticamente.")
                continue
            val = (r.get("valueQuantity") or {}).get("value")
            if val is None:
                issues.append(f"Observation LOINC {code}: no contiene valueQuantity.value.")
                continue
            obs_count += 1
            actions.append(("Importar signo vital", f"Paciente Patient/{patient_ref} | {coding.get('display') or code}: {val} {(r.get('valueQuantity') or {}).get('unit','')} | fecha {r.get('effectiveDateTime') or r.get('issued') or 'no informada'}", "observation"))
        elif tipo == "MedicationRequest":
            patient_ref = _resource_ref(r, "subject")
            practitioner_ref = _resource_ref(r, "requester")
            medication = r.get("medicationCodeableConcept") or {}
            med_text = medication.get("text", "")
            codings = medication.get("coding") or []
            med_code = str(codings[0].get("code") or "") if codings else ""
            med_display = str(codings[0].get("display") or med_text or med_code or "Medicamento sin nombre") if codings else str(med_text or "Medicamento sin nombre")
            dosage = (r.get("dosageInstruction") or [{}])[0]
            dose_text = dosage.get("text") or ""
            if not dose_text:
                dose_qty = dosage.get("doseAndRate") or [{}]
                if dose_qty and isinstance(dose_qty[0], dict):
                    q = dose_qty[0].get("doseQuantity") or {}
                    if q.get("value") is not None:
                        dose_text = f"{q['value']} {q.get('unit','')}".strip()
            route = ""
            try: route = dosage["route"]["text"] or dosage["route"]["coding"][0]["display"]
            except (KeyError, IndexError, TypeError): pass
            freq = ""
            timing = dosage.get("timing") or {}
            try:
                rep = timing["repeat"]
                freq = f"Cada {rep['period']} {rep.get('periodUnit','')}; veces {rep.get('frequency','')}".strip()
            except (KeyError, TypeError): pass
            if not freq: freq = dose_text or "Según indicación importada"
            missing = []
            if not patient_ref: missing.append("subject.reference")
            elif patient_ref not in patients:
                try: patient_exists = con.execute("SELECT id FROM Pacientes WHERE CAST(id AS TEXT)=? OR dni=?", (patient_ref, patient_ref)).fetchone()
                except sqlite3.Error: patient_exists = None
                if not patient_exists: missing.append(f"paciente Patient/{patient_ref} no encontrado")
            if not practitioner_ref: missing.append("requester.reference (profesional prescriptor)")
            elif practitioner_ref not in practitioners:
                try: prof_exists = con.execute("SELECT id FROM Profesionales WHERE CAST(id AS TEXT)=? OR dni=?", (practitioner_ref, practitioner_ref)).fetchone()
                except sqlite3.Error: prof_exists = None
                if not prof_exists: missing.append(f"profesional Practitioner/{practitioner_ref} no encontrado")
            if not med_display or med_display == "Medicamento sin nombre": missing.append("medicationCodeableConcept")
            if not dose_text: missing.append("dosageInstruction/dosis")
            if missing:
                issues.append("MedicationRequest: faltan " + ", ".join(missing) + "; no se podrá importar esta prescripción.")
            else:
                rx_count += 1
                actions.append(("Importar prescripción", f"Paciente Patient/{patient_ref} | Profesional Practitioner/{practitioner_ref} | {med_display} | dosis {dose_text} | vía {route or 'no informada'}", "prescription"))

    # No importamos recursos clínicos si el JSON incluye referencias rotas o faltan campos obligatorios.
    return {"resources": recursos, "patients": patients, "practitioners": practitioners,
            "patient_map": patient_map, "practitioner_map": practitioner_map,
            "actions": actions, "issues": issues, "observations": obs_count,
            "prescriptions": rx_count, "resource_count": len(recursos)}


def _resolve_patient_id(ref, plan, con):
    if ref in plan["patient_map"] and plan["patient_map"][ref] is not None:
        return plan["patient_map"][ref]
    if ref in plan["patients"]:
        p = plan["patients"][ref]
        ident, _ = _identifier(p)
        if ident:
            row = con.execute("SELECT id FROM Pacientes WHERE dni=?", (ident,)).fetchone()
            if row: return row[0]
        first, family = _human_name(p)
        gender = str(p.get("gender") or "unknown").upper()
        sex = {"MALE":"M", "FEMALE":"F", "OTHER":"O", "UNKNOWN":"N"}.get(gender, "N")
        birth = _parse_date(p.get("birthDate"))
        cur = con.execute("""INSERT INTO Pacientes
            (dni,nombre,apellido,fecha_nacimiento,sexo,telefono,email,domicilio,obra_social,activo)
            VALUES (?,?,?,?,?,NULL,NULL,NULL,NULL,1)""", (ident, first, family, birth, sex))
        new_id = cur.lastrowid
        plan["patient_map"][ref] = new_id
        return new_id
    row = con.execute("SELECT id FROM Pacientes WHERE CAST(id AS TEXT)=? OR dni=?", (ref, ref)).fetchone()
    if not row: raise ValueError(f"No se encontró paciente local para la referencia Patient/{ref}.")
    return row[0]


def _resolve_practitioner_id(ref, plan, con):
    if ref in plan["practitioner_map"] and plan["practitioner_map"][ref] is not None:
        return plan["practitioner_map"][ref]
    if ref not in plan["practitioners"]:
        row = con.execute("SELECT id FROM Profesionales WHERE CAST(id AS TEXT)=? OR dni=?", (ref, ref)).fetchone()
        if row: return row[0]
        raise ValueError(f"No se encontró profesional local para Practitioner/{ref}.")
    p = plan["practitioners"][ref]
    ident, _ = _identifier(p)
    row = con.execute("SELECT id FROM Profesionales WHERE dni=?", (ident,)).fetchone()
    if row: return row[0]
    first, family = _human_name(p)
    sex = {"MALE":"M", "FEMALE":"F"}.get(str(p.get("gender") or "").upper(), "")
    birth = _parse_date(p.get("birthDate"))
    matricula = ""
    for q in p.get("qualification") or []:
        for qi in q.get("identifier", []) or []:
            if qi.get("value"):
                matricula = str(qi["value"]).strip(); break
        if matricula: break
    cur = con.execute("""INSERT INTO Profesionales
        (dni,nombre,apellido,fecha_nacimiento,sexo,matricula,especialidad_id,telefono,email,activo)
        VALUES (?,?,?,?,?,?,NULL,NULL,NULL,1)""", (ident, first, family, birth, sex, matricula))
    new_id = cur.lastrowid
    plan["practitioner_map"][ref] = new_id
    return new_id


def _record_audit(con, tabla, registro_id, descripcion, origen, external_id, payload):
    """La auditoría autenticada se integra desde el menú principal del sistema.

    Esta ventana independiente no dispone de la sesión real del usuario; por eso no
    atribuye la operación a un usuario elegido arbitrariamente. Al integrarla en el
    menú autenticado, debe llamarse al módulo Auditoria_utiles con el usuario de sesión.
    """
    return


def ejecutar_importacion(plan, ruta_archivo):
    """Importa transaccionalmente; si falla un recurso, revierte todo el lote."""
    if plan["issues"]:
        raise ValueError("Hay observaciones pendientes de resolver. No se importó ningún dato.\n\n- " + "\n- ".join(plan["issues"]))
    con = conectar_bd()
    try:
        cur = con.cursor()
        before_patients = cur.execute("SELECT COUNT(*) FROM Pacientes").fetchone()[0]
        before_practitioners = cur.execute("SELECT COUNT(*) FROM Profesionales").fetchone()[0]
        # Inserta pacientes y profesionales incluidos en el Bundle, si todavía no existen.
        for rid, p in plan["patients"].items():
            _resolve_patient_id(rid, plan, cur)
        for rid, p in plan["practitioners"].items():
            _resolve_practitioner_id(rid, plan, cur)

        inserted = {"pacientes": 0, "profesionales": 0, "signos_vitales": 0, "prescripciones": 0}
        # Agrupa Observations por paciente y fecha/hora para que una serie de signos
        # (presión, pulso, temperatura, SpO2) se convierta en una sola fila local.
        grupos = {}
        for r in plan["resources"]:
            if r.get("resourceType") != "Observation":
                continue
            coding = _first_coding(r)
            code = str(coding.get("code") or "")
            if code not in LOINC:
                continue
            column, _unit = LOINC[code]
            val = (r.get("valueQuantity") or {}).get("value")
            fecha = r.get("effectiveDateTime") or r.get("issued") or datetime.now().isoformat(timespec="seconds")
            fecha = str(fecha).replace("T", " ").replace("Z", "")
            patient_ref = _resource_ref(r, "subject")
            patient_id = _resolve_patient_id(patient_ref, plan, cur)
            key = (patient_id, fecha)
            grupo = grupos.setdefault(key, {"presion_sistolica":None,"presion_diastolica":None,"frecuencia_cardiaca":None,"temperatura":None,"saturacion_oxigeno":None,"motivo": "Importación FHIR"})
            try:
                number = float(val)
                if column in {"presion_sistolica", "presion_diastolica", "frecuencia_cardiaca", "saturacion_oxigeno"}:
                    if not number.is_integer(): raise ValueError(f"Valor no entero para {column}: {val}")
                    grupo[column] = int(number)
                else:
                    grupo[column] = number
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Valor no válido en Observation {code}: {val}") from exc
        for (patient_id, fecha), values in grupos.items():
            cur.execute("""INSERT INTO SignosVitales
                (paciente_id,fecha_hora,presion_sistolica,presion_diastolica,frecuencia_cardiaca,temperatura,saturacion_oxigeno,motivo_consulta,medico_id,activo)
                VALUES (?,?,?,?,?,?,?,?,NULL,1)""",
                (patient_id, fecha, values["presion_sistolica"], values["presion_diastolica"], values["frecuencia_cardiaca"], values["temperatura"], values["saturacion_oxigeno"], values["motivo"]))
            inserted["signos_vitales"] += 1
            _record_audit(cur, "SignosVitales", cur.lastrowid, "Importación FHIR Observation", "FHIR JSON", "", str(ruta_archivo))

        for r in plan["resources"]:
            tipo = r.get("resourceType")
            if tipo == "MedicationRequest":
                patient_id = _resolve_patient_id(_resource_ref(r, "subject"), plan, cur)
                practitioner_id = _resolve_practitioner_id(_resource_ref(r, "requester"), plan, cur)
                med = r.get("medicationCodeableConcept") or {}
                codings = med.get("coding") or []
                code = str(codings[0].get("code") or "") if codings else ""
                name = str((codings[0].get("display") if codings else "") or med.get("text") or "Medicamento importado").strip()
                farmaco = cur.execute("SELECT id FROM Farmacos WHERE codigo=?", (code,)).fetchone() if code else None
                if not farmaco:
                    farmaco = cur.execute("SELECT id FROM Farmacos WHERE lower(nombre)=lower(?)", (name,)).fetchone()
                if farmaco:
                    farmaco_id = farmaco[0]
                else:
                    farmaco_code = code or ("FHIR-" + str(abs(hash(name))))
                    cur.execute("INSERT INTO Farmacos (codigo,nombre,activo) VALUES (?,?,1)", (farmaco_code, name))
                    farmaco_id = cur.lastrowid
                dosage = (r.get("dosageInstruction") or [{}])[0]
                dose_text = dosage.get("text") or ""
                if not dose_text:
                    dq = (dosage.get("doseAndRate") or [{}])[0].get("doseQuantity") or {}
                    if dq.get("value") is not None: dose_text = f"{dq['value']} {dq.get('unit','')}".strip()
                route = ""
                try: route = dosage["route"]["text"] or dosage["route"]["coding"][0]["display"]
                except (KeyError, IndexError, TypeError): pass
                timing = dosage.get("timing") or {}
                repeat = timing.get("repeat") or {}
                freq = dosage.get("text") or ""
                if not freq and repeat:
                    freq = f"{repeat.get('frequency','')} veces cada {repeat.get('period','')} {repeat.get('periodUnit','')}".strip()
                if not freq: freq = dose_text
                authored = str(r.get("authoredOn") or datetime.now().date().isoformat())[:19]
                quantity = None
                try: quantity = int((r.get("dispenseRequest") or {}).get("quantity", {}).get("value"))
                except (TypeError, ValueError): pass
                cur.execute("""INSERT INTO Prescripciones
                    (paciente_id,profesional_id,farmaco_id,dosis,via_administracion,frecuencia,duracion,cantidad,indicaciones,fecha_prescripcion,fecha_inicio,fecha_fin,activo)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (patient_id, practitioner_id, farmaco_id, dose_text, route or "No informada", freq or "No informada", None, quantity, dosage.get("text"), authored, None, None))
                inserted["prescripciones"] += 1
                _record_audit(cur, "Prescripciones", cur.lastrowid, "Importación FHIR MedicationRequest", "FHIR JSON", str(r.get("id") or ""), str(ruta_archivo))
        inserted["pacientes"] = cur.execute("SELECT COUNT(*) FROM Pacientes").fetchone()[0] - before_patients
        inserted["profesionales"] = cur.execute("SELECT COUNT(*) FROM Profesionales").fetchone()[0] - before_practitioners
        con.commit()
        return inserted
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


class AppFHIR:
    def __init__(self, root):
        self.root = root
        root.title("OpenHIS-UNLaM | Interoperabilidad FHIR")
        root.geometry("1080x740")
        root.minsize(850, 600)
        self.plan = None
        self.archivo_importar = None
        self._crear_interfaz()
        self.cargar_pacientes()

    def _crear_interfaz(self):
        cab = ttk.Frame(self.root, padding=14)
        cab.pack(fill="x")
        ttk.Label(cab, text="INTEROPERABILIDAD EN SALUD — FHIR", font=("Arial", 16, "bold")).pack(anchor="w")
        ttk.Label(cab, text="Exportación, revisión e importación controlada de JSON FHIR", font=("Arial", 10)).pack(anchor="w", pady=(3, 0))
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        exportar = ttk.Frame(self.tabs, padding=12)
        importar = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(exportar, text="Exportar signos vitales")
        self.tabs.add(importar, text="Importar FHIR JSON")
        ttk.Label(exportar, text="Paciente activo:").grid(row=0, column=0, sticky="w", pady=5)
        self.cb_paciente = ttk.Combobox(exportar, state="readonly", width=60)
        self.cb_paciente.grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        self.cb_paciente.bind("<<ComboboxSelected>>", lambda _e: self.cargar_signos())
        ttk.Label(exportar, text="Registro de signos vitales:").grid(row=1, column=0, sticky="w", pady=5)
        self.cb_signos = ttk.Combobox(exportar, state="readonly", width=60)
        self.cb_signos.grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(exportar, text="Actualizar pacientes", command=self.cargar_pacientes).grid(row=2, column=1, sticky="w", padx=8, pady=8)
        ttk.Button(exportar, text="Exportar signos vitales y prescripciones (FHIR JSON)", command=self.exportar).grid(row=3, column=1, sticky="w", padx=8, pady=8)
        self.txt_export = tk.Text(exportar, height=20, wrap="none", font=("Consolas", 9))
        self.txt_export.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=8)
        exportar.columnconfigure(1, weight=1); exportar.rowconfigure(4, weight=1)

        top = ttk.Frame(importar); top.pack(fill="x")
        ttk.Button(top, text="Seleccionar JSON…", command=self.seleccionar_archivo).pack(side="left")
        ttk.Button(top, text="Analizar y mostrar", command=self.validar_archivo).pack(side="left", padx=8)
        self.btn_importar = ttk.Button(top, text="Confirmar e importar a Salud.db…", command=self.confirmar_importacion, state="disabled")
        self.btn_importar.pack(side="left", padx=8)
        self.lbl_archivo = ttk.Label(importar, text="No se seleccionó ningún archivo.")
        self.lbl_archivo.pack(anchor="w", pady=8)
        self.txt_import = tk.Text(importar, wrap="word", font=("Consolas", 9))
        self.txt_import.pack(fill="both", expand=True)
        self.lbl_estado = ttk.Label(importar, text="Paso 1: seleccione un JSON y analícelo. Todavía no se escribe en la base.", foreground="#245B83")
        self.lbl_estado.pack(anchor="w", pady=(8, 0))

    def cargar_pacientes(self):
        try:
            con = conectar_bd()
            try:
                self.pacientes = con.execute("SELECT id,dni,apellido,nombre FROM Pacientes WHERE activo=1 ORDER BY apellido,nombre").fetchall()
            finally: con.close()
            self.cb_paciente["values"] = [f"{p[0]} | {p[2]}, {p[3]} | DNI {p[1]}" for p in self.pacientes]
            if self.pacientes:
                self.cb_paciente.current(0); self.cargar_signos()
            else: self.cb_signos["values"] = []
        except Exception as exc:
            messagebox.showerror("Base de datos", str(exc), parent=self.root)

    def cargar_signos(self):
        idx = self.cb_paciente.current()
        if idx < 0: return
        con = conectar_bd()
        try:
            rows = con.execute("SELECT id,fecha_hora,motivo_consulta FROM SignosVitales WHERE paciente_id=? AND activo=1 ORDER BY fecha_hora DESC", (self.pacientes[idx][0],)).fetchall()
            self.signos = rows
            self.cb_signos["values"] = [f"{r[0]} | {r[1] or 'sin fecha'} | {r[2] or 'sin motivo'}" for r in rows]
            if rows: self.cb_signos.current(0)
        finally: con.close()

    def exportar(self):
        idx = self.cb_paciente.current()
        if idx < 0:
            messagebox.showwarning("Seleccione un paciente", "Seleccione un paciente antes de exportar.", parent=self.root)
            return
        paciente_id, dni, apellido, nombre = self.pacientes[idx]
        con = conectar_bd()
        try:
            paciente = con.execute("SELECT dni,nombre,apellido,fecha_nacimiento,sexo FROM Pacientes WHERE id=?", (paciente_id,)).fetchone()
            signos = con.execute("""SELECT id,fecha_hora,presion_sistolica,presion_diastolica,frecuencia_cardiaca,temperatura,saturacion_oxigeno,motivo_consulta
                FROM SignosVitales WHERE paciente_id=? AND activo=1 ORDER BY fecha_hora""", (paciente_id,)).fetchall()
            rx_rows = con.execute("""SELECT rx.id,rx.dosis,rx.via_administracion,rx.frecuencia,rx.duracion,rx.cantidad,rx.indicaciones,rx.fecha_prescripcion,rx.fecha_inicio,rx.fecha_fin,
                f.codigo,f.nombre,pr.id,pr.dni,pr.nombre,pr.apellido,pr.fecha_nacimiento,pr.sexo,pr.matricula
                FROM Prescripciones rx JOIN Farmacos f ON f.id=rx.farmaco_id JOIN Profesionales pr ON pr.id=rx.profesional_id
                WHERE rx.paciente_id=? AND rx.activo=1 ORDER BY rx.fecha_prescripcion""", (paciente_id,)).fetchall()
        finally:
            con.close()
        patient_ref = f"patient-{paciente_id}"
        gender = {"M":"male", "F":"female", "O":"other", "N":"unknown"}.get(str(paciente[4] or "").upper(), "unknown")
        patient_resource = {"resourceType":"Patient", "id":patient_ref, "active":True,
            "identifier":[{"system":"urn:openhis:pacientes", "value":str(paciente[0])}],
            "name":[{"family":paciente[2], "given":[paciente[1]]}], "gender":gender}
        if paciente[3]: patient_resource["birthDate"] = str(paciente[3])[:10]
        resources = [patient_resource]
        loinc_defs = [("8480-6","Systolic blood pressure",2,"mm[Hg]"),("8462-4","Diastolic blood pressure",3,"mm[Hg]"),("8867-4","Heart rate",4,"/min"),("8310-5","Body temperature",5,"Cel"),("59408-5","Oxygen saturation",6,"%")]
        for signo in signos:
            sid, fecha = signo[0], signo[1]
            for code, display, colidx, unit in loinc_defs:
                value = signo[colidx]
                if value is None: continue
                resources.append({"resourceType":"Observation", "id":f"obs-{sid}-{code}", "status":"final",
                    "subject":{"reference":f"Patient/{patient_ref}"}, "effectiveDateTime":str(fecha or datetime.now(timezone.utc).isoformat()),
                    "code":{"coding":[{"system":"http://loinc.org","code":code,"display":display}]},
                    "valueQuantity":{"value":value,"unit":unit}})
        seen_practitioners = set()
        for row in rx_rows:
            (rxid,dosis,via,frecuencia,duracion,cantidad,indicaciones,fecha_prescripcion,fecha_inicio,fecha_fin,
             farmaco_codigo,farmaco_nombre,prof_id,prof_dni,prof_nombre,prof_apellido,prof_nacimiento,prof_sexo,matricula) = row
            practitioner_ref = f"practitioner-{prof_id}"
            if prof_id not in seen_practitioners:
                pgender = {"M":"male", "F":"female"}.get(str(prof_sexo or "").upper(), "unknown")
                pr = {"resourceType":"Practitioner","id":practitioner_ref,"active":True,
                    "identifier":[{"system":"urn:openhis:profesionales","value":str(prof_dni)}],
                    "name":[{"family":prof_apellido,"given":[prof_nombre]}],"gender":pgender,
                    "qualification":[{"identifier":[{"value":str(matricula)}]}]}
                if prof_nacimiento: pr["birthDate"] = str(prof_nacimiento)[:10]
                resources.append(pr); seen_practitioners.add(prof_id)
            dose_text = " ".join(x for x in [str(dosis or "").strip(), str(frecuencia or "").strip()] if x)
            dosage = {"text":dose_text or str(indicaciones or "Indicación no informada")}
            if via: dosage["route"] = {"text":str(via)}
            med_code = str(farmaco_codigo or "")
            med = {"text":str(farmaco_nombre or "Medicamento")}
            if med_code: med["coding"] = [{"system":"urn:openhis:farmacos","code":med_code,"display":str(farmaco_nombre)}]
            rx = {"resourceType":"MedicationRequest","id":f"medrx-{rxid}","status":"active",
                "intent":"order","subject":{"reference":f"Patient/{patient_ref}"},
                "requester":{"reference":f"Practitioner/{practitioner_ref}"},
                "medicationCodeableConcept":med,"dosageInstruction":[dosage],
                "authoredOn":str(fecha_prescripcion or datetime.now().date().isoformat())[:19]}
            if cantidad is not None: rx["dispenseRequest"]={"quantity":{"value":cantidad}}
            if indicaciones: rx["note"]=[{"text":str(indicaciones)}]
            resources.append(rx)
        salida={"resourceType":"Bundle","type":"collection","entry":[{"resource":r} for r in resources]}
        destino=filedialog.asksaveasfilename(parent=self.root,title="Guardar recursos FHIR",initialdir=str(CARPETA_INTERCAMBIO),initialfile=f"paciente_{paciente_id}_fhir.json",defaultextension=".json",filetypes=[("JSON","*.json")])
        if not destino: return
        Path(destino).write_text(json.dumps(salida,ensure_ascii=False,indent=2),encoding="utf-8")
        self.txt_export.delete("1.0","end"); self.txt_export.insert("1.0",json.dumps(salida,ensure_ascii=False,indent=2))
        n_obs=sum(1 for r in resources if r.get("resourceType")=="Observation")
        n_rx=sum(1 for r in resources if r.get("resourceType")=="MedicationRequest")
        messagebox.showinfo("Exportación finalizada",f"Se exportaron recursos FHIR:\n• Paciente: 1\n• Observations (signos vitales): {n_obs}\n• Profesionales: {len(seen_practitioners)}\n• Prescripciones: {n_rx}\n\n{destino}",parent=self.root)

    def seleccionar_archivo(self):
        ruta=filedialog.askopenfilename(parent=self.root,title="Seleccionar archivo FHIR JSON",filetypes=[("JSON","*.json"),("Todos los archivos","*.*")])
        if ruta:
            self.archivo_importar=Path(ruta); self.lbl_archivo.config(text=str(self.archivo_importar)); self.plan=None; self.btn_importar.config(state="disabled")
            self.lbl_estado.config(text="Archivo seleccionado. Pulse ‘Analizar y mostrar’ para revisar antes de importar.")

    def validar_archivo(self):
        if not self.archivo_importar:
            messagebox.showwarning("Archivo requerido","Seleccione primero un archivo JSON.",parent=self.root); return
        try:
            datos=json.loads(self.archivo_importar.read_text(encoding="utf-8"))
            con=conectar_bd()
            try: self.plan=preparar_importacion(datos,con)
            finally: con.close()
            preview=json.dumps(datos,ensure_ascii=False,indent=2)
            self.txt_import.delete("1.0","end"); self.txt_import.insert("1.0",preview)
            p=self.plan
            resumen=(f"ANÁLISIS PREVIO\nRecursos: {p['resource_count']} | Observations compatibles: {p['observations']} | Prescripciones: {p['prescriptions']}\n\n"
                     "ACCIONES DETECTADAS\n" + "\n".join(f"• {a[0]}: {a[1]}" for a in p['actions']))
            if p['issues']:
                resumen += "\n\nREVISIÓN NECESARIA — IMPORTACIÓN BLOQUEADA\n" + "\n".join(f"• {x}" for x in p['issues'])
                self.btn_importar.config(state="disabled")
                self.lbl_estado.config(text="Hay observaciones que resolver. No se importará nada hasta corregir el archivo.",foreground="#A33A2B")
            else:
                self.btn_importar.config(state="normal")
                self.lbl_estado.config(text="Previsualización lista. La base todavía no fue modificada.",foreground="#246B45")
            self.txt_import.insert("end","\n\n" + "="*70 + "\n" + resumen)
        except Exception as exc:
            self.plan=None; self.btn_importar.config(state="disabled")
            messagebox.showerror("JSON no válido o no compatible",str(exc),parent=self.root)

    def confirmar_importacion(self):
        if not self.plan or not self.archivo_importar:
            messagebox.showwarning("Falta análisis","Seleccione y analice un JSON antes de importar.",parent=self.root); return
        if self.plan["issues"]:
            messagebox.showerror("Importación bloqueada","El archivo tiene observaciones pendientes; no se importó nada.",parent=self.root); return
        p=self.plan
        mensaje=(f"Se va a importar a la base de datos Salud.db:\n\n"
                 f"• Recursos del archivo: {p['resource_count']}\n"
                 f"• Signos vitales/Observation: {p['observations']}\n"
                 f"• Prescripciones/MedicationRequest: {p['prescriptions']}\n\n"
                 "Los pacientes y profesionales se reutilizarán si coinciden por identificador; si no existen, se crearán cuando tengan todos los campos obligatorios.\n\n"
                 "¿Confirma la importación? Esta acción escribirá registros en la base de datos.")
        if not messagebox.askyesno("Confirmar importación",mensaje,icon="warning",parent=self.root): return
        try:
            resultado=ejecutar_importacion(p,self.archivo_importar)
            self.btn_importar.config(state="disabled")
            self.lbl_estado.config(text="Importación completada. Vuelva a analizar el archivo si desea repetir el proceso.",foreground="#246B45")
            messagebox.showinfo("Importación finalizada", "Se importaron los datos:\n\n" + "\n".join(f"• {k.replace('_',' ').capitalize()}: {v}" for k,v in resultado.items()) + "\n\nRevise la base antes de continuar.",parent=self.root)
            self.cargar_pacientes()
        except Exception as exc:
            messagebox.showerror("Error de importación", "No se completó la importación. La transacción se revirtió.\n\n"+str(exc),parent=self.root)

if __name__ == "__main__":
    root=tk.Tk(); AppFHIR(root); root.mainloop()
