"""Synchronous, on-demand prescription PDF — "Print Prescription".

Reuses the reports module's fpdf2 conventions (``app/reports/job_generators.py``):
the same latin-1 ``_safe`` sanitiser, date formatter, brand colours, A4 page +
15/16/15 margins, a green title bar, a page footer with ``Page X/{nb}``, and
``FPDF.table`` for the medicines grid. No second PDF framework, no Celery job —
a prescription print is immediate.

Generic placeholder letterhead: clinic display name only (the same string every
other PDF header uses). No address / phone / logo / registration number / legal
text — none of those exist in the app config or database, and this module does
not invent them.
"""
from __future__ import annotations

from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

# Reuse the reports module's shared PDF helpers rather than duplicating them.
from app.reports.job_generators import _BRAND, _HEADING_FILL, _ROW_ALT, _fmt_date, _safe

# The clinic display name every generated PDF already uses (see
# app/reports/job_generators.py and app/ivf/trigger_npo_service.py). Move to
# config if the product ever serves more than one clinic.
CLINIC_DISPLAY_NAME = "Dr. Archana IVF & Women Centre"


class _PrescriptionPDF(FPDF):
    """A4 prescription with a repeating green title bar and a page footer."""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(15, 16, 15)
        self.set_auto_page_break(auto=True, margin=20)
        self.set_title("Prescription")

    def header(self) -> None:
        self.set_fill_color(*_BRAND)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 10, f"  {_safe(CLINIC_DISPLAY_NAME)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, "  Prescription", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 8,
            f"Generated {_safe(_fmt_date(datetime.now()))}  -  Page {self.page_no()}/{{nb}}",
            align="C",
        )
        self.set_text_color(0, 0, 0)

    def kv(self, label: str, value) -> None:
        self.set_font("Helvetica", "B", 9.5)
        self.cell(28, 6, _safe(label), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 9.5)
        self.multi_cell(0, 6, _safe(value) or "-", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def render_prescription_pdf(prescription, patient, doctor) -> bytes:
    """Build the printable PDF for one already-saved prescription.

    ``prescription`` is an ``app.prescription.models.Prescription`` with its
    ``lines`` loaded; ``patient`` an ``app.patients.models.Patient``; ``doctor``
    the prescribing ``app.users.models.User`` (or ``None`` if unresolved). This
    function only reads — it never writes to or mutates any of them.
    """
    doctor_name = getattr(doctor, "full_name", None) or "-"

    pdf = _PrescriptionPDF()
    pdf.add_page()

    # --- header block: patient / UHID / doctor / date ---------------------
    pdf.set_font("Helvetica", "", 9.5)
    pdf.kv("Patient", getattr(patient, "full_name", None))
    pdf.kv("UHID", getattr(patient, "uhid", None))
    pdf.kv("Doctor", doctor_name)
    pdf.kv("Date", _fmt_date(prescription.created_at))
    if prescription.category:
        pdf.kv("Category", prescription.category)
    pdf.ln(3)

    # --- medicines table ------------------------------------------------
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(*_HEADING_FILL)
    pdf.cell(0, 8, "  Prescribed Medicines", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.ln(1.5)

    col_widths = (46, 22, 24, 22, 22, 44)  # sums to 180 == usable A4 width
    lines = list(prescription.lines)
    with pdf.table(
        width=sum(col_widths),
        col_widths=col_widths,
        line_height=6,
        headings_style=FontFace(emphasis="BOLD", fill_color=_HEADING_FILL),
        cell_fill_color=_ROW_ALT,
        cell_fill_mode="ROWS",
        text_align=("LEFT", "LEFT", "LEFT", "LEFT", "LEFT", "LEFT"),
        first_row_as_headings=True,
    ) as table:
        table.row(["Medicine", "Dosage", "Frequency", "Timing", "Duration", "Instructions"])
        if not lines:
            table.row(["-", "-", "-", "-", "-", "-"])
        for line in lines:
            table.row([
                _safe(line.medicine_name),
                _safe(line.dosage),
                _safe(line.frequency),
                _safe(line.timing),
                _safe(line.duration),
                _safe(line.instructions),
            ])

    # --- prescription-level notes ---------------------------------------
    if prescription.notes:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.cell(0, 6, "Notes", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.multi_cell(0, 5.5, _safe(prescription.notes), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- signature block ----------------------------------------------
    pdf.ln(16)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.cell(0, 6, "Doctor Signature:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)
    pdf.cell(70, 0, "", border="T", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.cell(0, 6, _safe(doctor_name), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
