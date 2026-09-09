"""Report-job generators.

Each generator is an async function ``(session, parameters) -> (bytes, content_type)``.
It only reads from other modules' tables; it never writes to them. Register new
report types in ``REPORT_GENERATORS`` - the async job pipeline does not change.

``generate_patient_summary`` produces a professional PDF (built with fpdf2, a
pure-Python library) here in the Celery worker - the browser never renders it.
The gathered data is identical to the JSON the job previously emitted; only the
serialisation changed.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from sqlalchemy.ext.asyncio import AsyncSession

from app.appointments.models import Appointment
from app.laboratory.models import LabReport, LabReportResult
from app.patients.models import Patient
from app.reports.job_models import ReportType

Generator = Callable[[AsyncSession, dict[str, Any]], Awaitable[tuple[bytes, str]]]


class ReportGenerationError(Exception):
    """A generator could not produce the report. Message is safe to surface."""


# fpdf2's core fonts (Helvetica) are latin-1 only. Patient data is free text, so
# every string is passed through this before it reaches the PDF - unsupported
# code points become "?" rather than crashing the worker. A future switch to an
# embedded Unicode TTF would lift this.
_BRAND = (6, 95, 70)          # brand-700 green, matches the app UI
_HEADING_FILL = (232, 240, 236)
_ROW_ALT = (247, 249, 248)


def _safe(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.encode("latin-1", "replace").decode("latin-1")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%d %b %Y, %H:%M UTC")


def _fmt_date(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%d %b %Y")


class _PatientSummaryPDF(FPDF):
    """A4 patient-summary report with a repeating title bar and page footer."""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(15, 16, 15)
        self.set_auto_page_break(auto=True, margin=18)
        self.set_title("Patient Summary Report")

    # -- repeating chrome ---------------------------------------------------
    def header(self) -> None:
        self.set_fill_color(*_BRAND)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 10, "  Dr. Archana IVF & Women Centre", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, "  Patient Summary Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 8,
            f"Confidential clinical document  -  generated {_fmt_dt(datetime.now(timezone.utc))}  -  "
            f"Page {self.page_no()}/{{nb}}",
            align="C",
        )
        self.set_text_color(0, 0, 0)

    # -- building blocks --------------------------------------------------
    def section(self, title: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_fill_color(*_HEADING_FILL)
        self.cell(0, 8, f"  {_safe(title)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.ln(1.5)

    def kv(self, label: str, value: Any) -> None:
        self.set_font("Helvetica", "B", 9.5)
        self.cell(45, 6, _safe(label), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 9.5)
        self.multi_cell(0, 6, _safe(value) or "-", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def note(self, text: str) -> None:
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(110, 110, 110)
        self.multi_cell(0, 5, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)


async def generate_patient_summary(
    session: AsyncSession, parameters: dict[str, Any]
) -> tuple[bytes, str]:
    """A PDF snapshot of one patient: demographics, appointment counts, and
    every uploaded lab report and its extracted results on file for them."""
    patient_id = UUID(str(parameters["patient_id"]))

    patient = (
        await session.execute(sa.select(Patient).where(Patient.id == patient_id))
    ).scalar_one_or_none()
    if patient is None:
        raise ReportGenerationError("The patient no longer exists.")

    appt_rows = (
        await session.execute(
            sa.select(Appointment.status, sa.func.count())
            .where(Appointment.patient_id == patient_id)
            .group_by(Appointment.status)
        )
    ).all()
    appointments_by_status = {
        (status.value if hasattr(status, "value") else str(status)): count
        for status, count in appt_rows
    }
    appointments_total = sum(appointments_by_status.values())

    lab_reports = (
        await session.execute(
            sa.select(LabReport)
            .where(LabReport.patient_id == patient_id)
            .order_by(LabReport.created_at.desc(), LabReport.id.desc())
        )
    ).scalars().all()

    report_ids = [r.id for r in lab_reports]
    results_by_report: dict[UUID, list[LabReportResult]] = {rid: [] for rid in report_ids}
    if report_ids:
        result_rows = (
            await session.execute(
                sa.select(LabReportResult)
                .where(LabReportResult.report_id.in_(report_ids))
                .order_by(LabReportResult.report_id, LabReportResult.id)
            )
        ).scalars().all()
        for row in result_rows:
            results_by_report.setdefault(row.report_id, []).append(row)
    result_count = sum(len(v) for v in results_by_report.values())

    # ---- render -------------------------------------------------------------
    pdf = _PatientSummaryPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(
        0, 5, f"Generated {_fmt_dt(datetime.now(timezone.utc))}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_text_color(0, 0, 0)

    pdf.section("Patient Information")
    pdf.kv("UHID", patient.uhid)
    pdf.kv("Full name", patient.full_name)
    pdf.kv("Date of birth", _fmt_date(patient.date_of_birth))
    pdf.kv("Gender", patient.gender)
    pdf.kv("Phone", patient.phone)
    pdf.kv("Email", patient.email)

    pdf.section("Appointments")
    pdf.kv("Total on record", appointments_total)
    if appointments_by_status:
        for status_name, count in sorted(appointments_by_status.items()):
            pdf.kv(status_name.replace("_", " ").title(), count)
    else:
        pdf.note("No appointments on record for this patient.")

    pdf.section("Laboratory")
    pdf.kv("Uploaded reports", len(lab_reports))
    pdf.kv("Extracted results", result_count)

    if not lab_reports:
        pdf.note("No laboratory reports have been uploaded for this patient.")

    for i, report in enumerate(lab_reports, start=1):
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.multi_cell(
            0, 6,
            _safe(f"{i}. {report.original_filename}"),
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(90, 90, 90)
        pdf.multi_cell(
            0, 5,
            _safe(
                f"{report.document_kind.value}  |  extraction: {report.extraction_status.value}"
                f" ({report.extraction_method.value})  |  pages: {report.page_count or '-'}"
                f"  |  uploaded {_fmt_date(report.created_at)}"
                f"  |  extracted {_fmt_date(report.extracted_at)}"
            ),
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

        rows = results_by_report.get(report.id, [])
        if not rows:
            pdf.note("   No structured results extracted from this report.")
            continue

        with pdf.table(
            width=180,
            col_widths=(52, 22, 22, 34, 20, 30),
            line_height=5.5,
            headings_style=FontFace(emphasis="BOLD", fill_color=_HEADING_FILL),
            cell_fill_color=_ROW_ALT,
            cell_fill_mode="ROWS",
            text_align=("LEFT", "LEFT", "LEFT", "LEFT", "LEFT", "LEFT"),
            first_row_as_headings=True,
        ) as table:
            table.row(["Test", "Value", "Unit", "Reference range", "Origin", "Validation"])
            for r in rows:
                table.row([
                    _safe(r.test_name),
                    _safe(r.value),
                    _safe(r.unit),
                    _safe(r.reference_range),
                    _safe(r.entry_origin.value),
                    _safe(r.validation_status.value.replace("_", " ")),
                ])

    out = pdf.output()
    return bytes(out), "application/pdf"


class _DischargeSummaryPDF(FPDF):
    """A4 discharge summary with the same repeating chrome as the patient
    summary (kept as its own class so changes here can't regress the verified
    patient-summary layout)."""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(15, 16, 15)
        self.set_auto_page_break(auto=True, margin=18)
        self.set_title("Discharge Summary")

    def header(self) -> None:
        self.set_fill_color(*_BRAND)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 10, "  Dr. Archana IVF & Women Centre", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, "  Discharge Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 8,
            f"Confidential clinical document  -  generated {_fmt_dt(datetime.now(timezone.utc))}  -  "
            f"Page {self.page_no()}/{{nb}}",
            align="C",
        )
        self.set_text_color(0, 0, 0)

    def section(self, title: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_fill_color(*_HEADING_FILL)
        self.cell(0, 8, f"  {_safe(title)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.ln(1.5)

    def kv(self, label: str, value: Any) -> None:
        self.set_font("Helvetica", "B", 9.5)
        self.cell(50, 6, _safe(label), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_font("Helvetica", "", 9.5)
        self.multi_cell(0, 6, _safe(value) or "-", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def note(self, text: str) -> None:
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(110, 110, 110)
        self.multi_cell(0, 5, _safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)

    def simple_table(self, headings: list[str], rows: list[list[Any]], col_widths: tuple[int, ...]) -> None:
        with self.table(
            width=sum(col_widths),
            col_widths=col_widths,
            line_height=5.5,
            headings_style=FontFace(emphasis="BOLD", fill_color=_HEADING_FILL),
            cell_fill_color=_ROW_ALT,
            cell_fill_mode="ROWS",
            text_align=tuple("LEFT" for _ in col_widths),
            first_row_as_headings=True,
        ) as table:
            table.row([_safe(h) for h in headings])
            for r in rows:
                table.row([_safe(c) for c in r])


async def generate_discharge_summary(
    session: AsyncSession, parameters: dict[str, Any]
) -> tuple[bytes, str]:
    """A structured discharge summary PDF for one patient - diagnosis/treatment
    context, everything done during care, and follow-up. Every value is a direct
    read of an existing record via ``reports.service.discharge_summary``; nothing
    clinical is generated or inferred here. The follow-up wording is a
    placeholder until the clinic's discharge template is supplied - the data
    model and pipeline do not depend on it."""
    from app.core.exceptions import NotFoundError
    from app.reports import service as analytics

    patient_id = UUID(str(parameters["patient_id"]))
    try:
        data = await analytics.discharge_summary(session, patient_id)
    except NotFoundError as exc:
        raise ReportGenerationError("The patient no longer exists.") from exc

    p = data["patient"]
    couple = data["couple"]

    pdf = _DischargeSummaryPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(
        0, 5, f"Generated {_fmt_dt(datetime.now(timezone.utc))}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_text_color(0, 0, 0)

    pdf.section("Patient Information")
    pdf.kv("UHID", p["uhid"])
    pdf.kv("Full name", p["full_name"])
    pdf.kv("Date of birth", _fmt_date(p["date_of_birth"]))
    pdf.kv("Partner", couple["partner_name"] if couple else "-")

    pdf.section("Diagnosis & Treatment")
    cycles = data["cycles"]
    if cycles:
        for c in cycles:
            pdf.kv(
                f"Cycle {c['cycle_number']}",
                f"{c['treatment']}  |  protocol {c['protocol']}  |  stage {c['stage']}"
                f"  |  started {_fmt_date(c['started_at'])}",
            )
    else:
        pdf.note("No IVF treatment cycle on record for this patient.")

    pdf.section("Consultations")
    rows = [[_fmt_date(c["date"]), c["type"], c["notes"]] for c in data["consultations"]]
    if rows:
        pdf.simple_table(["Date", "Type", "Notes"], rows, (28, 40, 112))
    else:
        pdf.note("No consultations on record.")

    pdf.section("Investigations")
    rows = [[_fmt_date(i["date"]), i["test_name"], i["status"]] for i in data["investigations"]]
    if rows:
        pdf.simple_table(["Date", "Test", "Status"], rows, (28, 110, 42))
    else:
        pdf.note("No investigations on record.")

    pdf.section("Prescriptions")
    rows = [
        [_fmt_date(r["date"]), r["category"] or "-", str(r["line_count"])]
        for r in data["prescriptions"]
    ]
    if rows:
        pdf.simple_table(["Date", "Category", "Items"], rows, (28, 110, 42))
    else:
        pdf.note("No prescriptions on record.")

    pdf.section("Monitoring Visits")
    rows = [
        [_fmt_date(m["date"]), str(m["cycle_day"]), f"{m['endometrium_mm']:.1f}", m["doctor_note"] or "-"]
        for m in data["monitoring_visits"]
    ]
    if rows:
        pdf.simple_table(["Date", "Cycle day", "Endo (mm)", "Note"], rows, (28, 22, 24, 106))
    else:
        pdf.note("No monitoring visits on record.")

    pdf.section("Injections")
    rows = [
        [_fmt_date(i["administered_at"]), i["medicine_name"], i["dose"], i["status"]]
        for i in data["injections"]
    ]
    if rows:
        pdf.simple_table(["Administered", "Medicine", "Dose", "Status"], rows, (32, 66, 40, 42))
    else:
        pdf.note("No injections on record.")

    pdf.section("Oocytes & Embryology")
    oa = data["oocyte_assessments"]
    if oa:
        a = oa[0]
        pdf.kv("Retrieval date", _fmt_date(a["retrieval_date"]))
        pdf.kv("Oocytes retrieved", a["oocytes_retrieved"])
        pdf.kv("Mature oocytes", a["mature_oocytes"])
        pdf.kv("Normally fertilised", a["normally_fertilised"])
    else:
        pdf.note("No oocyte retrieval on record.")
    emb = [[e["label"], str(e["day"]), e["grade"], e["status"]] for e in data["embryos"]]
    if emb:
        pdf.ln(1)
        pdf.simple_table(["Embryo", "Day", "Grade", "Status"], emb, (50, 22, 40, 68))

    pdf.section("Embryo Transfers")
    rows = [
        [_fmt_date(t["transfer_date"]), "Completed" if t["completed"] else "Not completed"]
        for t in data["embryo_transfers"]
    ]
    if rows:
        pdf.simple_table(["Date", "Status"], rows, (40, 140))
    else:
        pdf.note("No embryo transfers on record.")

    pdf.section("Current Cryostorage")
    storage = data["current_storage"]
    if storage:
        for s in storage:
            pdf.kv("Location", s["address"])
    else:
        pdf.note("No embryos currently in storage.")

    pdf.section("Pregnancy Outcome")
    outcomes = data["pregnancy_outcomes"]
    if outcomes:
        for o in outcomes:
            pdf.kv("Outcome", o["outcome"])
            pdf.kv("Transfer date", _fmt_date(o["transfer_date"]))
            pdf.kv("Estimated due date", _fmt_date(o["estimated_due_date"]))
    else:
        pdf.note("No pregnancy outcome recorded.")

    pdf.section("Follow-up & Next Visit")
    pdf.note(
        "Placeholder wording - replace with the clinic's approved discharge "
        "template once available. The fields below are not auto-generated from "
        "clinical data."
    )
    pdf.kv("Follow-up instructions", "As per the latest consultation notes above.")
    pdf.kv("Next visit", "As advised by the treating consultant.")

    out = pdf.output()
    return bytes(out), "application/pdf"


REPORT_GENERATORS: dict[ReportType, Generator] = {
    ReportType.patient_summary: generate_patient_summary,
    ReportType.discharge_summary: generate_discharge_summary,
}
