"""
Default roles and the granular permission taxonomy, per enterprise
spec §6. Run via `python -m app.roles.seed` or automatically on first
container start (see backend/scripts/seed_db.py).

Role set matches the spec's 10 roles. The existing frontend prototype's
4 demo roles (doctor, receptionist, embryologist, management) map onto
this richer set — `management` maps to `admin`+`it_admin` combined
visibility for the prototype's demo purposes; production deployments
should split these into distinct accounts.
"""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.roles.models import Permission, Role

# ---------------------------------------------------------------------------
# Permission taxonomy — module.action strings, per spec §6 examples plus the
# full module list this backend implements.
# ---------------------------------------------------------------------------
PERMISSIONS: list[tuple[str, str, str, bool]] = [
    # (code, module, description, is_critical)
    # Patients
    ("patients.read", "patients", "View patient records", False),
    ("patients.create", "patients", "Register new patients/couples", False),
    ("patients.update", "patients", "Edit patient demographic/medical data", False),
    ("patients.merge", "patients", "Merge duplicate patient records", True),
    ("patients.sensitive_documents", "patients", "View/download Aadhaar, visa and other identity documents", True),
    # Appointments
    ("appointments.read", "appointments", "View appointment book", False),
    ("appointments.create", "appointments", "Book appointments", False),
    ("appointments.checkin", "appointments", "Check in a patient", False),
    ("appointments.cancel", "appointments", "Cancel an appointment", False),
    # Clinical
    ("clinical.read", "clinical", "View consultations and clinical notes", False),
    ("clinical.write", "clinical", "Create/edit clinical notes", False),
    ("clinical.correct", "clinical", "Issue a correction to a signed clinical record", True),
    # Nursing — minimal vitals/observations scaffold (full workflow unconfirmed)
    ("nursing.read", "nursing", "View nursing records / recorded vitals", False),
    ("nursing.create", "nursing", "Record nursing vitals and observations", False),
    # IVF
    ("ivf.read", "ivf", "View IVF cycle and treatment plan data", False),
    ("ivf.write", "ivf", "Create/edit IVF cycles and treatment plans", False),
    ("ivf.monitoring.write", "ivf", "Record stimulation monitoring visits", False),
    ("ivf.protocol.read", "ivf", "View the restricted treatment protocol", True),
    ("ivf.protocol.write", "ivf", "Write the restricted treatment protocol", True),
    # Embryology
    ("embryology.read", "embryology", "View embryology records", False),
    ("embryology.write", "embryology", "Grade and record embryo development", False),
    ("embryology.transfer", "embryology", "Perform/confirm embryo transfer", True),
    # Cryostorage
    ("cryostorage.read", "cryostorage", "View cryostorage inventory", False),
    ("cryostorage.move", "cryostorage", "Move stored embryos between locations", True),
    # Laboratory
    ("laboratory.read", "laboratory", "View lab orders and results", False),
    ("laboratory.order", "laboratory", "Order lab tests", False),
    ("laboratory.result", "laboratory", "Enter/verify lab results", False),
    ("laboratory.upload", "laboratory", "Upload an outside-lab report and run extraction", False),
    ("laboratory.correct", "laboratory", "Correct an extracted lab result or add one by hand", True),
    # OT
    ("ot.read", "ot", "View OT schedule", False),
    ("ot.schedule", "ot", "Schedule OT procedures", False),
    ("ot.checklist", "ot", "Complete OT readiness checklists", False),
    # Pharmacy
    ("pharmacy.read", "pharmacy", "View pharmacy stock and sales", False),
    ("pharmacy.dispense", "pharmacy", "Dispense medicine to a patient", True),
    ("pharmacy.return", "pharmacy", "Process a pharmacy return", True),
    ("pharmacy.manage", "pharmacy", "Manage the medicine catalogue and attributes", False),
    ("pharmacy.purchase", "pharmacy", "Create and receive pharmacy purchases (GRN)", False),
    ("pharmacy.adjust", "pharmacy", "Record a manual pharmacy stock adjustment", True),
    ("pharmacy.indent_request", "pharmacy", "Raise a department indent request to the pharmacy", False),
    ("pharmacy.indent_deliver", "pharmacy", "Deliver/return medicines against a pharmacy indent", True),
    ("pharmacy.purchase_return", "pharmacy", "Return purchased stock back to a vendor", True),
    ("pharmacy.po_create", "pharmacy", "Create/edit a pharmacy purchase order", False),
    ("pharmacy.po_approve", "pharmacy", "Approve/cancel a pharmacy purchase order", True),
    ("pharmacy.settings_manage", "pharmacy", "Edit pharmacy print/invoice settings", True),
    # Inventory
    ("inventory.read", "inventory", "View inventory levels", False),
    ("inventory.adjust", "inventory", "Adjust inventory stock counts", True),
    ("inventory.write_off", "inventory", "Write off damaged/expired stock", True),
    # Purchasing
    ("purchasing.read", "purchasing", "View purchase requests/orders", False),
    ("purchasing.request", "purchasing", "Submit a purchase request", False),
    ("purchasing.approve", "purchasing", "Approve a purchase order", True),
    ("purchasing.receive", "purchasing", "Record goods receipt (GRN)", False),
    ("purchasing.vendor_manage", "purchasing", "Add/edit vendors", False),
    # Billing
    ("billing.read", "billing", "View invoices and payment status", False),
    ("billing.create", "billing", "Create charges and invoices", False),
    ("billing.payment", "billing", "Record a payment", False),
    ("billing.refund", "billing", "Issue a refund", True),
    ("billing.override", "billing", "Override the billing lock (emergency)", True),
    ("billing.discount", "billing", "Apply a discount to an invoice", True),
    # Accounting
    ("accounting.read", "accounting", "View ledger, cash book, GST reports", False),
    ("accounting.write", "accounting", "Post accounting entries", True),
    # Assets
    ("assets.read", "assets", "View asset register and location history", False),
    ("assets.register", "assets", "Register/edit assets and manage locations", False),
    ("assets.move", "assets", "Record an official asset location change", False),
    ("assets.delete", "assets", "Retire/delete an asset record", True),
    # Maintenance
    ("maintenance.read", "maintenance", "View maintenance schedule", False),
    ("maintenance.complete", "maintenance", "Mark maintenance task complete", False),
    # Quality
    ("quality.read", "quality", "View QA/QC checklists", False),
    ("quality.complete", "quality", "Complete a QA/QC task", False),
    # HR
    ("hr.read", "hr", "View employee directory", False),
    ("hr.write", "hr", "Edit employee records", True),
    ("hr.approve_leave", "hr", "Approve/reject leave requests", False),
    # Reports
    ("reports.read", "reports", "View operational/clinical reports", False),
    ("reports.export", "reports", "Export reports", False),
    ("reports.generate", "reports", "Submit an asynchronous report-generation job", False),
    # Audit
    ("audit.read", "audit", "View the audit log", True),
    # Messaging — new module, source doc §26-27
    ("messaging.send", "messaging", "Send WhatsApp/SMS messages and view message history", False),
    # Donor management — new module, source doc §22-23
    ("donor.read", "donor", "View donor records and matching history", False),
    ("donor.write", "donor", "Register donors and record benchmarks", False),
    ("donor.match", "donor", "Match/unmatch a donor to a patient", True),
    # Admin
    ("admin.manage_users", "admin", "Create/edit/deactivate user accounts", True),
    ("admin.manage_roles", "admin", "Edit role/permission assignments", True),
    ("admin.manage_settings", "admin", "Edit master settings (charges, packages, tests)", True),
]

