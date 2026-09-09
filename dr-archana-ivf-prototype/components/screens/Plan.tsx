'use client';

import React, { useState } from 'react';
import { useApp, type ScreenId } from '@/lib/store';
import { PATIENT, PARTNER, MEDICATIONS, PACKAGE, INVESTIGATIONS } from '@/lib/data';
import { cn, formatINR } from '@/lib/utils';
import { Card, CardHeader, Badge, Button, SectionTitle, Field, DataRow, InfoNote, ProgressBar, Input } from '@/components/ui/primitives';
import { CycleTriggerNpoPanel } from '@/components/ivf/CycleTriggerNpoPanel';
import { PatientHeader } from './Workspace';
import { useCoupleForPatient } from '@/lib/api/patients';
import {
  useActiveCycle,
  useSaveTreatmentPlan,
  useTreatmentProtocol,
  useSaveTreatmentProtocol,
  useInjections,
  useScheduleInjection,
  useAdministerInjection,
  type CycleStage,
} from '@/lib/api/ivf';
import { ApiError } from '@/lib/api/client';
import {
  ClipboardList,
  Pill,
  Target,
  ShieldCheck,
  Receipt,
  FlaskConical,
  Check,
  CircleDot,
  Circle,
  Stethoscope,
  Lock,
  Syringe,
  Plus,
} from 'lucide-react';

const UI_STAGES = [
  { id: 'consult', label: 'Consultation' },
  { id: 'stim', label: 'Stimulation' },
  { id: 'retrieval', label: 'Retrieval' },
  { id: 'embryology', label: 'Embryology' },
  { id: 'transfer', label: 'Transfer' },
  { id: 'followup', label: 'Follow-up' },
] as const;

/** Backend has 8 granular stages; this screen's tracker shows 6. Multiple
 * backend stages collapse onto one UI step (stimulation+trigger -> "stim",
 * pregnancy_followup+completed -> "followup") rather than the tracker
 * needing its own redesign. */
const STAGE_TO_UI_INDEX: Record<CycleStage, number> = {
  assessment: 0,
  stimulation: 1,
  trigger: 1,
  retrieval: 2,
  embryology: 3,
  transfer: 4,
  pregnancy_followup: 5,
  completed: 5,
};

function buildStages(currentStage: CycleStage | null) {
  const activeIdx = currentStage ? STAGE_TO_UI_INDEX[currentStage] : 1;
  return UI_STAGES.map((s, i) => ({
    ...s,
    status: i < activeIdx ? 'done' : i === activeIdx ? 'active' : 'todo',
  }));
}

