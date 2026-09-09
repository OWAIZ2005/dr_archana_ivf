"""Printable QR label for a physical asset — one label per A4 page.

Reuses ``app/printing/service.generate_qr_png`` for the QR image and the same
fpdf2 conventions as the other document generators (see
``app/prescription/pdf.py`` / ``app/reports/job_generators.py``). No second QR
or PDF framework.

The QR encodes ONLY ``<app-base-url>/#scan=<qr_token>`` (see
``app/assets/qr.py``) — the application URL plus the asset's opaque, permanent
token. It reveals no location, asset name, serial number, asset code or
database id. A phone camera that reads it opens the app straight at the
scanned asset. When no base URL is configured the bare token is encoded (still
resolvable via manual entry).
"""
from __future__ import annotations

import io

from fpdf import FPDF
from fpdf.enums import Align, XPos, YPos

from app.printing.service import generate_qr_png

# Same green + clinic name every other generated document uses.
_BRAND = (6, 95, 70)
CLINIC_DISPLAY_NAME = "Dr. Archana IVF & Women Centre"


def _safe(value: object) -> str:
    text = "" if value is None else str(value)
    return text.encode("latin-1", "replace").decode("latin-1")


def render_asset_label_pdf(asset, *, qr_payload: str | None = None) -> bytes:
    """``asset`` is an ``app.assets.models.Asset``. Read-only.

    ``qr_payload`` is the exact string to encode in the QR image (built by
    ``app.assets.qr.build_scan_payload``). Defaults to the bare opaque token
    when not supplied.
    """
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(18, 20, 18)
    pdf.set_auto_page_break(auto=False)
    pdf.set_title(f"Asset label {asset.asset_code}")
    pdf.add_page()

    # Header
    pdf.set_fill_color(*_BRAND)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 11, f"  {_safe(CLINIC_DISPLAY_NAME)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(16)

    # Asset name + code
    pdf.set_font("Helvetica", "B", 20)
    pdf.multi_cell(0, 10, _safe(asset.name), align=Align.C, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 8, _safe(asset.asset_code), align=Align.C, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    # QR (encodes "<app-url>/#scan=<token>" — no location/serial/code/id)
    qr_png = generate_qr_png(qr_payload or asset.qr_token)
    qr_mm = 90
    x = (pdf.w - qr_mm) / 2
    pdf.image(io.BytesIO(qr_png), x=x, y=pdf.get_y(), w=qr_mm, h=qr_mm)
    pdf.set_y(pdf.get_y() + qr_mm + 8)

    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(
        0, 6,
        "Scan and sign in to view the current location or record a move.",
        align=Align.C, new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.set_text_color(0, 0, 0)

    return bytes(pdf.output())
