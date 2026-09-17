"""
Imports every module's models so `Base.metadata` is fully populated
before Alembic's autogenerate (or `Base.metadata.create_all` in tests)
runs. Nothing in here is used directly — the imports are the point.
"""
from app.accounting import models as _accounting_models  # noqa: F401
from app.appointments import models as _appointments_models  # noqa: F401
from app.assets import models as _assets_models  # noqa: F401
from app.audit import models as _audit_models  # noqa: F401
from app.auth import models as _auth_models  # noqa: F401
from app.billing import models as _billing_models  # noqa: F401
from app.clinical import models as _clinical_models  # noqa: F401
from app.clinical_documents import models as _clinical_documents_models  # noqa: F401
from app.core.idempotency import IdempotencyRecord  # noqa: F401
from app.cryostorage import models as _cryostorage_models  # noqa: F401
from app.donor import models as _donor_models  # noqa: F401
from app.embryology import models as _embryology_models  # noqa: F401
from app.events import models as _events_models  # noqa: F401
from app.hr import models as _hr_models  # noqa: F401
from app.inventory import models as _inventory_models  # noqa: F401
from app.ivf import models as _ivf_models  # noqa: F401
from app.laboratory import models as _laboratory_models  # noqa: F401
from app.maintenance import models as _maintenance_models  # noqa: F401
from app.messaging import models as _messaging_models  # noqa: F401
from app.notifications import models as _notifications_models  # noqa: F401
from app.nursing import models as _nursing_models  # noqa: F401
from app.ot import models as _ot_models  # noqa: F401
from app.patients import models as _patients_models  # noqa: F401
from app.pharmacy import models as _pharmacy_models  # noqa: F401
from app.pharmacy import templates as _pharmacy_templates_models  # noqa: F401
from app.pharmacy import purchase_returns as _pharmacy_purchase_returns_models  # noqa: F401
from app.pharmacy import purchase_orders as _pharmacy_purchase_orders_models  # noqa: F401
from app.pharmacy import settings as _pharmacy_settings_models  # noqa: F401
from app.prescription import models as _prescription_models  # noqa: F401
from app.printing import models as _printing_models  # noqa: F401
from app.purchasing import models as _purchasing_models  # noqa: F401
from app.quality import models as _quality_models  # noqa: F401
from app.reports import job_models as _reports_job_models  # noqa: F401
from app.roles import models as _roles_models  # noqa: F401
from app.users import models as _users_models  # noqa: F401
