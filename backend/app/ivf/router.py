import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.ivf import service
from app.ivf import trigger_npo_service as tn_service
from app.ivf.trigger_npo_schemas import (
    EventMessageOut,
    NpoCreate,
    NpoOut,
    TriggerConfirm,
    TriggerCreate,
    TriggerOut,
    TriggerReschedule,
)
from app.ivf.schemas import (
    BetaHcgCreate,
    BetaHcgOut,
    CycleCreate,
    CycleOut,
    CycleStageUpdate,
    InjectionAdminister,
    InjectionOut,
    InjectionScheduleCreate,
    MilestoneCreate,
    MilestoneOut,
    MonitoringReview,
    MonitoringVisitCreate,
    MonitoringVisitOut,
    PregnancyOut,
    TreatmentPlanOut,
    TreatmentPlanUpsert,
    TreatmentProtocolOut,
    TreatmentProtocolUpsert,
)
from app.users.models import User

router = APIRouter(prefix="/ivf", tags=["ivf"])


@router.post("/cycles", response_model=CycleOut, status_code=201)
async def create_cycle(
    body: CycleCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> CycleOut:
    return await service.create_cycle(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/cycles/{cycle_id}", response_model=CycleOut)
async def get_cycle(
    cycle_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("ivf.read")),
) -> CycleOut:
    return await service.get_cycle(session, cycle_id)


@router.get("/cycles/by-couple/{couple_id}/active", response_model=CycleOut | None)
async def get_active_cycle(
    couple_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("ivf.read")),
) -> CycleOut | None:
    return await service.get_active_cycle_for_couple(session, couple_id)