# ---------------------------------------------------------------------------
# Default roles and the permission codes each one gets out of the box.
# ---------------------------------------------------------------------------
ROLE_DEFAULTS: dict[str, tuple[str, list[str]]] = {
    "doctor": ("Doctor", [
        "patients.read", "patients.create", "patients.update", "patients.sensitive_documents",
        "appointments.read", "appointments.create", "appointments.checkin", "appointments.cancel",
        "clinical.read", "clinical.write", "clinical.correct",
        "nursing.read", "nursing.create",
        "ivf.read", "ivf.write", "ivf.monitoring.write",
        "embryology.read", "embryology.transfer",
        "cryostorage.read",
        "laboratory.read", "laboratory.order", "laboratory.upload", "laboratory.correct",
        "ot.read", "ot.schedule",
        "pharmacy.read", "pharmacy.indent_request",
        "billing.read", "billing.override", "donor.read",
        "reports.read", "reports.generate", "audit.read",
    ]),
    "nurse": ("Nurse", [
        "patients.read", "appointments.read", "appointments.checkin",
        "clinical.read", "clinical.write",
        "nursing.read", "nursing.create",
        "ivf.read", "ivf.monitoring.write",
        "ot.read", "ot.checklist",
        "pharmacy.read", "pharmacy.indent_request",
        "assets.read",
    ]),
    "receptionist": ("Receptionist", [
        "patients.read", "patients.create", "patients.sensitive_documents",
        "appointments.read", "appointments.create", "appointments.checkin", "appointments.cancel",
        "billing.read", "billing.create", "billing.payment",
        "pharmacy.read",
        "messaging.send",
        "assets.read",
    ]),
    "embryologist": ("Embryologist", [
        "patients.read",
        "ivf.read",
        "embryology.read", "embryology.write", "embryology.transfer",
        "cryostorage.read", "cryostorage.move",
        "laboratory.read", "laboratory.result", "laboratory.upload", "laboratory.correct",
        "inventory.read",
        "donor.read", "donor.write", "donor.match",
    ]),
    "lab_technician": ("Lab Technician", [
        "patients.read",
        "laboratory.read", "laboratory.order", "laboratory.result",
        "laboratory.upload", "laboratory.correct",
        "quality.read", "quality.complete",
    ]),
    "pharmacist": ("Pharmacist", [
        "patients.read",
        "pharmacy.read", "pharmacy.dispense", "pharmacy.return", "pharmacy.manage", "pharmacy.purchase", "pharmacy.adjust",
        "pharmacy.indent_request", "pharmacy.indent_deliver", "pharmacy.purchase_return", "pharmacy.po_create",
        "pharmacy.settings_manage",
        "reports.read", "reports.export",
        "inventory.read",
        "purchasing.read", "purchasing.request", "purchasing.receive", "purchasing.vendor_manage",
    ]),
    "accountant": ("Accountant", [
        "billing.read", "billing.create", "billing.payment", "billing.refund",
        "accounting.read", "accounting.write",
        "reports.read", "reports.export", "reports.generate",
    ]),
    "management": ("Management", [
        "patients.read", "appointments.read",
        "billing.read", "accounting.read",
        "pharmacy.read", "pharmacy.indent_request", "pharmacy.po_approve",
        "inventory.read", "purchasing.read", "purchasing.approve",
        "hr.read", "hr.approve_leave",
        "reports.read", "reports.export", "reports.generate",
        "audit.read",
        "maintenance.read", "quality.read",
        "assets.read", "assets.register", "assets.move",
    ]),
    "chief_consultant": ("Chief Consultant", [
        # Everything a doctor has, plus the restricted treatment protocol.
        # New requirement (source doc §7/§33): "Protocol = Akshana Ma'am +
        # Admin only." RBAC in this system is role-based, not per-user, so
        # this role exists specifically to be assigned to that one
        # individual (and any future chief consultant) without widening
        # what the general "doctor" role can see — do not add
        # ivf.protocol.* to the doctor role.
        "patients.read", "patients.create", "patients.update", "patients.sensitive_documents",
        "appointments.read", "appointments.create", "appointments.checkin", "appointments.cancel",
        "clinical.read", "clinical.write", "clinical.correct",
        "nursing.read", "nursing.create",
        "ivf.read", "ivf.write", "ivf.monitoring.write", "ivf.protocol.read", "ivf.protocol.write",
        "embryology.read", "embryology.transfer",
        "cryostorage.read",
        "laboratory.read", "laboratory.order", "laboratory.upload", "laboratory.correct",
        "ot.read", "ot.schedule",
        "pharmacy.read", "pharmacy.indent_request",
        "billing.read", "billing.override", "donor.read",
        "reports.read", "reports.generate", "audit.read",
    ]),
    "administrator": ("Administrator", ["*"]),  # gets every permission below
    "it_administrator": ("IT Administrator", [
        "admin.manage_users", "admin.manage_roles", "admin.manage_settings",
        "audit.read", "reports.read",
    ]),
}


