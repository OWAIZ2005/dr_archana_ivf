"""Asset & Item Tracking — location master, opaque QR token, append-only
movement history, RBAC, audit, and the printable label.

Extends the pre-existing app/assets module; does not duplicate it.
"""
from io import BytesIO

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.roles.models import Role
from app.users.models import User

BASE = "/api/v1/assets"
UNKNOWN = "00000000-0000-0000-0000-000000000000"


@pytest_asyncio.fixture
async def viewer_headers(client: AsyncClient, db_session, seeded_roles) -> dict:
    """A signed-in user with assets.read but NOT assets.move (the nurse role
    after this feature's roles/seed.py change)."""
    role = (await db_session.execute(select(Role).where(Role.code == "nurse"))).scalar_one()
    db_session.add(User(
        employee_code="TEST-ASSET-VIEW", full_name="Asset Viewer", email="assetviewer@example.com",
        role_id=role.id, password_hash=hash_password("TestPass123!"),
    ))
    await db_session.commit()
    r = await client.post("/api/v1/auth/login", json={"email": "assetviewer@example.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _mk_location(client, headers, name, **extra) -> dict:
    r = await client.post(f"{BASE}/locations", headers=headers, json={"name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_asset(client, headers, *, name, location_id, **extra) -> dict:
    r = await client.post(BASE, headers=headers, json={"name": name, "current_location_id": location_id, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def _move(client, headers, asset_id, to_location_id, note=None):
    return await client.post(
        f"{BASE}/{asset_id}/move", headers=headers, json={"to_location_id": to_location_id, "note": note}
    )


async def _history(client, headers, asset_id) -> list[dict]:
    r = await client.get(f"{BASE}/{asset_id}/history", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------- #

class TestRegisterAndLocations:
    async def test_create_location_and_asset_with_current_location(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "OT-1", building="Main Building", floor="2nd Floor",
                                 description="Operating theatre 1", in_charge="Sister Mary", phone="044-1234")
        asset = await _mk_asset(client, admin_headers, name="Exam Couch", location_id=loc["id"],
                                category="Furniture", brand="Acme", model="C-100", serial_number="SN-EX-001")
        assert asset["asset_code"].startswith("AST-")
        assert asset["current_location"]["id"] == loc["id"]
        assert asset["current_location"]["name"] == "OT-1"

    async def test_asset_has_a_secure_opaque_qr_token(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "Store Room A")
        asset = await _mk_asset(client, admin_headers, name="Printer", location_id=loc["id"], serial_number="PRN-42")
        token = asset["qr_token"]
        assert len(token) >= 20                       # not a short/sequential id
        assert asset["id"] not in token               # not the DB id
        assert asset["asset_code"] not in token       # not the human code
        assert "AST-" not in token
        # the token / resolve response must not leak plain location text into the token
        assert "Store Room A" not in token

    async def test_invalid_qr_token_is_rejected(self, client, admin_headers):
        assert (await client.get(f"{BASE}/resolve/not-a-real-token", headers=admin_headers)).status_code == 404
        assert (await client.get(f"{BASE}/resolve/x", headers=admin_headers)).status_code == 404

    async def test_registration_writes_an_initial_journey_event(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "IT Department")
        asset = await _mk_asset(client, admin_headers, name="Laptop A", location_id=loc["id"])
        hist = await _history(client, admin_headers, asset["id"])
        assert len(hist) == 1
        assert hist[0]["event_type"] == "register"
        assert hist[0]["from_location"] is None
        assert hist[0]["to_location"]["name"] == "IT Department"
        assert hist[0]["moved_by_name"]  # recorded from the acting user


class TestSearch:
    async def test_search_by_name_code_and_serial_and_filter_by_location(self, client, admin_headers):
        a = await _mk_location(client, admin_headers, "Loc A")
        b = await _mk_location(client, admin_headers, "Loc B")
        dell = await _mk_asset(client, admin_headers, name="Dell Latitude Laptop", location_id=a["id"], serial_number="DL-77-XZ")
        await _mk_asset(client, admin_headers, name="Refrigerator", location_id=b["id"], serial_number="RF-01")

        by_name = (await client.get(f"{BASE}?q=dell", headers=admin_headers)).json()
        assert [x["id"] for x in by_name] == [dell["id"]]
        by_code = (await client.get(f"{BASE}?q={dell['asset_code']}", headers=admin_headers)).json()
        assert dell["id"] in [x["id"] for x in by_code]
        by_serial = (await client.get(f"{BASE}?q=DL-77", headers=admin_headers)).json()
        assert dell["id"] in [x["id"] for x in by_serial]

        at_a = (await client.get(f"{BASE}?location_id={a['id']}", headers=admin_headers)).json()
        assert [x["id"] for x in at_a] == [dell["id"]]

    async def test_multiple_assets_at_the_same_location(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "Reception Desk")
        x = await _mk_asset(client, admin_headers, name="Barcode Scanner", location_id=loc["id"])
        y = await _mk_asset(client, admin_headers, name="Label Printer", location_id=loc["id"])
        here = (await client.get(f"{BASE}?location_id={loc['id']}", headers=admin_headers)).json()
        assert {x["id"], y["id"]} == {a["id"] for a in here}

    async def test_location_detail_fields_returned(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "Andrology Lab", building="Main Building", floor="2nd Floor",
                                 description="Semen analysis", in_charge="Dr X", phone="044-9999")
        got = (await client.get(f"{BASE}/locations/{loc['id']}", headers=admin_headers)).json()
        assert got["building"] == "Main Building" and got["floor"] == "2nd Floor"
        assert got["in_charge"] == "Dr X" and got["phone"] == "044-9999"


class TestMovementHistory:
    async def test_move_a_to_b_to_c_keeps_full_append_only_history(self, client, admin_headers):
        a = await _mk_location(client, admin_headers, "Store Room B")
        b = await _mk_location(client, admin_headers, "Consultation Room 2")
        c = await _mk_location(client, admin_headers, "OT-2")
        asset = await _mk_asset(client, admin_headers, name="Ultrasound Probe", location_id=a["id"])

        r1 = await _move(client, admin_headers, asset["id"], b["id"], note="needed for a scan")
        assert r1.status_code == 200
        assert r1.json()["current_location"]["id"] == b["id"]

        hist_after_1 = await _history(client, admin_headers, asset["id"])
        assert [h["event_type"] for h in hist_after_1] == ["register", "move"]
        assert hist_after_1[1]["from_location"]["name"] == "Store Room B"
        assert hist_after_1[1]["to_location"]["name"] == "Consultation Room 2"
        assert hist_after_1[1]["note"] == "needed for a scan"
        register_row_snapshot = hist_after_1[0]

        r2 = await _move(client, admin_headers, asset["id"], c["id"])
        assert r2.json()["current_location"]["id"] == c["id"]

        hist_after_2 = await _history(client, admin_headers, asset["id"])
        assert [h["to_location"]["name"] for h in hist_after_2] == ["Store Room B", "Consultation Room 2", "OT-2"]
        # earlier rows are byte-identical — nothing was mutated
        assert hist_after_2[0] == register_row_snapshot
        assert hist_after_2[1] == hist_after_1[1]

        # re-fetch the asset: current location persists as C
        refetched = (await client.get(f"{BASE}/{asset['id']}", headers=admin_headers)).json()
        assert refetched["current_location"]["name"] == "OT-2"

    async def test_qr_token_is_unchanged_and_still_resolves_after_moves(self, client, admin_headers):
        a = await _mk_location(client, admin_headers, "Pharmacy")
        b = await _mk_location(client, admin_headers, "Admin Office")
        asset = await _mk_asset(client, admin_headers, name="Weighing Scale", location_id=a["id"])
        token = asset["qr_token"]

        await _move(client, admin_headers, asset["id"], b["id"])
        resolved = await client.get(f"{BASE}/resolve/{token}", headers=admin_headers)
        assert resolved.status_code == 200
        body = resolved.json()
        assert body["id"] == asset["id"]
        assert body["qr_token"] == token                    # permanent
        assert body["current_location"]["name"] == "Admin Office"  # live state

    async def test_move_to_unknown_location_is_rejected(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "Lab Store")
        asset = await _mk_asset(client, admin_headers, name="Centrifuge", location_id=loc["id"])
        r = await _move(client, admin_headers, asset["id"], UNKNOWN)
        assert r.status_code == 422

    async def test_unknown_asset_move_and_history_are_404(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "Nowhere")
        assert (await _move(client, admin_headers, UNKNOWN, loc["id"])).status_code == 404
        assert (await client.get(f"{BASE}/{UNKNOWN}/history", headers=admin_headers)).status_code == 404


class TestRbacAndAudit:
    async def test_unauthenticated_cannot_move(self, client, admin_headers):
        a = await _mk_location(client, admin_headers, "Room X")
        b = await _mk_location(client, admin_headers, "Room Y")
        asset = await _mk_asset(client, admin_headers, name="Monitor", location_id=a["id"])
        r = await client.post(f"{BASE}/{asset['id']}/move", json={"to_location_id": b["id"]})
        assert r.status_code == 401

    async def test_viewer_without_move_permission_is_forbidden(self, client, admin_headers, viewer_headers):
        a = await _mk_location(client, admin_headers, "Room P")
        b = await _mk_location(client, admin_headers, "Room Q")
        asset = await _mk_asset(client, admin_headers, name="Trolley", location_id=a["id"])
        aid = asset["id"]
        # can view
        assert (await client.get(f"{BASE}/{aid}", headers=viewer_headers)).status_code == 200
        assert (await client.get(f"{BASE}/{aid}/history", headers=viewer_headers)).status_code == 200
        # cannot register or move
        assert (await client.post(BASE, headers=viewer_headers,
                                  json={"name": "X", "current_location_id": a["id"]})).status_code == 403
        assert (await _move(client, viewer_headers, aid, b["id"])).status_code == 403

    async def test_move_creates_an_audit_event(self, client, admin_headers, db_session):
        a = await _mk_location(client, admin_headers, "Audit Loc A")
        b = await _mk_location(client, admin_headers, "Audit Loc B")
        asset = await _mk_asset(client, admin_headers, name="Audited Asset", location_id=a["id"])
        await _move(client, admin_headers, asset["id"], b["id"])

        from app.audit.models import AuditEvent
        rows = (await db_session.execute(
            select(AuditEvent).where(AuditEvent.action == "assets.moved", AuditEvent.entity_id == asset["id"])
        )).scalars().all()
        assert rows, "assets.moved audit event was not written"
        ev = rows[-1]
        assert ev.before_state["location"] == "Audit Loc A"
        assert ev.after_state["location"] == "Audit Loc B"


class TestPrintableLabel:
    async def test_label_pdf_is_valid(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "Label Loc")
        asset = await _mk_asset(client, admin_headers, name="Fridge", location_id=loc["id"])
        r = await client.get(f"{BASE}/{asset['id']}/label", headers=admin_headers)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.headers["content-disposition"].endswith(f'asset_{asset["asset_code"]}.pdf"')
        assert r.content.startswith(b"%PDF-")
        assert r.content.rstrip().endswith(b"%%EOF")

    async def test_qr_png_preview_is_an_image_without_location_text(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "SecretRoomZZZ")
        asset = await _mk_asset(client, admin_headers, name="Camera", location_id=loc["id"])
        r = await client.get(f"{BASE}/{asset['id']}/qr", headers=admin_headers)
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert b"SecretRoomZZZ" not in r.content  # QR encodes the token only


class TestScanUrlPayload:
    """The printed QR must encode ``<app-base-url>/#scan=<opaque-token>`` and
    nothing else — no location, asset name, serial, asset code or DB id. The
    base URL always comes from config (the frontend's ``NEXT_PUBLIC_APP_URL``,
    forwarded as ``?base=``), never a hardcoded address."""

    def test_build_scan_payload_uses_configured_base_and_hash_scan_token(self):
        from app.assets.qr import build_scan_payload

        out = build_scan_payload("tok_ABC123opaque", base="http://localhost:3000")
        assert out == "http://localhost:3000/#scan=tok_ABC123opaque"
        assert "#scan=" in out
        # trailing slash on the base is normalised, not doubled
        assert build_scan_payload("t0ken", base="http://localhost:3000/") == "http://localhost:3000/#scan=t0ken"
        # a LAN https hostname works the same way, still no hardcoding in source
        assert build_scan_payload("t0ken", base="https://hmis.hospital.local") == "https://hmis.hospital.local/#scan=t0ken"

    def test_build_scan_payload_never_embeds_asset_metadata(self):
        from app.assets.qr import build_scan_payload

        out = build_scan_payload("opaqueTOKENvalue1234", base="http://192.0.2.50:3000")
        # only the base URL and the token — nothing sensitive
        assert out == "http://192.0.2.50:3000/#scan=opaqueTOKENvalue1234"
        for leaked in ("AST-", "Store Room", "serial", "SN-", "location", "id="):
            assert leaked not in out

    def test_build_scan_payload_falls_back_to_bare_token_without_base(self):
        from app.assets.qr import build_scan_payload

        assert build_scan_payload("bareOpaqueToken12345") == "bareOpaqueToken12345"
        # a non-http value is rejected (no scheme injection)
        assert build_scan_payload("bareOpaqueToken12345", base="javascript:alert(1)") == "bareOpaqueToken12345"
        assert build_scan_payload("bareOpaqueToken12345", base="") == "bareOpaqueToken12345"

    async def test_qr_endpoint_encodes_the_scan_url_for_the_given_base(self, client, admin_headers):
        from app.printing.service import generate_qr_png

        loc = await _mk_location(client, admin_headers, "QR URL Loc")
        asset = await _mk_asset(client, admin_headers, name="Projector", location_id=loc["id"])
        base = "http://localhost:3000"

        r = await client.get(f"{BASE}/{asset['id']}/qr?base={base}", headers=admin_headers)
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        # QR generation is deterministic: the endpoint's image must be exactly
        # the QR for "<base>/#scan=<token>".
        expected = generate_qr_png(f"{base}/#scan={asset['qr_token']}")
        assert r.content == expected
        # and NOT the QR for the bare token
        assert r.content != generate_qr_png(asset["qr_token"])

    async def test_qr_endpoint_without_base_encodes_bare_token(self, client, admin_headers):
        from app.printing.service import generate_qr_png

        loc = await _mk_location(client, admin_headers, "QR NoBase Loc")
        asset = await _mk_asset(client, admin_headers, name="Kettle", location_id=loc["id"])
        r = await client.get(f"{BASE}/{asset['id']}/qr", headers=admin_headers)
        assert r.status_code == 200
        assert r.content == generate_qr_png(asset["qr_token"])

    async def test_label_pdf_embeds_the_scan_url_qr_and_stays_valid(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "Label URL Loc")
        asset = await _mk_asset(client, admin_headers, name="Desk Fan", location_id=loc["id"],
                                serial_number="FAN-SN-9", category="Appliance")
        r = await client.get(f"{BASE}/{asset['id']}/label?base=http://localhost:3000", headers=admin_headers)
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF-") and r.content.rstrip().endswith(b"%%EOF")
        # the label PDF must not carry the location / serial / asset code as
        # extractable text of the QR payload (the visible label legitimately
        # shows name + code, but the QR itself is only the scan URL)
        assert b"http://localhost:3000/#scan=" not in r.content  # it's a QR image, not text

    async def test_scan_url_token_still_resolves_and_is_unchanged_after_moves(self, client, admin_headers):
        a = await _mk_location(client, admin_headers, "Scan Move A")
        b = await _mk_location(client, admin_headers, "Scan Move B")
        c = await _mk_location(client, admin_headers, "Scan Move C")
        asset = await _mk_asset(client, admin_headers, name="Barcode Gun", location_id=a["id"])
        token = asset["qr_token"]

        await _move(client, admin_headers, asset["id"], b["id"])
        await _move(client, admin_headers, asset["id"], c["id"])

        # the same token the QR URL carries (…/#scan=<token>) resolves to live state
        resolved = await client.get(f"{BASE}/resolve/{token}", headers=admin_headers)
        assert resolved.status_code == 200
        assert resolved.json()["qr_token"] == token
        assert resolved.json()["current_location"]["name"] == "Scan Move C"

        # the QR image itself is unchanged by the moves
        from app.printing.service import generate_qr_png
        after = await client.get(f"{BASE}/{asset['id']}/qr?base=http://localhost:3000", headers=admin_headers)
        assert after.content == generate_qr_png(f"http://localhost:3000/#scan={token}")

    async def test_unauthenticated_scan_resolve_is_rejected(self, client, admin_headers):
        loc = await _mk_location(client, admin_headers, "Scan Auth Loc")
        asset = await _mk_asset(client, admin_headers, name="Tablet", location_id=loc["id"])
        # a phone that opened …/#scan=<token> still has to sign in; the resolve
        # endpoint is behind assets.read
        r = await client.get(f"{BASE}/resolve/{asset['qr_token']}")
        assert r.status_code == 401

    async def test_scan_resolve_works_for_reader_but_move_still_needs_permission(self, client, admin_headers, viewer_headers):
        a = await _mk_location(client, admin_headers, "Scan Rbac A")
        b = await _mk_location(client, admin_headers, "Scan Rbac B")
        asset = await _mk_asset(client, admin_headers, name="Label Maker", location_id=a["id"])
        token = asset["qr_token"]

        # assets.read user (nurse) can open the scanned asset…
        seen = await client.get(f"{BASE}/resolve/{token}", headers=viewer_headers)
        assert seen.status_code == 200
        assert seen.json()["current_location"]["name"] == "Scan Rbac A"
        # …but the QR sticker grants no move permission
        assert (await _move(client, viewer_headers, asset["id"], b["id"])).status_code == 403

    async def test_auth_me_exposes_permissions_so_the_mobile_page_can_hide_move(
        self, client, admin_headers, viewer_headers
    ):
        """The mobile scan page decides whether to show [ Move Asset ] from
        the current user's permission list — the backend still enforces it."""
        mgr = (await client.get("/api/v1/auth/me", headers=admin_headers)).json()
        assert "assets.move" in mgr["permissions"]
        assert "assets.read" in mgr["permissions"]

        viewer = (await client.get("/api/v1/auth/me", headers=viewer_headers)).json()
        assert "assets.read" in viewer["permissions"]
        assert "assets.move" not in viewer["permissions"]