@router.post("/cycles/{cycle_id}/stage", response_model=CycleOut)
async def advance_stage(
    cycle_id: str,
    body: CycleStageUpdate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> CycleOut:
    return await service.advance_stage(session, cycle_id, body.stage, actor_id=current.id, actor_role=current.role.code)


@router.put("/cycles/{cycle_id}/treatment-plan", response_model=TreatmentPlanOut)
async def save_treatment_plan(
    cycle_id: str,
    body: TreatmentPlanUpsert,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> TreatmentPlanOut:
    return await service.upsert_treatment_plan(session, cycle_id, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/cycles/{cycle_id}/protocol", response_model=TreatmentProtocolOut | None)
async def get_treatment_protocol(
    cycle_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("ivf.protocol.read")),
) -> TreatmentProtocolOut | None:
    """Restricted — Chief Consultant + Administrator only (source doc §7/§33).
    Deliberately its own endpoint, never embedded in GET /ivf/cycles/{id},
    so a broader ivf.read grant can never accidentally return this."""
    return await service.get_treatment_protocol(session, cycle_id)


@router.put("/cycles/{cycle_id}/protocol", response_model=TreatmentProtocolOut)
async def save_treatment_protocol(
    cycle_id: str,
    body: TreatmentProtocolUpsert,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.protocol.write")),
) -> TreatmentProtocolOut:
    return await service.upsert_treatment_protocol(session, cycle_id, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/injections", response_model=InjectionOut, status_code=201)
async def schedule_injection(
    body: InjectionScheduleCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> InjectionOut:
    return await service.schedule_injection(session, body, actor_id=current.id, actor_role=current.role.code)


@router.get("/injections/by-cycle/{cycle_id}", response_model=list[InjectionOut])
async def list_injections(
    cycle_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("ivf.read")),
) -> list[InjectionOut]:
    return await service.list_injections_for_cycle(session, cycle_id)


@router.post("/injections/{injection_id}/administer", response_model=InjectionOut)
async def administer_injection(
    injection_id: str,
    body: InjectionAdminister,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.monitoring.write")),
) -> InjectionOut:
    """Payment-gated — source doc §10. Raises 402 payment_required if
    the injections charge for this cycle isn't paid/overridden."""
    return await service.administer_injection(session, injection_id, body.notes, actor_id=current.id, actor_role=current.role.code)


@router.post("/monitoring", response_model=MonitoringVisitOut, status_code=201)
async def record_monitoring(
    body: MonitoringVisitCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.monitoring.write")),
) -> MonitoringVisitOut:
    return await service.record_monitoring_visit(session, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/monitoring/{visit_id}/review", response_model=MonitoringVisitOut)
async def review_monitoring(
    visit_id: str,
    body: MonitoringReview,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.monitoring.write")),
) -> MonitoringVisitOut:
    return await service.review_monitoring_visit(session, visit_id, body.doctor_note, actor_id=current.id, actor_role=current.role.code)


@router.get("/pregnancy/by-cycle/{cycle_id}", response_model=PregnancyOut)
async def get_pregnancy(
    cycle_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("ivf.read")),
) -> PregnancyOut:
    return await service.get_or_create_pregnancy(session, cycle_id)


@router.post("/pregnancy/beta-hcg", response_model=BetaHcgOut, status_code=201)
async def record_beta_hcg(
    body: BetaHcgCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> BetaHcgOut:
    return await service.record_beta_hcg(session, body, actor_id=current.id, actor_role=current.role.code)


@router.post("/pregnancy/milestones", response_model=MilestoneOut, status_code=201)
async def record_milestone(
    body: MilestoneCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> MilestoneOut:
    return await service.record_pregnancy_milestone(session, body, actor_id=current.id, actor_role=current.role.code)


# ===========================================================================
# Trigger injection & NPO — hospital-side clinical events. Notifications for
# these go to staff only (see app/ivf/trigger_npo_service.py); no patient send.
# ===========================================================================


@router.post("/cycles/{cycle_id}/trigger", response_model=TriggerOut, status_code=201)
async def create_trigger(
    cycle_id: uuid.UUID,
    body: TriggerCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> TriggerOut:
    return await tn_service.create_trigger(
        session, cycle_id, body, actor_id=current.id, actor_role=current.role.code
    )


@router.get("/cycles/{cycle_id}/trigger", response_model=TriggerOut | None)
async def get_cycle_trigger(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("ivf.read")),
) -> TriggerOut | None:
    return await tn_service.get_trigger_for_cycle(session, cycle_id)


@router.get("/triggers/{trigger_id}", response_model=TriggerOut)
async def get_trigger(
    trigger_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("ivf.read")),
) -> TriggerOut:
    return await tn_service.get_trigger(session, trigger_id)


@router.patch("/triggers/{trigger_id}", response_model=TriggerOut)
async def reschedule_trigger(
    trigger_id: uuid.UUID,
    body: TriggerReschedule,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> TriggerOut:
    return await tn_service.reschedule_trigger(
        session, trigger_id, body, actor_id=current.id, actor_role=current.role.code
    )


@router.post("/triggers/{trigger_id}/acknowledge", response_model=TriggerOut)
async def acknowledge_trigger(
    trigger_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> TriggerOut:
    return await tn_service.acknowledge_trigger(
        session, trigger_id, actor_id=current.id, actor_role=current.role.code
    )


@router.post("/triggers/{trigger_id}/confirm", response_model=TriggerOut)
async def confirm_trigger(
    trigger_id: uuid.UUID,
    body: TriggerConfirm,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> TriggerOut:
    return await tn_service.confirm_trigger(
        session, trigger_id, body.confirmed_at, actor_id=current.id, actor_role=current.role.code
    )


@router.get("/triggers/{trigger_id}/notifications", response_model=list[EventMessageOut])
async def trigger_notifications(
    trigger_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("ivf.read")),
) -> list[EventMessageOut]:
    from app.messaging.service import list_event_messages

    return await list_event_messages(session, event_type=tn_service.TRIGGER_EVENT, event_id=str(trigger_id))


@router.post("/cycles/{cycle_id}/npo", response_model=NpoOut, status_code=201)
async def create_npo(
    cycle_id: uuid.UUID,
    body: NpoCreate,
    session: AsyncSession = Depends(get_db),
    current: User = Depends(require_permission("ivf.write")),
) -> NpoOut:
    return await tn_service.create_npo(
        session, cycle_id, body, actor_id=current.id, actor_role=current.role.code
    )


@router.get("/cycles/{cycle_id}/npo", response_model=NpoOut | None)
async def get_cycle_npo(
    cycle_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("ivf.read")),
) -> NpoOut | None:
    return await tn_service.get_npo_for_cycle(session, cycle_id)


@router.get("/npo/{npo_id}/notifications", response_model=list[EventMessageOut])
async def npo_notifications(
    npo_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("ivf.read")),
) -> list[EventMessageOut]:
    from app.messaging.service import list_event_messages

    return await list_event_messages(session, event_type=tn_service.NPO_EVENT, event_id=str(npo_id))