async def seed_roles_and_permissions(session: AsyncSession) -> None:
    existing = (await session.execute(select(Permission.code))).scalars().all()
    existing_codes = set(existing)

    perms_by_code: dict[str, Permission] = {}
    for code, module, desc, critical in PERMISSIONS:
        if code in existing_codes:
            continue
        perm = Permission(code=code, module=module, description=desc, is_critical=critical)
        session.add(perm)
        perms_by_code[code] = perm
    await session.flush()

    # reload full set (existing + just-created) so role assignment can reference any of them
    all_perms = {p.code: p for p in (await session.execute(select(Permission))).scalars().all()}

    existing_roles = {r.code for r in (await session.execute(select(Role))).scalars().all()}

    for role_code, (name, perm_codes) in ROLE_DEFAULTS.items():
        if role_code in existing_roles:
            # Every system role (defined here in code, not created by a
            # hospital admin) is re-synced to exactly match ROLE_DEFAULTS on
            # every run — not just the "*" wildcard role. Without this, a
            # permission added to an existing role's list here (e.g.
            # donor.read added to "embryologist" after that role was first
            # seeded) would silently never reach an already-seeded database,
            # which is exactly the bug that shipped ivf.protocol.* and
            # donor.* without embryologist/doctor actually getting them. A
            # hospital that wants to customize permissions for a role
            # should create a NEW role rather than editing a system one —
            # this resync would otherwise undo that edit on the next deploy.
            result = await session.execute(select(Role).where(Role.code == role_code))
            role = result.scalar_one()
            role.permissions = list(all_perms.values()) if perm_codes == ["*"] else [all_perms[c] for c in perm_codes if c in all_perms]
            session.add(role)
            continue
        role = Role(code=role_code, name=name, is_system_role=True)
        if perm_codes == ["*"]:
            role.permissions = list(all_perms.values())
        else:
            role.permissions = [all_perms[c] for c in perm_codes if c in all_perms]
        session.add(role)

    await session.flush()


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_roles_and_permissions(session)
        await session.commit()
    print(f"Seeded {len(PERMISSIONS)} permissions and {len(ROLE_DEFAULTS)} roles.")


if __name__ == "__main__":
    asyncio.run(main())
