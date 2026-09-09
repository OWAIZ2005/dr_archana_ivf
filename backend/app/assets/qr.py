"""Builds the payload encoded in a printed asset QR.

The QR reveals ONLY the application URL plus the asset's opaque, permanent
``qr_token``::

    <app-base-url>/#scan=<qr_token>

It never contains the location, asset name, serial number, asset code or
database id. When no application base URL is available (neither the
frontend's ``?base=`` param nor ``settings.ASSET_QR_BASE_URL``) the bare
opaque token is encoded instead — that still resolves through the
"Scan / enter QR token" box on the Asset Tracking screen.

No IP address or hostname is hardcoded here; the base URL is always supplied
by configuration (``NEXT_PUBLIC_APP_URL`` on the frontend, forwarded as the
``base`` query param, or ``ASSET_QR_BASE_URL`` in the backend settings).
"""
from __future__ import annotations

from app.core.config import get_settings


def _clean_base(base: str | None) -> str | None:
    if not base:
        return None
    b = base.strip().rstrip("/")
    if b.startswith("http://") or b.startswith("https://"):
        return b
    return None


def build_scan_payload(qr_token: str, base: str | None = None) -> str:
    """Return the exact string to encode in the QR for ``qr_token``.

    ``base`` is the caller-supplied application origin (e.g.
    ``http://localhost:3000`` locally, ``https://hmis.hospital.local`` on the
    hospital LAN). Falls back to ``settings.ASSET_QR_BASE_URL`` and finally to
    the bare token.
    """
    resolved = _clean_base(base) or _clean_base(get_settings().ASSET_QR_BASE_URL)
    if resolved is None:
        return qr_token
    return f"{resolved}/#scan={qr_token}"