export function Plan() {
  const { go, toast, selectedPatientId } = useApp();
  const coupleQuery = useCoupleForPatient(selectedPatientId);
  const cycleQuery = useActiveCycle(coupleQuery.data?.id ?? null);
  const savePlan = useSaveTreatmentPlan();

  const cycle = cycleQuery.data ?? null;

  // Restricted protocol — Chief Consultant + Admin only. A failed fetch
  // (403 for every other role) means the card simply doesn't render,
  // never a frontend-only hide of data that was already sent.
  const protocolQuery = useTreatmentProtocol(cycle?.id ?? null);
  const saveProtocol = useSaveTreatmentProtocol();
  const [protocolDraft, setProtocolDraft] = useState('');
  const [protocolEditing, setProtocolEditing] = useState(false);
  const canSeeProtocol = !protocolQuery.isError && !!cycle;

  const injectionsQuery = useInjections(cycle?.id ?? null);
  const scheduleInjection = useScheduleInjection();
  const administerInjection = useAdministerInjection();
  const [newInjection, setNewInjection] = useState({ medicine_name: '', dose: '', scheduled_at: '' });
  const plan = cycle?.treatment_plans?.[0] ?? null;
  const stages = buildStages(cycle?.stage ?? null);
  const activeIdx = stages.findIndex((s) => s.status === 'active');
  const progressPct = ((activeIdx >= 0 ? activeIdx : 1) / (UI_STAGES.length - 1)) * 100;

  // Real medication_plan rows are {name, dose, route, status} — no
  // `since`/`tone`, which only the static demo fixture carries.
  type MedicationRow = { name: string; dose: string; route: string; status: string; since?: string; tone?: import('@/lib/data').StatusTone };
  const medications: MedicationRow[] = plan?.medication_plan?.length ? plan.medication_plan : MEDICATIONS;

  const confirmPlan = () => {
    if (!cycle) {
      toast({ title: 'Treatment plan confirmed', body: 'Plan re-confirmed and recorded in the audit trail.', tone: 'success' });
      return;
    }
    savePlan.mutate(
      {
        cycleId: cycle.id,
        objective: plan?.objective ?? 'Achieve a single healthy ongoing pregnancy',
        medication_plan: plan?.medication_plan ?? null,
        notes: plan?.notes ?? null,
      },
      {
        onSuccess: () => toast({ title: 'Treatment plan confirmed', body: 'Plan re-confirmed and recorded in the audit trail.', tone: 'success' }),
        onError: (err) => toast({ title: 'Could not save plan', body: err instanceof ApiError ? err.message : 'Please try again.', tone: 'error' }),
      }
    );
  };

  return (
    <div className="screen-enter mx-auto max-w-[1300px] space-y-5 p-4 sm:p-6 lg:p-8">
      <PatientHeader compact />

      <SectionTitle
        eyebrow={cycle ? `Cycle ${cycle.cycle_number}` : `Cycle ${PATIENT.cycleId}`}
        title="IVF Treatment Plan"
        description="Protocol, objectives, medication schedule and expected stages"
        action={
          <Button variant="primary" icon={<Check className="h-4 w-4" />} loading={savePlan.isPending} onClick={confirmPlan}>
            Confirm Plan
          </Button>
        }
      />

      {/* ============ STAGE TRACKER ============ */}
      <Card className="p-4 sm:p-5">
        <div className="relative">
          <div className="absolute left-0 right-0 top-[15px] h-[2px] bg-ink-200" />
          <div
            className="absolute left-0 top-[15px] h-[2px] bg-gradient-to-r from-brand-500 to-brand-600 transition-[width] duration-[1500ms] ease-spring"
            style={{ width: `${progressPct}%` }}
          />
          <div className="relative flex justify-between">
            {stages.map((s, i) => (
              <div key={s.id} className="animate-fade-up flex min-w-0 flex-1 flex-col items-center px-0.5" style={{ animationDelay: `${i * 80}ms` }}>
                <div
                  className={cn(
                    'relative z-10 flex h-8 w-8 items-center justify-center rounded-full ring-4 ring-white',
                    s.status === 'done' ? 'bg-brand-600' : s.status === 'active' ? 'bg-amber-500' : 'border-2 border-dashed border-ink-300 bg-white'
                  )}
                >
                  {s.status === 'active' && <span className="absolute inset-0 animate-pulse-ring rounded-full bg-amber-400/50" />}
                  {s.status === 'done' ? (
                    <Check className="h-4 w-4 text-white" strokeWidth={3} />
                  ) : s.status === 'active' ? (
                    <CircleDot className="h-4 w-4 text-white" />
                  ) : (
                    <Circle className="h-2.5 w-2.5 text-ink-300" fill="currentColor" />
                  )}
                </div>
                <p
                  className={cn(
                    'mt-2 max-w-full text-center text-[11.5px] font-medium leading-tight sm:text-[13px]',
                    s.status === 'todo' ? 'text-ink-400' : 'text-ink-900'
                  )}
                >
                  {s.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* ============ PLAN CORE ============ */}
        <div className="min-w-0 space-y-5 lg:col-span-2">
          <Card>
            <CardHeader
              icon={<ClipboardList className="h-4 w-4" />}
              title="Treatment Configuration"
              subtitle="Agreed with the couple on 12 July 2026"
              action={<Badge tone="active">Active</Badge>}
            />
            <div className="grid gap-4 px-5 pb-5 sm:grid-cols-2">
              <Field label="Treatment" value={cycle?.treatment ?? PATIENT.treatment} />
              <Field label="Protocol" value={cycle?.protocol ?? PATIENT.protocol} />
              <Field label="Indication" value={`${PATIENT.infertilityType} — ${PATIENT.duration}`} />
              <Field label="Fertilisation Method" value="ICSI (partner factor)" />
              <Field label="Transfer Strategy" value="Elective single blastocyst transfer" />
              <Field label="Surplus Embryos" value="Vitrification offered and consented" />
            </div>

            <div className="px-5 pb-5">
              <InfoNote tone="brand" icon={<Target className="h-4 w-4" />}>
                <span className="font-medium">Treatment objective:</span> achieve a single healthy
                ongoing pregnancy while minimising the risk of ovarian hyperstimulation and multiple
                gestation. ICSI is indicated by the partner&apos;s semen analysis.
              </InfoNote>
            </div>
          </Card>

          <Card>
            <CardHeader icon={<Pill className="h-4 w-4" />} title="Medication Plan" subtitle="Stimulation and adjunct therapy" />
            <div className="stagger space-y-2 px-5 pb-5">
              {medications.map((m, i) => {
                const since = m.since ?? null;
                const tone = m.tone ?? 'active';
                return (
                  <div
                    key={m.name}
                    style={{ ['--i' as string]: i }}
                    className="flex flex-wrap items-center gap-3 rounded-xl border border-ink-200/70 p-3.5"
                  >
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                      <Pill className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[14.5px] font-semibold text-ink-900">
                        {m.name} <span className="tnum font-normal text-ink-500">· {m.dose}</span>
                      </p>
                      <p className="text-[13px] text-ink-500">{m.route}</p>
                    </div>
                    {since && <span className="text-[12.5px] text-ink-400">From {since}</span>}
                    <Badge tone={tone} size="sm">
                      {m.status}
                    </Badge>
                  </div>
                );
              })}
            </div>
          </Card>

          {cycle && (
            <Card>
              <CardHeader
                icon={<Syringe className="h-4 w-4" />}
                title="Injection Schedule"
                subtitle="Administration requires payment clearance"
              />
              <div className="stagger space-y-2 px-5 pb-3">
                {(injectionsQuery.data ?? []).length === 0 && (
                  <p className="text-[13.5px] text-ink-500">No injections scheduled yet for this cycle.</p>
                )}
                {(injectionsQuery.data ?? []).map((inj, i) => (
                  <div key={inj.id} style={{ ['--i' as string]: i }} className="flex flex-wrap items-center gap-3 rounded-xl border border-ink-200/70 p-3.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                      <Syringe className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[14.5px] font-semibold text-ink-900">
                        {inj.medicine_name} <span className="tnum font-normal text-ink-500">· {inj.dose}</span>
                      </p>
                      <p className="tnum text-[12.5px] text-ink-500">
                        Scheduled {new Date(inj.scheduled_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })}
                      </p>
                    </div>
                    {inj.status === 'scheduled' ? (
                      <Button
                        size="sm" variant="primary"
                        loading={administerInjection.isPending}
                        onClick={() => administerInjection.mutate(
                          { injectionId: inj.id },
                          {
                            onSuccess: () => toast({ title: 'Injection administered', body: `${inj.medicine_name} recorded.`, tone: 'success' }),
                            onError: (err) => toast({
                              title: err instanceof ApiError && err.errorCode === 'payment_required' ? 'Payment required' : 'Could not administer',
                              body: err instanceof ApiError ? err.message : 'Please try again.',
                              tone: 'error',
                            }),
                          }
                        )}
                      >
                        Mark Administered
                      </Button>
                    ) : (
                      <Badge tone={inj.status === 'administered' ? 'completed' : 'neutral'} size="sm">{inj.status}</Badge>
                    )}
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap items-end gap-2 border-t border-ink-100 px-5 py-4">
                <Input placeholder="Medicine" value={newInjection.medicine_name} onChange={(e) => setNewInjection((f) => ({ ...f, medicine_name: e.target.value }))} className="min-w-[140px] flex-1" />
                <Input placeholder="Dose" value={newInjection.dose} onChange={(e) => setNewInjection((f) => ({ ...f, dose: e.target.value }))} className="w-28" />
                <Input type="datetime-local" value={newInjection.scheduled_at} onChange={(e) => setNewInjection((f) => ({ ...f, scheduled_at: e.target.value }))} className="min-w-[180px]" />
                <Button
                  icon={<Plus className="h-3.5 w-3.5" />}
                  disabled={!newInjection.medicine_name || !newInjection.dose || !newInjection.scheduled_at}
                  loading={scheduleInjection.isPending}
                  onClick={() => scheduleInjection.mutate(
                    { cycle_id: cycle.id, medicine_name: newInjection.medicine_name, dose: newInjection.dose, scheduled_at: new Date(newInjection.scheduled_at).toISOString() },
                    { onSuccess: () => setNewInjection({ medicine_name: '', dose: '', scheduled_at: '' }) }
                  )}
                >
                  Schedule
                </Button>
              </div>
            </Card>
          )}

          {cycle && <CycleTriggerNpoPanel cycleId={cycle.id} />}

          <Card>
            <CardHeader icon={<FlaskConical className="h-4 w-4" />} title="Planned Investigations" subtitle="Baseline workup completed prior to cycle start" />
            <div className="grid gap-2 px-5 pb-5 sm:grid-cols-2">
              {INVESTIGATIONS.slice(0, 6).map((iv) => (
                <div key={iv.name} className="flex items-center justify-between rounded-lg bg-ink-50/70 px-3 py-2">
                  <span className="min-w-0 truncate text-[13.5px] text-ink-700">{iv.name}</span>
                  <Badge tone={iv.flag === 'normal' ? 'completed' : 'attention'} size="sm">
                    {iv.value}
                  </Badge>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* ============ RIGHT RAIL ============ */}
        <div className="space-y-5">
          {canSeeProtocol && (
            <Card>
              <CardHeader
                icon={<Lock className="h-4 w-4" />}
                title="Treatment Protocol"
                subtitle="Restricted — Chief Consultant & Admin only"
                action={
                  !protocolEditing && (
                    <Button size="sm" onClick={() => { setProtocolDraft(protocolQuery.data?.content ?? ''); setProtocolEditing(true); }}>
                      {protocolQuery.data ? 'Edit' : 'Add'}
                    </Button>
                  )
                }
              />
              <div className="px-5 pb-5">
                {protocolEditing ? (
                  <div className="space-y-3">
                    <textarea
                      value={protocolDraft}
                      onChange={(e) => setProtocolDraft(e.target.value)}
                      rows={5}
                      className="w-full rounded-lg border border-ink-200 bg-white p-3 text-[13.5px] text-ink-900"
                      placeholder="Protocol content…"
                    />
                    <div className="flex justify-end gap-2">
                      <Button size="sm" onClick={() => setProtocolEditing(false)}>Cancel</Button>
                      <Button
                        size="sm" variant="primary"
                        loading={saveProtocol.isPending}
                        disabled={!protocolDraft.trim()}
                        onClick={() => saveProtocol.mutate(
                          { cycleId: cycle!.id, content: protocolDraft },
                          {
                            onSuccess: () => { setProtocolEditing(false); toast({ title: 'Protocol saved', body: 'Recorded in the audit trail.', tone: 'success' }); },
                            onError: (err) => toast({ title: 'Could not save', body: err instanceof ApiError ? err.message : 'Please try again.', tone: 'error' }),
                          }
                        )}
                      >
                        Save
                      </Button>
                    </div>
                  </div>
                ) : protocolQuery.data ? (
                  <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-700">{protocolQuery.data.content}</p>
                ) : (
                  <p className="text-[13px] text-ink-500">No protocol recorded yet for this cycle.</p>
                )}
              </div>
            </Card>
          )}

          <Card>
            <CardHeader icon={<ShieldCheck className="h-4 w-4" />} title="Consent Status" />
            <div className="px-5 pb-5">
              {[
                { l: 'IVF treatment consent', d: '12 Jul 2026' },
                { l: 'ICSI procedure consent', d: '12 Jul 2026' },
                { l: 'Cryopreservation consent', d: '3 Aug 2026' },
                { l: 'Anaesthesia consent', d: 'Pending — due before retrieval' },
              ].map((c, i) => {
                const signed = !c.d.includes('Pending');
                return (
                  <div key={c.l} className="flex items-center gap-2.5 border-b border-ink-100 py-2.5 last:border-0">
                    <div
                      className={cn(
                        'flex h-5 w-5 shrink-0 items-center justify-center rounded-full',
                        signed ? 'bg-brand-600' : 'bg-amber-100 ring-1 ring-amber-300'
                      )}
                    >
                      {signed ? <Check className="h-3 w-3 text-white" strokeWidth={3.5} /> : <Circle className="h-2 w-2 text-amber-600" fill="currentColor" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13.5px] font-medium text-ink-800">{c.l}</p>
                      <p className="text-[12px] text-ink-400">{c.d}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card>
            <CardHeader icon={<Receipt className="h-4 w-4" />} title="Package Details" />
            <div className="px-5 pb-5">
              <p className="text-[14.5px] font-semibold text-ink-900">{PACKAGE.name}</p>
              <p className="tnum mt-1 text-[26px] font-semibold text-ink-900">
                {formatINR(PACKAGE.value)}
              </p>
              <div className="mt-3">
                <div className="mb-1.5 flex justify-between text-[12.5px]">
                  <span className="text-ink-500">Collected</span>
                  <span className="tnum font-medium text-ink-800">
                    {formatINR(PACKAGE.paid)} of {formatINR(PACKAGE.value)}
                  </span>
                </div>
                <ProgressBar value={(PACKAGE.paid / PACKAGE.value) * 100} height={7} />
              </div>
              <div className="mt-3">
                <DataRow label="Outstanding" value={formatINR(PACKAGE.outstanding)} tone="attention" />
              </div>
              <Button className="mt-3 w-full" onClick={() => go('billing')}>
                Open billing
              </Button>
            </div>
          </Card>

          <Card>
            <CardHeader icon={<Stethoscope className="h-4 w-4" />} title="Estimated Timeline" />
            <div className="px-5 pb-5">
              {[
                { l: 'Trigger injection', d: '31 Jul 2026' },
                { l: 'Oocyte retrieval', d: '2 Aug 2026' },
                { l: 'Embryo transfer', d: '7 Aug 2026' },
                { l: 'Beta-hCG test', d: '21 Aug 2026' },
              ].map((t) => (
                <DataRow key={t.l} label={t.l} value={t.d} />
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
