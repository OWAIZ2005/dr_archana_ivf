'use client';

import React, { useState } from 'react';
import { useApp } from '@/lib/store';
import { useAuth } from '@/lib/auth';
import { TRANSFER_CHECKLIST, EMBRYOS, PATIENT, PARTNER } from '@/lib/data';
import { cn } from '@/lib/utils';
import { Card, CardHeader, Badge, Button, SectionTitle, Field, InfoNote, Modal } from '@/components/ui/primitives';
import { useCoupleForPatient, usePatientSummary, useUploadPatientDocument } from '@/lib/api/patients';
import { SignatureCapture } from '@/components/ui/SignatureCapture';
import { useActiveCycle } from '@/lib/api/ivf';
import { useEmbryosForCycle } from '@/lib/api/embryology';
import {
  useTransferForCycle,
  useInitiateTransfer,
  useCheckTransferItem,
  useCompleteTransfer,
} from '@/lib/api/cryostorage';
import { useDoctors, useEmbryologists } from '@/lib/api/users';
import { ApiError } from '@/lib/api/client';
import {
  Check,
  ShieldCheck,
  Baby,
  Stethoscope,
  FileSignature,
  AlertTriangle,
  ArrowRight,
  Sparkles,
} from 'lucide-react';

export function Transfer() {
  const { go, toast, completeTransfer, transferComplete, selectedPatientId } = useApp();
  const { user: authUser } = useAuth();
  const [checked, setChecked] = useState<string[]>([]);
  const [confirm, setConfirm] = useState(false);
  const [running, setRunning] = useState(false);
  const [witnessClinicianSig, setWitnessClinicianSig] = useState<File | null>(null);
  const [witnessEmbryologistSig, setWitnessEmbryologistSig] = useState<File | null>(null);
  const uploadSignature = useUploadPatientDocument();

  const summaryQuery = usePatientSummary(selectedPatientId);
  const coupleQuery = useCoupleForPatient(selectedPatientId);
  const cycleQuery = useActiveCycle(coupleQuery.data?.id ?? null);
  const embryosQuery = useEmbryosForCycle(cycleQuery.data?.id ?? null);
  const transferQuery = useTransferForCycle(cycleQuery.data?.id ?? null);
  const doctorsQuery = useDoctors();
  const embryologistsQuery = useEmbryologists();
  const initiateTransfer = useInitiateTransfer();
  const checkItem = useCheckTransferItem();
  const completeTransferMutation = useCompleteTransfer();

  const selectedEmbryo = (embryosQuery.data ?? []).find((e) => e.status === 'selected_for_transfer') ?? null;
  const hasRealData = !!cycleQuery.data && !!selectedEmbryo;
  const realTransfer = transferQuery.data ?? null;

  const embryo = hasRealData
    ? {
        id: selectedEmbryo!.label, day: selectedEmbryo!.day, grade: selectedEmbryo!.grade,
        expansion: selectedEmbryo!.expansion ?? '—', icm: selectedEmbryo!.icm_grade ?? '—',
        trophectoderm: selectedEmbryo!.trophectoderm_grade ?? '—',
      }
    : EMBRYOS.find((e) => e.id === 'E-01')!;

  const patientName = summaryQuery.data?.full_name ?? PATIENT.name;
  const patientUhid = summaryQuery.data?.uhid ?? PATIENT.id;
  const realPartner = coupleQuery.data
    ? coupleQuery.data.female_patient.id === selectedPatientId ? coupleQuery.data.male_patient : coupleQuery.data.female_patient
    : null;
  const partnerName = realPartner?.full_name ?? PARTNER.name;
  const partnerUhid = realPartner?.uhid ?? PARTNER.id;

  const allChecked = hasRealData
    ? realTransfer
      ? realTransfer.checklist.every((c) => c.checked)
      : false
    : checked.length === TRANSFER_CHECKLIST.length;
  const isComplete = hasRealData ? !!realTransfer?.completed : transferComplete;

  const toggle = (id: string) => {
    if (hasRealData) {
      // Real checklist items pass their real item_code as `id` (see the
      // `items` view-model built below) — no lookup needed, unlike the
      // static fixture's arbitrary c1..c6 ids.
      if (!realTransfer || realTransfer.completed) return;
      const item = realTransfer.checklist.find((c) => c.item_code === id);
      if (item && !item.checked) {
        checkItem.mutate({ transferId: realTransfer.id, itemCode: item.item_code });
      }
      return;
    }
    setChecked((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  };

  const checkAll = () => {
    if (hasRealData) return; // real checks are one-by-one, audited — no bulk shortcut
    setChecked(TRANSFER_CHECKLIST.map((c) => c.id));
  };

  const beginTransfer = () => {
    if (!cycleQuery.data || !selectedEmbryo) return;
    const doctorId = authUser?.role_code === 'doctor' ? authUser.id : doctorsQuery.data?.[0]?.id;
    const embryologistId = authUser?.role_code === 'embryologist' ? authUser.id : embryologistsQuery.data?.[0]?.id;
    if (!doctorId || !embryologistId) {
      toast({ title: 'Cannot start transfer', body: 'No doctor or embryologist on record to assign.', tone: 'error' });
      return;
    }
    initiateTransfer.mutate(
      {
        cycle_id: cycleQuery.data.id, embryo_id: selectedEmbryo.id,
        procedure_doctor_id: doctorId, embryologist_id: embryologistId,
        transfer_date: new Date().toISOString().slice(0, 10),
      },
      { onError: (err) => toast({ title: 'Could not start transfer', body: err instanceof ApiError ? err.message : 'Please try again.', tone: 'error' }) }
    );
  };

  const runTransfer = () => {
    if (hasRealData && realTransfer) {
      setRunning(true);
      completeTransferMutation.mutate(realTransfer.id, {
        onSuccess: async () => {
          // The transfer itself is already recorded at this point — a
          // signature-upload failure is surfaced as a non-fatal warning
          // (same pattern as the registration-photo upload) rather than
          // rolling back or blocking a procedure that has already happened.
          const failed: string[] = [];
          if (selectedPatientId && witnessClinicianSig) {
            try {
              await uploadSignature.mutateAsync({ patientId: selectedPatientId, documentType: 'consent_signature_witness_clinician', file: witnessClinicianSig });
            } catch {
              failed.push('clinician');
            }
          }
          if (selectedPatientId && witnessEmbryologistSig) {
            try {
              await uploadSignature.mutateAsync({ patientId: selectedPatientId, documentType: 'consent_signature_witness_embryologist', file: witnessEmbryologistSig });
            } catch {
              failed.push('embryologist');
            }
          }
          setRunning(false);
          setConfirm(false);
          toast({
            title: 'Embryo transfer completed',
            body: failed.length
              ? `Procedure recorded. The ${failed.join(' and ')} witness signature could not be saved — capture it again from the patient profile.`
              : 'Procedure recorded. Luteal support prescribed.',
            tone: failed.length ? 'warning' : 'success',
          });
          setTimeout(() => go('pregnancy'), 900);
        },
        onError: (err) => {
          setRunning(false);
          toast({ title: 'Could not complete transfer', body: err instanceof ApiError ? err.message : 'Please try again.', tone: 'error' });
        },
      });
      return;
    }
    setRunning(true);
    setTimeout(() => {
      setRunning(false);
      setConfirm(false);
      completeTransfer();
      toast({
        title: 'Embryo transfer completed',
        body: 'Procedure recorded. Luteal support prescribed. Beta-hCG scheduled for 21 August 2026.',
        tone: 'success',
      });
      setTimeout(() => go('pregnancy'), 900);
    }, 1900);
  };

  return (
    <div className="screen-enter mx-auto max-w-[1200px] space-y-5 p-4 sm:p-6 lg:p-8">
      <SectionTitle
        eyebrow="Procedure"
        title="Embryo Transfer"
        description={
          hasRealData && realTransfer
            ? `${patientName} · Transfer date ${new Date(realTransfer.transfer_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })} · Ultrasound-guided single blastocyst transfer`
            : `${patientName} · Transfer date 7 August 2026 · Ultrasound-guided single blastocyst transfer`
        }
        action={
          isComplete ? (
            <Badge tone="completed">Transfer completed</Badge>
          ) : (
            <Badge tone="scheduled">Awaiting sign-off</Badge>
          )
        }
      />

      <div className="grid gap-5 lg:grid-cols-3">
        {/* ============ SELECTED EMBRYO ============ */}
        <Card className="overflow-hidden">
          <div className="bg-gradient-to-br from-brand-600 to-brand-800 p-5 text-white">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-200" />
              <span className="text-[12px] font-semibold uppercase tracking-[0.1em] text-brand-200">
                Selected Embryo
              </span>
            </div>
            <p className="tnum tracking-display mt-2 text-[38px] font-semibold leading-none">
              {embryo.id}
            </p>
            <div className="mt-3 flex items-center gap-3">
              <span className="tnum rounded-lg bg-white/15 px-2.5 py-1 text-[14px] font-bold ring-1 ring-inset ring-white/20">
                Grade {embryo.grade}
              </span>
              <span className="text-[14px] text-brand-100">Day {embryo.day} blastocyst</span>
            </div>
          </div>

          <div className="p-5">
            <Field label="Expansion" value={embryo.expansion} />
            <div className="mt-3.5">
              <Field label="Inner Cell Mass" value={embryo.icm} />
            </div>
            <div className="mt-3.5">
              <Field label="Trophectoderm" value={embryo.trophectoderm} />
            </div>
            <div className="mt-3.5">
              <Field label="Number of Embryos" value="1 — elective single transfer" />
            </div>
            <div className="mt-3.5">
              <Field
                label="Procedure Doctor"
                value={
                  hasRealData
                    ? (authUser?.role_code === 'doctor' ? authUser.full_name : doctorsQuery.data?.[0]?.full_name) ?? 'Dr. Archana S. Ayyanathan'
                    : 'Dr. Archana S. Ayyanathan'
                }
              />
            </div>
            <div className="mt-3.5">
              <Field
                label="Embryologist"
                value={
                  hasRealData
                    ? (authUser?.role_code === 'embryologist' ? authUser.full_name : embryologistsQuery.data?.[0]?.full_name) ?? 'Dr. Meera Kapoor'
                    : 'Dr. Meera Kapoor'
                }
              />
            </div>

            <div className="mt-4">
              <InfoNote tone="brand" icon={<ShieldCheck className="h-4 w-4" />}>
                Consent verified — signed by both partners on 6 August 2026.
              </InfoNote>
            </div>
          </div>
        </Card>

        {/* ============ CHECKLIST ============ */}
        <Card className="lg:col-span-2">
          <CardHeader
            icon={<ShieldCheck className="h-4 w-4" />}
            title="Pre-Transfer Safety Verification"
            subtitle="All six checks must be confirmed before the procedure can proceed"
            action={
              !hasRealData &&
              !allChecked &&
              !isComplete && (
                <Button size="sm" variant="ghost" onClick={checkAll}>
                  Verify all
                </Button>
              )
            }
          />

          {hasRealData && !realTransfer ? (
            <div className="px-5 pb-5">
              <InfoNote tone="brand" icon={<Sparkles className="h-4 w-4" />}>
                No transfer has been started for this cycle yet. Beginning the workflow creates the
                6-point checklist below, each item audited as it's confirmed.
              </InfoNote>
              <Button
                variant="primary"
                className="mt-4 w-full"
                loading={initiateTransfer.isPending}
                icon={<ShieldCheck className="h-4 w-4" />}
                onClick={beginTransfer}
              >
                {initiateTransfer.isPending ? 'Starting…' : 'Begin Transfer Verification'}
              </Button>
            </div>
          ) : (
            <>
              <div className="px-5">
                {/* progress */}
                {(() => {
                  const items = hasRealData && realTransfer
                    ? realTransfer.checklist.map((c) => ({ id: c.item_code, label: c.label, detail: TRANSFER_CHECKLIST.find((t) => t.label === c.label)?.detail ?? '', on: c.checked }))
                    : TRANSFER_CHECKLIST.map((c) => ({ id: c.id, label: c.label, detail: c.detail, on: checked.includes(c.id) || isComplete }));
                  const doneCount = items.filter((i) => i.on).length;
                  return (
                    <>
                      <div className="mb-4 flex items-center gap-3 rounded-xl bg-ink-50 p-3">
                        <div className="flex-1">
                          <div className="mb-1.5 flex justify-between text-[12.5px]">
                            <span className="font-medium text-ink-600">Verification progress</span>
                            <span className="tnum font-semibold text-ink-900">
                              {doneCount} of {items.length}
                            </span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-ink-200">
                            <div
                              className={cn(
                                'h-full rounded-full transition-[width] duration-500 ease-spring',
                                allChecked ? 'bg-gradient-to-r from-brand-400 to-brand-600' : 'bg-gradient-to-r from-amber-400 to-amber-500'
                              )}
                              style={{ width: `${(doneCount / items.length) * 100}%` }}
                            />
                          </div>
                        </div>
                        {allChecked && (
                          <Badge tone="completed" className="animate-scale-in">
                            Ready
                          </Badge>
                        )}
                      </div>

                      {/* items */}
                      <div className="stagger space-y-2 pb-5">
                        {items.map((c, i) => (
                          <button
                            key={c.id}
                            disabled={isComplete || (hasRealData && c.on)}
                            onClick={() => toggle(c.id)}
                            style={{ ['--i' as string]: i }}
                            className={cn(
                              'flex w-full items-start gap-3.5 rounded-xl border p-3.5 text-left transition-all duration-250',
                              c.on
                                ? 'border-brand-300 bg-brand-50/50'
                                : 'border-ink-200/70 bg-white hover:border-ink-300 hover:bg-ink-50/60'
                            )}
                          >
                            <div
                              className={cn(
                                'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition-all duration-250',
                                c.on ? 'border-brand-600 bg-brand-600' : 'border-ink-300 bg-white'
                              )}
                            >
                              {c.on && (
                                <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="white" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                                  <path d="M20 6L9 17l-5-5" className="tick-path" />
                                </svg>
                              )}
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className={cn('text-[14.5px] font-medium', c.on ? 'text-brand-900' : 'text-ink-800')}>
                                {c.label}
                              </p>
                              {c.detail && <p className="mt-0.5 text-[13px] leading-relaxed text-ink-500">{c.detail}</p>}
                            </div>
                            {c.on && <Check className="mt-1 h-4 w-4 shrink-0 text-brand-600" />}
                          </button>
                        ))}
                      </div>
                    </>
                  );
                })()}
              </div>

          <div className="border-t border-ink-100 bg-ink-50/50 p-5">
            {!allChecked && !isComplete && (
              <InfoNote tone="amber" icon={<AlertTriangle className="h-4 w-4" />}>
                Complete every verification step before proceeding. This checklist forms part of the
                permanent medical record and is auditable.
              </InfoNote>
            )}

            {isComplete ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600">
                    <Check className="h-5 w-5 text-white" strokeWidth={3} />
                  </div>
                  <div>
                    <p className="text-[14.5px] font-semibold text-ink-900">Transfer completed</p>
                    <p className="text-[13px] text-ink-500">
                      {hasRealData && realTransfer
                        ? `Recorded for ${new Date(realTransfer.transfer_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}`
                        : 'Recorded 7 August 2026, 11:42 AM'}
                    </p>
                  </div>
                </div>
                <Button variant="primary" iconRight={<ArrowRight className="h-4 w-4" />} onClick={() => go('pregnancy')}>
                  View Pregnancy Follow-up
                </Button>
              </div>
            ) : (
              <Button
                variant="primary"
                size="lg"
                className="mt-4 w-full"
                disabled={!allChecked}
                icon={<Baby className="h-4 w-4" />}
                onClick={() => setConfirm(true)}
              >
                Complete Embryo Transfer
              </Button>
            )}
          </div>
            </>
          )}
        </Card>
      </div>

      {/* ============ CONFIRM MODAL ============ */}
      <Modal
        open={confirm}
        onClose={() => !running && setConfirm(false)}
        title="Confirm embryo transfer"
        subtitle="This action is final and will be recorded in the permanent medical record."
        footer={
          <>
            <Button onClick={() => { setConfirm(false); setWitnessClinicianSig(null); setWitnessEmbryologistSig(null); }} disabled={running}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={running}
              disabled={hasRealData && (!witnessClinicianSig || !witnessEmbryologistSig)}
              icon={<Check className="h-4 w-4" />}
              onClick={runTransfer}
            >
              {running ? 'Recording procedure…' : 'Confirm & Complete'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="rounded-xl border border-brand-200 bg-brand-50/60 p-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Patient" value={`${patientName} — ${patientUhid}`} />
              <Field label="Partner" value={`${partnerName} — ${partnerUhid}`} />
              <Field label="Embryo" value={`${embryo.id} · Day ${embryo.day} · Grade ${embryo.grade}`} />
              <Field
                label="Procedure Date"
                value={hasRealData && realTransfer ? new Date(realTransfer.transfer_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' }) : '7 August 2026'}
              />
              <Field
                label="Clinician"
                value={hasRealData ? (authUser?.role_code === 'doctor' ? authUser.full_name : doctorsQuery.data?.[0]?.full_name) ?? 'Dr. Archana S. Ayyanathan' : 'Dr. Archana S. Ayyanathan'}
              />
              <Field
                label="Embryologist"
                value={hasRealData ? (authUser?.role_code === 'embryologist' ? authUser.full_name : embryologistsQuery.data?.[0]?.full_name) ?? 'Dr. Meera Kapoor' : 'Dr. Meera Kapoor'}
              />
            </div>
          </div>

          <InfoNote tone="neutral" icon={<FileSignature className="h-4 w-4" />}>
            All six safety verifications have been confirmed. Capture the double-witness signature
            below to complete the procedure — it is written to the audit trail with a timestamp.
          </InfoNote>

          <div className="grid gap-3 sm:grid-cols-2">
            <SignatureCapture
              idPrefix="transfer-witness-clinician"
              label="Witness — Clinician"
              value={witnessClinicianSig}
              onChange={setWitnessClinicianSig}
            />
            <SignatureCapture
              idPrefix="transfer-witness-embryologist"
              label="Witness — Embryologist"
              value={witnessEmbryologistSig}
              onChange={setWitnessEmbryologistSig}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
