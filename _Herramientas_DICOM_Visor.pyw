

# -*- coding: utf-8 -*-
"""OpenHIS-UNLaM: conversión de JPG/PNG a DICOM y anonimización.
Requiere Python 3, Pillow y pydicom. No requiere NumPy.
La conversión produce DICOM Secondary Capture. Revisar y validar antes de uso clínico.
"""
import os
import sqlite3
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import struct

try:
    from PIL import Image, ImageOps, ImageTk
    PIL_ERROR = None
except Exception as exc:
    Image = ImageOps = ImageTk = None
    PIL_ERROR = str(exc)

try:
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
    PYDICOM_ERROR = None
except Exception as exc:
    pydicom = None
    PYDICOM_ERROR = str(exc)

TITLE = "OpenHIS-UNLaM | Herramientas DICOM"

DEFAULT_INSTITUTION = "Hospital Universitario San Justo"
DEFAULT_INSTITUTION_ADDRESS = "San Justo - Buenos Aires"

def find_database_path():
    """Busca Salud.db en la carpeta del proyecto y ubicaciones habituales."""
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, "BD", "Salud.db"),
        os.path.join(base, "Salud.db"),
        os.path.join(os.getcwd(), "BD", "Salud.db"),
        os.path.join(os.getcwd(), "Salud.db"),
        os.path.join(os.path.dirname(base), "BD", "Salud.db"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    # Ruta esperada por el proyecto; si todavía no existe, no se crea una BD vacía.
    return os.path.join(base, "BD", "Salud.db")

def check_dependencies(parent=None):
    missing = []
    if Image is None:
        missing.append("Pillow")
    if pydicom is None:
        missing.append("pydicom")
    if missing:
        details = []
        if Image is None:
            details.append("Pillow: " + (PIL_ERROR or "no se pudo importar"))
        if pydicom is None:
            details.append("pydicom: " + (PYDICOM_ERROR or "no se pudo importar"))
        messagebox.showerror(
            "Faltan dependencias",
            "No se puede procesar la imagen. Faltan: " + ", ".join(missing) +
            ". No se necesita NumPy.\n\nEn PowerShell ejecutá:\n"
            "python -m ensurepip --upgrade\n"
            "python -m pip install --upgrade pip\n"
            "python -m pip install pillow pydicom\n\n"
            "Si ensurepip falla, copiá el mensaje completo.\n\n" + "\n".join(details),
            parent=parent
        )
        return False
    return True

def parse_date(value, label, allow_blank=True):
    value = value.strip()
    if not value and allow_blank:
        return ""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError:
        raise ValueError(f"{label}: usá AAAA-MM-DD, por ejemplo 2026-10-17.")

def parse_time(value):
    value = value.strip()
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%H:%M").strftime("%H%M%S")
    except ValueError:
        raise ValueError("La hora debe tener formato HH:MM, por ejemplo 14:35.")

def txt(value, limit=64):
    return value.strip()[:limit]

def convert_image(source, target, data):
    if not check_dependencies():
        return False
    if not os.path.isfile(source):
        raise FileNotFoundError("No se encuentra el archivo de imagen de origen.")
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("L")
        width, height = image.size
        pixels = image.tobytes()  # No necesita NumPy.

    now = datetime.now()
    sop_uid = generate_uid()
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = sop_uid
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.ImplementationClassUID = generate_uid()

    ds = FileDataset(target, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SOPInstanceUID = sop_uid
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.Modality = data["modality"] or "OT"
    ds.ImageType = ["DERIVED", "SECONDARY"]
    ds.ConversionType = "WSD"

    ds.PatientName = txt(data["patient_name"]) or "NO_INFORMADO"
    ds.PatientID = txt(data["patient_id"]) or "NO_INFORMADO"
    ds.PatientSex = data["sex"] if data["sex"] in ("M", "F", "O") else ""
    if data["birth_date"]:
        ds.PatientBirthDate = parse_date(data["birth_date"], "Fecha de nacimiento")

    ds.StudyDescription = txt(data["study_description"]) or "Imagen importada"
    ds.SeriesDescription = txt(data["series_description"]) or "Secondary Capture"
    ds.StudyID = txt(data["study_id"], 16)
    ds.AccessionNumber = txt(data["accession_number"], 16)
    ds.ReferringPhysicianName = txt(data["referring_physician"])
    ds.PerformingPhysicianName = txt(data["performing_physician"])
    ds.InstitutionName = txt(data["institution"])
    ds.InstitutionAddress = txt(data["institution_address"], 1024)
    ds.Manufacturer = "OpenHIS-UNLaM"

    study_date = parse_date(data["study_date"], "Fecha del estudio")
    study_time = parse_time(data["study_time"])
    ds.StudyDate = study_date
    ds.StudyTime = study_time
    ds.SeriesDate = study_date
    ds.SeriesTime = study_time
    ds.AcquisitionDate = study_date
    ds.AcquisitionTime = study_time
    ds.InstanceCreationDate = now.strftime("%Y%m%d")
    ds.InstanceCreationTime = now.strftime("%H%M%S")
    ds.ContentDate = now.strftime("%Y%m%d")
    ds.ContentTime = now.strftime("%H%M%S")
    ds.DerivationDescription = "Convertido desde JPG/PNG por OpenHIS-UNLaM"
    ds.PatientIdentityRemoved = "NO"

    ds.Rows = height
    ds.Columns = width
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = pixels
    ds.save_as(target, write_like_original=False)
    return True

REMOVE_TAGS = [
    "OtherPatientIDs", "OtherPatientIDsSequence", "OtherPatientNames",
    "PatientAddress", "PatientTelephoneNumbers", "PatientComments",
    "MedicalRecordLocator", "IssuerOfPatientID", "IssuerOfPatientIDQualifiersSequence",
    "AccessionNumber", "InstitutionName", "InstitutionAddress",
    "InstitutionalDepartmentName", "ReferringPhysicianName",
    "ReferringPhysicianAddress", "ReferringPhysicianTelephoneNumbers",
    "PerformingPhysicianName", "OperatorsName", "NameOfPhysiciansReadingStudy",
    "PhysiciansOfRecord", "RequestingPhysician", "StudyID",
    "StudyDescription", "SeriesDescription", "ProtocolName",
    "ScheduledPerformingPhysicianName", "ScheduledProcedureStepDescription",
    "RequestedProcedureDescription", "PatientBirthTime",
]

def anonymize_dicom(source, target):
    if not check_dependencies():
        return False
    ds = pydicom.dcmread(source)
    birth = str(getattr(ds, "PatientBirthDate", "") or "")
    birth_year = birth[:4] if len(birth) >= 4 and birth[:4].isdigit() else ""
    date = str(getattr(ds, "StudyDate", "") or getattr(ds, "AcquisitionDate", "") or "")
    study_year = date[:4] if len(date) >= 4 and date[:4].isdigit() else ""
    sex = str(getattr(ds, "PatientSex", "") or "").upper()
    if sex not in ("M", "F", "O"):
        sex = ""

    ds.remove_private_tags()
    for name in REMOVE_TAGS:
        if name in ds:
            del ds[name]

    def clean_nested(dataset):
        for elem in list(dataset):
            if elem.VR == "SQ":
                for item in elem.value:
                    item.remove_private_tags()
                    for name in ("PatientName", "PatientID", "PatientAddress",
                                 "PatientTelephoneNumbers", "ReferringPhysicianName",
                                 "PerformingPhysicianName", "OperatorsName",
                                 "InstitutionName", "AccessionNumber"):
                        if name in item:
                            del item[name]
                    clean_nested(item)
    clean_nested(ds)

    ds.PatientName = "ANONIMO"
    ds.PatientID = "ANONIMO"
    ds.PatientIdentityRemoved = "YES"
    ds.DeidentificationMethod = "OpenHIS-UNLaM"
    if birth_year:
        ds.PatientBirthDate = birth_year + "0101"
    elif "PatientBirthDate" in ds:
        del ds.PatientBirthDate
    if study_year:
        ds.StudyDate = study_year + "0101"
        if "AcquisitionDate" in ds:
            ds.AcquisitionDate = study_year + "0101"
        if "SeriesDate" in ds:
            ds.SeriesDate = study_year + "0101"
    else:
        for name in ("StudyDate", "AcquisitionDate", "SeriesDate"):
            if name in ds:
                del ds[name]
    if sex:
        ds.PatientSex = sex
    elif "PatientSex" in ds:
        del ds.PatientSex
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    if getattr(ds, "file_meta", None) is not None:
        ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.save_as(target, write_like_original=False)
    return True

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.geometry("1120x820")
        self.minsize(900, 700)
        self.configure(padx=14, pady=14)
        self.v = {}
        self.viewer_image_ref = None
        self.db_path = find_database_path()
        self.patient_records = {}
        self.professional_records = {}
        self.build()

    def var(self, key, default=""):
        self.v[key] = tk.StringVar(value=default)
        return self.v[key]

    def build(self):
        ttk.Label(self, text="Conversor JPG/PNG a DICOM",
                  font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(self, text="Ingresá los datos conocidos. El programa no puede inferir del archivo de imagen los datos clínicos que no contiene.",
                  wraplength=850).pack(anchor="w", pady=(3, 10))
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        tab = ttk.Frame(nb, padding=12)
        anon = ttk.Frame(nb, padding=12)
        viewer = ttk.Frame(nb, padding=10)
        nb.add(tab, text="Convertir imagen")
        nb.add(anon, text="Anonimizar DICOM")
        nb.add(viewer, text="Visor DICOM")
        self.build_viewer(viewer)

        defaults = {
            "source": "", "patient_name": "", "patient_id": "", "birth_date": "",
            "sex": "", "study_date": datetime.now().strftime("%Y-%m-%d"),
            "study_time": datetime.now().strftime("%H:%M"),
            "study_description": "Imagen importada desde JPG/PNG",
            "series_description": "Secondary Capture", "study_id": "",
            "accession_number": "", "referring_physician": "",
            "performing_physician": "", "institution": DEFAULT_INSTITUTION,
            "institution_address": DEFAULT_INSTITUTION_ADDRESS,
            "modality": "OT", "anon_source": ""
        }
        for k, v in defaults.items():
            self.var(k, v)

        row = 0
        ttk.Label(tab, text="Imagen JPG/JPEG/PNG").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(tab, textvariable=self.v["source"]).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(tab, text="Examinar…", command=self.pick_image).grid(row=row, column=2, padx=5)
        row += 1

        # Selectores opcionales desde la base del sistema. Los campos manuales siguen editables.
        ttk.Label(tab, text="Paciente registrado (opcional)").grid(row=row, column=0, sticky="w", pady=4)
        self.patient_choice = tk.StringVar(value="")
        self.patient_combo = ttk.Combobox(tab, textvariable=self.patient_choice, state="readonly")
        self.patient_combo.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        self.patient_combo.bind("<<ComboboxSelected>>", self.on_patient_selected)
        row += 1

        ttk.Label(tab, text="Profesional derivante registrado (opcional)").grid(row=row, column=0, sticky="w", pady=4)
        self.referrer_choice = tk.StringVar(value="")
        self.referrer_combo = ttk.Combobox(tab, textvariable=self.referrer_choice, state="readonly")
        self.referrer_combo.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        self.referrer_combo.bind("<<ComboboxSelected>>", self.on_referrer_selected)
        row += 1

        ttk.Label(tab, text="Profesional actuante registrado (opcional)").grid(row=row, column=0, sticky="w", pady=4)
        self.performer_choice = tk.StringVar(value="")
        self.performer_combo = ttk.Combobox(tab, textvariable=self.performer_choice, state="readonly")
        self.performer_combo.grid(row=row, column=1, columnspan=3, sticky="ew", pady=4)
        self.performer_combo.bind("<<ComboboxSelected>>", self.on_performer_selected)
        row += 1

        self.db_status = tk.StringVar(value="Conectando con la base de datos…")
        ttk.Label(tab, textvariable=self.db_status, foreground="#555555", wraplength=850).grid(
            row=row, column=0, columnspan=4, sticky="w", pady=(0, 6))
        row += 1
        self.load_database_choices()

        pairs = [
            ("patient_name", "Nombre del paciente", "patient_id", "ID del paciente"),
            ("birth_date", "Nacimiento (AAAA-MM-DD)", "sex", "Sexo"),
            ("referring_physician", "Profesional derivante", "performing_physician", "Profesional actuante"),
            ("institution", "Institución", "institution_address", "Dirección institución"),
            ("study_date", "Fecha del estudio (AAAA-MM-DD)", "study_time", "Hora (HH:MM)"),
            ("study_description", "Descripción del estudio", "series_description", "Descripción de serie"),
            ("study_id", "ID del estudio", "accession_number", "N.º de acceso"),
            ("modality", "Modalidad DICOM", "", ""),
        ]
        for left, ll, right, rl in pairs:
            ttk.Label(tab, text=ll).grid(row=row, column=0, sticky="w", pady=4)
            if left == "sex":
                w = ttk.Combobox(tab, textvariable=self.v[left], values=["", "F", "M", "O"], state="readonly")
            elif left == "modality":
                w = ttk.Combobox(tab, textvariable=self.v[left], values=["OT", "SC", "XC"], state="readonly")
            else:
                w = ttk.Entry(tab, textvariable=self.v[left])
            w.grid(row=row, column=1, sticky="ew", pady=4, padx=(0, 8))
            if right:
                ttk.Label(tab, text=rl).grid(row=row, column=2, sticky="w", pady=4)
                rw = ttk.Combobox(tab, textvariable=self.v[right], values=["", "F", "M", "O"], state="readonly") if right == "sex" else ttk.Entry(tab, textvariable=self.v[right])
                rw.grid(row=row, column=3, sticky="ew", pady=4)
            row += 1

        ttk.Button(tab, text="Convertir y guardar DICOM…", command=self.convert).grid(row=row, column=0, sticky="w", pady=(14, 8))
        ttk.Label(tab, text="La creación del archivo se registra automáticamente. La última visualización debe registrarse en una bitácora de auditoría del sistema.",
                  wraplength=800).grid(row=row+1, column=0, columnspan=4, sticky="w")
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(3, weight=1)

        ttk.Label(anon, text="DICOM de entrada").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(anon, textvariable=self.v["anon_source"]).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(anon, text="Examinar…", command=self.pick_dicom).grid(row=1, column=1, padx=6)
        ttk.Label(anon, text="Conserva año de nacimiento, año del estudio y sexo; elimina identificadores habituales y grupos privados. No borra texto identificatorio impreso en los píxeles.",
                  wraplength=700).grid(row=2, column=0, columnspan=2, sticky="w", pady=14)
        ttk.Button(anon, text="Anonimizar y guardar como…", command=self.anonymize).grid(row=3, column=0, sticky="w")
        anon.columnconfigure(0, weight=1)
        ttk.Label(self, text="Prototipo educativo: validar el DICOM con un visor y revisar privacidad antes de uso clínico.",
                  foreground="#8a3b12", wraplength=850).pack(anchor="w", pady=(10, 0))


    def load_database_choices(self):
        """Carga pacientes y profesionales activos de Salud.db; si falla, deja habilitada la carga manual."""
        blank = ["— Ingresar manualmente / no está en la tabla —"]
        self.patient_records = {}
        self.professional_records = {}
        patients, professionals = [], []
        try:
            if not os.path.isfile(self.db_path):
                raise FileNotFoundError(f"No se encontró Salud.db en: {self.db_path}")
            with sqlite3.connect(self.db_path) as con:
                con.row_factory = sqlite3.Row
                patients = con.execute(
                    "SELECT id, dni, nombre, apellido, fecha_nacimiento, sexo "
                    "FROM Pacientes WHERE COALESCE(activo,1)=1 ORDER BY apellido, nombre"
                ).fetchall()
                professionals = con.execute(
                    "SELECT id, dni, nombre, apellido, matricula, activo "
                    "FROM Profesionales WHERE COALESCE(activo,1)=1 ORDER BY apellido, nombre"
                ).fetchall()

            p_labels = blank[:]
            for r in patients:
                label = f'{r["apellido"]}, {r["nombre"]} | DNI {r["dni"]} | ID {r["id"]}'
                self.patient_records[label] = dict(r)
                p_labels.append(label)
            doc_labels = blank[:]
            for r in professionals:
                matricula = r["matricula"] or "sin matrícula"
                label = f'{r["apellido"]}, {r["nombre"]} | Matr. {matricula} | DNI {r["dni"]}'
                self.professional_records[label] = dict(r)
                doc_labels.append(label)

            self.patient_combo["values"] = p_labels
            self.referrer_combo["values"] = doc_labels
            self.performer_combo["values"] = doc_labels
            self.patient_choice.set(blank[0])
            self.referrer_choice.set(blank[0])
            self.performer_choice.set(blank[0])
            self.db_status.set(
                f"Base conectada: {self.db_path} | {len(patients)} pacientes activos y "
                f"{len(professionals)} profesionales activos. También podés escribir datos manualmente."
            )
        except Exception as exc:
            self.patient_combo["values"] = blank
            self.referrer_combo["values"] = blank
            self.performer_combo["values"] = blank
            self.patient_choice.set(blank[0])
            self.referrer_choice.set(blank[0])
            self.performer_choice.set(blank[0])
            self.db_status.set(
                f"No se pudieron cargar las tablas ({exc}). La carga manual sigue disponible. "
                "Verificá la ubicación de Salud.db."
            )

    def on_patient_selected(self, _event=None):
        record = self.patient_records.get(self.patient_choice.get())
        if not record:
            return
        self.v["patient_name"].set(f'{record["nombre"]} {record["apellido"]}')
        self.v["patient_id"].set(str(record["dni"] or ""))
        birth = str(record["fecha_nacimiento"] or "")
        # La tabla puede guardar fecha ISO o timestamp; DICOM espera AAAAMMDD.
        if len(birth) >= 10 and birth[4] == "-" and birth[7] == "-":
            birth = birth[:10]
        elif len(birth) == 8 and birth.isdigit():
            birth = f"{birth[:4]}-{birth[4:6]}-{birth[6:8]}"
        self.v["birth_date"].set(birth)
        sex = str(record["sexo"] or "").upper()
        self.v["sex"].set(sex if sex in ("F", "M", "O") else "")

    def on_referrer_selected(self, _event=None):
        record = self.professional_records.get(self.referrer_choice.get())
        if record:
            self.v["referring_physician"].set(f'{record["apellido"]}^{record["nombre"]}')

    def on_performer_selected(self, _event=None):
        record = self.professional_records.get(self.performer_choice.get())
        if record:
            self.v["performing_physician"].set(f'{record["apellido"]}^{record["nombre"]}')

    def build_viewer(self, parent):
        """Pestaña para inspeccionar los metadatos y previsualizar imágenes DICOM comunes."""
        top = ttk.Frame(parent)
        top.pack(fill="x", pady=(0, 8))
        self.viewer_path = tk.StringVar()
        ttk.Label(top, text="Archivo DICOM:").pack(side="left")
        ttk.Entry(top, textvariable=self.viewer_path).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Abrir DICOM…", command=self.open_viewer_file).pack(side="left")

        split = ttk.Panedwindow(parent, orient="horizontal")
        split.pack(fill="both", expand=True)
        meta_frame = ttk.Frame(split, padding=(0, 0, 6, 0))
        image_frame = ttk.Frame(split, padding=(6, 0, 0, 0))
        split.add(meta_frame, weight=3)
        split.add(image_frame, weight=2)

        ttk.Label(meta_frame, text="Metadatos DICOM", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        text_frame = ttk.Frame(meta_frame)
        text_frame.pack(fill="both", expand=True)
        self.metadata_text = tk.Text(text_frame, wrap="none", font=("Consolas", 9), state="disabled")
        yscroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.metadata_text.yview)
        xscroll = ttk.Scrollbar(text_frame, orient="horizontal", command=self.metadata_text.xview)
        self.metadata_text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.metadata_text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        ttk.Label(image_frame, text="Vista previa de imagen", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        self.viewer_image_label = ttk.Label(image_frame, text="Abrí un archivo DICOM para ver la imagen.", anchor="center", justify="center")
        self.viewer_image_label.pack(fill="both", expand=True)
        self.viewer_status = tk.StringVar(value="Sin archivo cargado")
        ttk.Label(image_frame, textvariable=self.viewer_status, wraplength=300).pack(fill="x", pady=(6, 0))
        ttk.Label(parent, text="La vista previa depende del formato de píxeles y la compresión del DICOM. No es un visor diagnóstico certificado.",
                  foreground="#8a3b12", wraplength=800).pack(anchor="w", pady=(8, 0))

    def open_viewer_file(self):
        path = filedialog.askopenfilename(parent=self, title="Abrir archivo DICOM",
            filetypes=[("Archivos DICOM", "*.dcm"), ("Todos los archivos", "*.*")])
        if path:
            self.viewer_path.set(path)
            self.load_viewer(path)

    def load_viewer(self, path):
        if not check_dependencies(self):
            return
        try:
            ds = pydicom.dcmread(path, force=True)
            lines = [f"Archivo: {os.path.basename(path)}", "=" * 88]
            if getattr(ds, "file_meta", None):
                lines.append("[FILE META INFORMATION]")
                for elem in ds.file_meta:
                    lines.append(self.format_element(elem, 0))
                lines.append("")
            lines.append("[DATASET / METADATOS]")
            for elem in ds:
                lines.extend(self.format_element_recursive(elem, 0))
            self.metadata_text.configure(state="normal")
            self.metadata_text.delete("1.0", "end")
            self.metadata_text.insert("1.0", "\n".join(lines))
            self.metadata_text.configure(state="disabled")
            self.show_dicom_image(ds)
        except Exception as exc:
            messagebox.showerror("No se pudo abrir el DICOM", f"{exc}\n\nDetalle:\n{traceback.format_exc()}", parent=self)

    @staticmethod
    def format_element(elem, level=0):
        tag = f"({elem.tag.group:04X},{elem.tag.element:04X})"
        name = elem.keyword or elem.name
        value = str(elem.value).replace("\n", " ")
        if len(value) > 500:
            value = value[:500] + "… [valor abreviado]"
        return f"{'  '*level}{tag} {name} [{elem.VR}] = {value}"

    def format_element_recursive(self, elem, level=0):
        if elem.VR != "SQ":
            return [self.format_element(elem, level)]
        out = [f"{'  '*level}({elem.tag.group:04X},{elem.tag.element:04X}) {elem.keyword or elem.name} [SQ] - {len(elem.value)} elemento(s)"]
        for i, item in enumerate(elem.value):
            out.append(f"{'  '*(level+1)}-- Elemento de secuencia {i+1} --")
            for child in item:
                out.extend(self.format_element_recursive(child, level+2))
        return out

    def show_dicom_image(self, ds):
        """Decodificador básico sin NumPy para DICOM sin compresión: MONOCHROME 8/16 bits y RGB 8 bits."""
        try:
            if not hasattr(ds, "PixelData"):
                self.viewer_image_label.configure(image="", text="Este DICOM no contiene PixelData.")
                self.viewer_image_ref = None
                self.viewer_status.set("No contiene imagen")
                return
            syntax = getattr(getattr(ds, "file_meta", None), "TransferSyntaxUID", None)
            if syntax and getattr(syntax, "is_compressed", False):
                self.viewer_image_label.configure(image="", text="Imagen comprimida.\nLa vista previa básica no puede decodificar esta compresión.")
                self.viewer_image_ref = None
                self.viewer_status.set(f"Transfer Syntax: {syntax}; se requiere un decodificador compatible")
                return
            rows = int(ds.Rows); cols = int(ds.Columns)
            samples = int(getattr(ds, "SamplesPerPixel", 1))
            bits = int(getattr(ds, "BitsAllocated", 8))
            photo = str(getattr(ds, "PhotometricInterpretation", "MONOCHROME2"))
            raw = bytes(ds.PixelData)
            expected = rows * cols * samples * max(bits // 8, 1)
            if len(raw) < expected:
                raise ValueError(f"PixelData incompleto: se esperaban al menos {expected} bytes y hay {len(raw)}.")
            if samples == 1 and bits == 8:
                im = Image.frombytes("L", (cols, rows), raw[:rows*cols])
                if photo == "MONOCHROME1":
                    im = ImageOps.invert(im)
            elif samples == 1 and bits == 16:
                endian = ">" if syntax and getattr(syntax, "is_little_endian", True) is False else "<"
                count = rows * cols
                vals = struct.unpack(endian + ("h" if int(getattr(ds, "PixelRepresentation", 0)) else "H") * count,
                                      raw[:count*2])
                low, high = min(vals), max(vals)
                if high == low:
                    scaled = bytes([0]) * count
                else:
                    scaled = bytes(max(0, min(255, int((v-low)*255/(high-low)))) for v in vals)
                im = Image.frombytes("L", (cols, rows), scaled)
                if photo == "MONOCHROME1":
                    im = ImageOps.invert(im)
            elif samples == 3 and bits == 8:
                im = Image.frombytes("RGB", (cols, rows), raw[:rows*cols*3])
            else:
                self.viewer_image_label.configure(image="", text=f"Formato de píxeles no soportado por la vista previa básica.\n{samples} muestra(s), {bits} bits.")
                self.viewer_image_ref = None
                self.viewer_status.set("Metadatos disponibles; no se pudo previsualizar la imagen")
                return
            im.thumbnail((520, 520), Image.Resampling.LANCZOS)
            self.viewer_image_ref = ImageTk.PhotoImage(im)
            self.viewer_image_label.configure(image=self.viewer_image_ref, text="")
            self.viewer_status.set(f"{cols} × {rows} píxeles | {photo} | {bits} bits | {os.path.basename(self.viewer_path.get())}")
        except Exception as exc:
            self.viewer_image_label.configure(image="", text="No se pudo mostrar la imagen.")
            self.viewer_image_ref = None
            self.viewer_status.set(str(exc))

    def pick_image(self):
        p = filedialog.askopenfilename(filetypes=[("Imágenes JPG/PNG", "*.jpg *.jpeg *.png"), ("Todos", "*.*")])
        if p: self.v["source"].set(p)

    def pick_dicom(self):
        p = filedialog.askopenfilename(filetypes=[("DICOM", "*.dcm"), ("Todos", "*.*")])
        if p: self.v["anon_source"].set(p)

    def convert(self):
        if not check_dependencies(self): return
        source = self.v["source"].get().strip()
        if not source or not os.path.isfile(source):
            messagebox.showwarning("Falta imagen", "Seleccioná una imagen JPG o PNG válida.", parent=self); return
        try:
            if self.v["birth_date"].get().strip():
                parse_date(self.v["birth_date"].get(), "Nacimiento")
            parse_date(self.v["study_date"].get(), "Fecha del estudio", allow_blank=False)
            parse_time(self.v["study_time"].get())
        except ValueError as exc:
            messagebox.showerror("Datos inválidos", str(exc), parent=self); return
        target = filedialog.asksaveasfilename(parent=self, title="Guardar DICOM", defaultextension=".dcm",
            filetypes=[("DICOM", "*.dcm")], initialfile=os.path.splitext(os.path.basename(source))[0] + ".dcm")
        if not target: return
        if os.path.abspath(source) == os.path.abspath(target):
            messagebox.showerror("Destino inválido", "Elegí un destino distinto de la imagen original.", parent=self); return
        data = {k: v.get().strip() for k, v in self.v.items()}
        try:
            convert_image(source, target, data)
            if os.path.isfile(target) and os.path.getsize(target) > 0:
                messagebox.showinfo("Conversión completada", f"Archivo DICOM creado:\n{target}", parent=self)
            else:
                raise IOError("No se creó el archivo de destino.")
        except Exception as exc:
            messagebox.showerror("Error al convertir", f"{exc}\n\nDetalle:\n{traceback.format_exc()}", parent=self)

    def anonymize(self):
        if not check_dependencies(self): return
        source = self.v["anon_source"].get().strip()
        if not source or not os.path.isfile(source):
            messagebox.showwarning("Falta archivo", "Seleccioná un DICOM válido.", parent=self); return
        target = filedialog.asksaveasfilename(parent=self, title="Guardar DICOM anonimizado", defaultextension=".dcm",
            filetypes=[("DICOM", "*.dcm")], initialfile=os.path.splitext(os.path.basename(source))[0] + "_anonimo.dcm")
        if not target: return
        if os.path.abspath(source) == os.path.abspath(target):
            messagebox.showerror("Destino inválido", "El destino debe ser distinto del original.", parent=self); return
        try:
            anonymize_dicom(source, target)
            if os.path.isfile(target) and os.path.getsize(target) > 0:
                messagebox.showinfo("Anonimización completada", f"Archivo anonimizado creado:\n{target}", parent=self)
            else:
                raise IOError("No se creó el archivo de destino.")
        except Exception as exc:
            messagebox.showerror("Error al anonimizar", f"{exc}\n\nDetalle:\n{traceback.format_exc()}", parent=self)

if __name__ == "__main__":
    App().mainloop()
