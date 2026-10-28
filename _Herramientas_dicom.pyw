# -*- coding: utf-8 -*-
"""OpenHIS-UNLaM HU-10: conversión JPG/PNG a DICOM y anonimización.
Dependencias: Pillow y pydicom. No requiere NumPy.
Una imagen convertida desde JPG/PNG será DICOM Secondary Capture, no una imagen diagnóstica original.
La anonimización de metadatos no borra texto identificatorio que esté dentro de los píxeles.
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = ImageOps = None

try:
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid
except ImportError:
    pydicom = None

TITLE = "OpenHIS-UNLaM | HU-10 - Herramientas DICOM"

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

def dependencies_ok():
    missing = []
    if Image is None:
        missing.append("Pillow")
    if pydicom is None:
        missing.append("pydicom")
    if missing:
        messagebox.showerror(
            "Dependencias faltantes",
            "Faltan: " + ", ".join(missing) +
            ". Este programa no necesita NumPy.\n\nCuando pip esté disponible, ejecutar:\n"
            "python -m pip install pillow pydicom"
        )
        return False
    return True

def convert_to_dicom(source, target, birth_year="", image_year="", sex=""):
    if not dependencies_ok():
        return
    with Image.open(source) as original:
        image = ImageOps.exif_transpose(original).convert("L")
        width, height = image.size
        pixel_bytes = image.tobytes()  # Pillow; no NumPy

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
    ds.Modality = "OT"
    ds.ConversionType = "WSD"
    ds.ImageType = ["DERIVED", "SECONDARY"]
    ds.PatientName = "ANONIMO"
    ds.PatientID = "ANONIMO"
    ds.PatientIdentityRemoved = "YES"
    ds.DeidentificationMethod = "OpenHIS-UNLaM HU-10"
    if birth_year:
        ds.PatientBirthDate = birth_year + "0101"
    ds.PatientSex = sex if sex in ("M", "F", "O") else ""
    if image_year:
        ds.StudyDate = image_year + "0101"
        ds.SeriesDate = image_year + "0101"
        ds.AcquisitionDate = image_year + "0101"
    ds.StudyDescription = "Imagen importada desde JPG/PNG"
    ds.SeriesDescription = "Secondary Capture"
    ds.Manufacturer = "OpenHIS-UNLaM"
    ds.Rows = height
    ds.Columns = width
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = pixel_bytes
    ds.save_as(target, write_like_original=False)

def anonymize_dicom(source, target):
    if not dependencies_ok():
        return
    ds = pydicom.dcmread(source)
    birth = str(getattr(ds, "PatientBirthDate", "") or "")
    birth_year = birth[:4] if len(birth) >= 4 and birth[:4].isdigit() else ""
    study_date = str(getattr(ds, "StudyDate", "") or "")
    if not study_date:
        study_date = str(getattr(ds, "AcquisitionDate", "") or getattr(ds, "SeriesDate", "") or "")
    image_year = study_date[:4] if len(study_date) >= 4 and study_date[:4].isdigit() else ""
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
    ds.DeidentificationMethod = "OpenHIS-UNLaM HU-10: metadatos identificatorios eliminados"
    if birth_year:
        ds.PatientBirthDate = birth_year + "0101"
    elif "PatientBirthDate" in ds:
        del ds.PatientBirthDate
    if image_year:
        ds.StudyDate = image_year + "0101"
        if "AcquisitionDate" in ds:
            ds.AcquisitionDate = image_year + "0101"
        if "SeriesDate" in ds:
            ds.SeriesDate = image_year + "0101"
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
        if not getattr(ds.file_meta, "MediaStorageSOPClassUID", None):
            ds.file_meta.MediaStorageSOPClassUID = getattr(ds, "SOPClassUID", SecondaryCaptureImageStorage)
    ds.save_as(target, write_like_original=False)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.geometry("760x560")
        self.minsize(680, 500)
        self.configure(padx=16, pady=16)
        self.image_path = tk.StringVar()
        self.dicom_path = tk.StringVar()
        self.birth_year = tk.StringVar()
        self.image_year = tk.StringVar()
        self.sex = tk.StringVar(value="")
        self.build_ui()

    def build_ui(self):
        ttk.Label(self, text="HU-10 | Herramientas DICOM",
                  font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(self, text="Conversión JPG/PNG a DICOM y anonimización de metadatos.",
                  wraplength=700).pack(anchor="w", pady=(4, 12))
        book = ttk.Notebook(self)
        book.pack(fill="both", expand=True)
        convert_tab = ttk.Frame(book, padding=14)
        anon_tab = ttk.Frame(book, padding=14)
        book.add(convert_tab, text="Imagen a DICOM")
        book.add(anon_tab, text="Anonimizar DICOM")

        ttk.Label(convert_tab, text="Imagen JPG o PNG").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(convert_tab, textvariable=self.image_path).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(convert_tab, text="Examinar…", command=self.pick_image).grid(row=1, column=1, padx=8)
        ttk.Label(convert_tab, text="Año de nacimiento (opcional, YYYY)").grid(row=2, column=0, sticky="w", pady=(12, 3))
        ttk.Entry(convert_tab, textvariable=self.birth_year, width=12).grid(row=3, column=0, sticky="w")
        ttk.Label(convert_tab, text="Año de toma de la imagen (opcional, YYYY)").grid(row=4, column=0, sticky="w", pady=(10, 3))
        ttk.Entry(convert_tab, textvariable=self.image_year, width=12).grid(row=5, column=0, sticky="w")
        ttk.Label(convert_tab, text="Sexo").grid(row=6, column=0, sticky="w", pady=(10, 3))
        choices = ttk.Frame(convert_tab)
        choices.grid(row=7, column=0, sticky="w")
        for label, value in (("No especificado", ""), ("F", "F"), ("M", "M"), ("O", "O")):
            ttk.Radiobutton(choices, text=label, variable=self.sex, value=value).pack(side="left", padx=(0, 10))
        ttk.Button(convert_tab, text="Convertir y guardar DICOM…",
                   command=self.convert).grid(row=8, column=0, sticky="w", pady=18)
        ttk.Label(convert_tab, text="La salida es DICOM Secondary Capture; no reemplaza una adquisición diagnóstica original.",
                  wraplength=660).grid(row=9, column=0, columnspan=2, sticky="w")
        convert_tab.columnconfigure(0, weight=1)

        ttk.Label(anon_tab, text="Archivo DICOM de entrada").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(anon_tab, textvariable=self.dicom_path).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(anon_tab, text="Examinar…", command=self.pick_dicom).grid(row=1, column=1, padx=8)
        ttk.Label(anon_tab, text="Conserva el año de nacimiento, el año del estudio/toma y el sexo; "
                  "regenera los UID principales y elimina grupos privados y metadatos identificatorios habituales.",
                  wraplength=670).grid(row=2, column=0, columnspan=2, sticky="w", pady=16)
        ttk.Button(anon_tab, text="Anonimizar y guardar como…",
                   command=self.anonymize).grid(row=3, column=0, sticky="w")
        anon_tab.columnconfigure(0, weight=1)

        ttk.Label(self, text="Importante: revise la imagen; los nombres o identificadores impresos en los píxeles no se borran automáticamente.",
                  wraplength=720, foreground="#8a3b12").pack(anchor="w", pady=(12, 0))

    def pick_image(self):
        path = filedialog.askopenfilename(filetypes=[("Imágenes JPG/PNG", "*.jpg *.jpeg *.png"), ("Todos", "*.*")])
        if path:
            self.image_path.set(path)

    def pick_dicom(self):
        path = filedialog.askopenfilename(filetypes=[("DICOM", "*.dcm"), ("Todos", "*.*")])
        if path:
            self.dicom_path.set(path)

    @staticmethod
    def valid_year(value, label):
        if value and (len(value) != 4 or not value.isdigit()):
            messagebox.showerror("Dato inválido", f"{label}: ingresá cuatro dígitos, por ejemplo 2026.")
            return False
        return True

    def convert(self):
        source = self.image_path.get().strip()
        if not source:
            messagebox.showwarning("Falta imagen", "Seleccioná primero un archivo JPG o PNG.")
            return
        by, iy = self.birth_year.get().strip(), self.image_year.get().strip()
        if not self.valid_year(by, "Año de nacimiento") or not self.valid_year(iy, "Año de toma"):
            return
        target = filedialog.asksaveasfilename(defaultextension=".dcm", filetypes=[("DICOM", "*.dcm")],
                                              initialfile=os.path.splitext(os.path.basename(source))[0] + ".dcm")
        if not target:
            return
        try:
            convert_to_dicom(source, target, by, iy, self.sex.get())
            messagebox.showinfo("Listo", f"DICOM guardado en:\n{target}")
        except Exception as exc:
            messagebox.showerror("Error de conversión", str(exc))

    def anonymize(self):
        source = self.dicom_path.get().strip()
        if not source or not os.path.isfile(source):
            messagebox.showwarning("Falta archivo", "Seleccioná un archivo DICOM válido.")
            return
        target = filedialog.asksaveasfilename(defaultextension=".dcm", filetypes=[("DICOM", "*.dcm")],
                                              initialfile=os.path.splitext(os.path.basename(source))[0] + "_anonimo.dcm")
        if not target:
            return
        if os.path.abspath(source) == os.path.abspath(target):
            messagebox.showerror("Ruta inválida", "La salida debe ser distinta del archivo original.")
            return
        try:
            anonymize_dicom(source, target)
            messagebox.showinfo("Listo", f"DICOM anonimizado guardado en:\n{target}")
        except Exception as exc:
            messagebox.showerror("Error de anonimización", str(exc))

if __name__ == "__main__":
    App().mainloop()

