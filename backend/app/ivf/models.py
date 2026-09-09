"""
IVF cycle, treatment plan, and stimulation monitoring — from the
frontend's Plan.tsx stage tracker and MonitoringVisit shape (follicle
arrays + hormone panel powering the FollicleMap component unchanged).
"""
import enum
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class CycleStage(str, enum.Enum):
    ASSESSMENT = "assessment"
    STIMULATION = "stimulation"
    TRIGGER = "trigger"
    RETRIEVAL = "retrieval"
    EMBRYOLOGY = "embryology"
    TRANSFER = "transfer"
    PREGNANCY_FOLLOWUP = "pregnancy_followup"
    COMPLETED = "completed"


class IVFCycle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ivf_cycles"

    cycle_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)  # IVF-2026-00428
    couple_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("couples.id"), nullable=False, index=True)
    primary_doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    protocol: Mapped[str] = mapped_column(String(128), nullable=False)  # "GnRH Antagonist Protocol"
    treatment: Mapped[str] = mapped_column(String(128), nullable=False)  # "IVF with ICSI"
    stage: Mapped[CycleStage] = mapped_column(Enum(CycleStage), default=CycleStage.ASSESSMENT, index=True)
    started_at: Mapped[date] = mapped_column(Date, nullable=False)

    treatment_plans: Mapped[list["TreatmentPlan"]] = relationship(back_populates="cycle", lazy="selectin")
    monitoring_visits: Mapped[list["MonitoringVisit"]] = relationship(back_populates="cycle", lazy="selectin")
    # Deliberately NOT lazy="selectin" — unlike every other cycle relationship,
    # the restricted protocol must never be pulled in "for free" by a normal
    # GET /ivf/cycles/{id} response. Callers fetch it explicitly through the
    # separate, permission-gated /ivf/cycles/{id}/protocol endpoint only.
    treatment_protocol: Mapped["TreatmentProtocol | None"] = relationship(back_populates="cycle", uselist=False)


class TreatmentPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "treatment_plans"

    cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ivf_cycles.id"), nullable=False, index=True)
    cycle: Mapped["IVFCycle"] = relationship(back_populates="treatment_plans")

    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    medication_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # list of {name, dose, route, status}
    consent_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)  # "Remarks" per source doc §7 — normal ivf.read/write visibility


class TreatmentProtocol(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The restricted "Protocol" leg of Planning (source doc §7). Deliberately
    a separate table from TreatmentPlan, not just a permission check on a
    shared row — a future `SELECT *` on treatment_plans (e.g. an export, a
    join, a report query) can never accidentally leak this by construction.
    Gated by ivf.protocol.read/write, currently granted only to the
    `chief_consultant` and `administrator` roles (roles/seed.py) — never
    broaden this without an explicit decision, per source doc §33."""
    __tablename__ = "treatment_protocols"

    cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ivf_cycles.id"), nullable=False, index=True)
    cycle: Mapped["IVFCycle"] = relationship(back_populates="treatment_protocol")

    content: Mapped[str] = mapped_column(Text, nullable=False)
    fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # configurable structured fields, per source doc §7
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class InjectionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    ADMINISTERED = "administered"
    SKIPPED = "skipped"


class InjectionAdministration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """New requirement (source doc §10) — a real, queryable, state-machine
    table for the 'prescribed vs administered' distinction. Previously
    this only existed as a free-text `status` key inside
    TreatmentPlan.medication_plan JSON, which the source doc's own rules
    forbid relying on for a critical, auditable, payment-gated action.
    Deliberately does NOT model a full prescription/dosage-template system
    (source doc §9's prescription color/template is explicitly blocked on
    the hospital providing the actual paper form — see
    NEW_FEATURES_GAP_ANALYSIS.md §6) — this only tracks the administration
    event itself, referencing the medicine/dose as recorded on the plan."""
    __tablename__ = "injection_administrations"

    cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ivf_cycles.id"), nullable=False, index=True)
    medicine_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dose: Mapped[str] = mapped_column(String(64), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[InjectionStatus] = mapped_column(Enum(InjectionStatus), default=InjectionStatus.SCHEDULED, index=True)

    administered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    administered_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class MonitoringVisit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Follicle sizes stored as JSON arrays (mm) — matches the frontend's
    MonitoringVisit.right/left shape exactly, so the FollicleMap SVG
    component needs zero changes when wired to real data."""
    __tablename__ = "monitoring_visits"

    cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ivf_cycles.id"), nullable=False, index=True)
    cycle: Mapped["IVFCycle"] = relationship(back_populates="monitoring_visits")

    cycle_day: Mapped[int] = mapped_column(nullable=False)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)

    right_follicles_mm: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    left_follicles_mm: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    endometrium_mm: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False)

    estradiol_pg_ml: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    lh_miu_ml: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    progesterone_ng_ml: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    doctor_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PregnancyOutcome(str, enum.Enum):
    PENDING = "pending"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    BIOCHEMICAL_ONLY = "biochemical_only"


class PregnancyRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pregnancy_records"

    cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ivf_cycles.id"), nullable=False, unique=True, index=True)
    transfer_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    outcome: Mapped[PregnancyOutcome] = mapped_column(Enum(PregnancyOutcome), default=PregnancyOutcome.PENDING)
    estimated_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    beta_hcg_results: Mapped[list["BetaHcgResult"]] = relationship(back_populates="pregnancy", lazy="selectin")
    milestones: Mapped[list["PregnancyMilestone"]] = relationship(back_populates="pregnancy", lazy="selectin")


class BetaHcgResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "beta_hcg_results"

    pregnancy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pregnancy_records.id"), nullable=False)
    pregnancy: Mapped["PregnancyRecord"] = relationship(back_populates="beta_hcg_results")

    day_label: Mapped[str] = mapped_column(String(32), nullable=False)  # "Day 14"
    value_miu_ml: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    recorded_at: Mapped[date] = mapped_column(Date, nullable=False)
    interpretation: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PregnancyMilestone(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "pregnancy_milestones"

    pregnancy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pregnancy_records.id"), nullable=False)
    pregnancy: Mapped["PregnancyRecord"] = relationship(back_populates="milestones")

    label: Mapped[str] = mapped_column(String(128), nullable=False)  # "Gestational Sac", "Cardiac Activity"
    milestone_date: Mapped[date] = mapped_column(Date, nullable=False)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_completed: Mapped[bool] = mapped_column(default=True)


# ===========================================================================
# Trigger injection & NPO — hospital-side clinical events that drive internal
# staff notifications (never patient messages). Kept in the ivf module because
# both belong to an IVF cycle; deliberately two small tables, no more.
# ===========================================================================


class TriggerStatus(str, enum.Enum):
    # Lowercase member names so SQLAlchemy's Enum stores the same string the
    # migration's PG enum defines (matches ReportStatus / MessageStatus).
    planned = "planned"      # scheduled, not yet actioned
    confirmed = "confirmed"  # staff confirmed the injection was given
    overdue = "overdue"      # planned time passed, all reminders sent, still unacknowledged


class TriggerInjection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One trigger shot per cycle. ``planned_at`` is editable (rescheduling);
    every change is written to the audit trail and resets the reminder run so
    notifications follow the NEW time. Reminders go to hospital staff only."""
    __tablename__ = "trigger_injections"

    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ivf_cycles.id"), nullable=False, index=True
    )
    cycle: Mapped["IVFCycle"] = relationship()

    medicine: Mapped[str] = mapped_column(String(128), nullable=False)  # e.g. "Inj. Ovitrelle 250mcg"
    planned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    status: Mapped[TriggerStatus] = mapped_column(
        Enum(TriggerStatus, name="trigger_status"), nullable=False, default=TriggerStatus.planned, index=True
    )

    # Acknowledgement (a staff member has seen the reminder and is on it) is the
    # minimum extra state the 5-minute retry loop needs: reminders stop as soon
    # as this OR confirmed_at is set. Confirmation is the stronger, final action.
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # How many reminders have gone out for the CURRENT planned_at. Reset to 0 on
    # reschedule. The scheduled task stops once this reaches the configured max.
    reminders_sent: Mapped[int] = mapped_column(nullable=False, default=0)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NpoWindow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The nil-by-mouth window for a cycle's procedure. ``start_at`` is either
    given directly or computed as (procedure time - configured lead time); the
    lead time is never hardcoded in clinical logic. Notification is staff-only."""
    __tablename__ = "npo_windows"

    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ivf_cycles.id"), nullable=False, index=True
    )
    cycle: Mapped["IVFCycle"] = relationship()

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "Oocyte retrieval under sedation"

    # Set once the "NPO started" staff notification has been generated — the
    # idempotency guard for that one-shot send.
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
