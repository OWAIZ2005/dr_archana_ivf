'use client';

import React, { useMemo, useState, useEffect } from 'react';
import { useApp } from '@/lib/store';
import { CRYO_HIERARCHY, PATIENT, EMBRYOS } from '@/lib/data';
import { cn } from '@/lib/utils';
import { Card, CardHeader, Badge, Button, SectionTitle, Field, InfoNote, DataRow, Modal } from '@/components/ui/primitives';
import { useCoupleForPatient, usePatientSummary, useUploadPatientDocument } from '@/lib/api/patients';
import { useActiveCycle } from '@/lib/api/ivf';
import { useEmbryosForCycle } from '@/lib/api/embryology';
import { useCryoLocationsForCycle, useCustodyHistory } from '@/lib/api/cryostorage';
import { SignatureCapture } from '@/components/ui/SignatureCapture';
import { ApiError } from '@/lib/api/client';
import {
  Snowflake,
  ChevronRight,
  ShieldCheck,
  Thermometer,
  CalendarClock,
  History,
  FileSignature,
  Container,
} from 'lucide-react';

/** The actual capture step of "Renew Consent" — a couple's storage consent
 * must be re-signed periodically (see the Next Renewal metric above). Reuses
 * the same PatientDocument/MinIO pipeline every other signature in this app
 * goes through, tagged so it's distinguishable from the original intake
 * consent captured at Registration. */
function RenewConsentModal({ patientId, onClose }: { patientId: string; onClose: () => void }) {
  const { toast } = useApp();
  const upload = useUploadPatientDocument();
  const [signature, setSignature] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    if (!signature) return;
    setError(null);
    upload.mutate(
      { patientId, documentType: 'consent_signature_renewal', file: signature },
      {
        onSuccess: () => { toast({ title: 'Consent renewed', body: 'Storage consent re-signed and filed.', tone: 'success' }); onClose(); },
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not save the renewed consent.'),
      }
    );
  };

  return (
    <Modal
      open onClose={onClose} title="Renew Storage Consent"
      subtitle="Re-signed on this device — finger, stylus or Apple Pencil"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={!signature} loading={upload.isPending} onClick={submit}>
            Save Renewal
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <SignatureCapture idPrefix="cryo-renewal" label="Patient signature" value={signature} onChange={setSignature} />
        {error && <p className="text-[13px] text-rose-600">{error}</p>}
      </div>
    </Modal>
  );
}

function fmtDate(iso: string | null) {
  return iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
}

export function Cryostorage() {
  const { selectedPatientId } = useApp();
  const [renewOpen, setRenewOpen] = useState(false);
  const summaryQuery = usePatientSummary(selectedPatientId);
  const coupleQuery = useCoupleForPatient(selectedPatientId);
  const cycleQuery = useActiveCycle(coupleQuery.data?.id ?? null);
  const embryosQuery = useEmbryosForCycle(cycleQuery.data?.id ?? null);
  const locationsQuery = useCryoLocationsForCycle(cycleQuery.data?.id ?? null);

  const realLocations = locationsQuery.data ?? [];
  const hasRealData = realLocations.length > 0;

  const embryoById = useMemo(() => {
    const map = new Map((embryosQuery.data ?? []).map((e) => [e.id, e]));
    return map;
  }, [embryosQuery.data]);

  const realStraws = useMemo(
    () =>
      realLocations.map((l) => {
        const emb = l.embryo_id ? embryoById.get(l.embryo_id) : undefined;
        return {
          id: l.straw,
          embryo: emb?.label ?? '—',
          embryoId: l.embryo_id,
          grade: emb?.grade ?? '—',
          frozen: fmtDate(l.frozen_at),
          status: l.is_active ? 'Active' : 'Vacated',
          tank: l.tank,
          canister: l.canister,
          cane: l.cane,
          goblet: l.goblet,
          consentVerified: l.consent_verified,
          renewalDue: l.renewal_due,
        };
      }),
    [realLocations, embryoById]
  );

  const straws = hasRealData ? realStraws : CRYO_HIERARCHY.straws.map((s) => ({
    id: s.id, embryo: s.embryo, embryoId: null as string | null, grade: s.grade, frozen: s.frozen, status: s.status,
    tank: CRYO_HIERARCHY.tank, canister: CRYO_HIERARCHY.canister, cane: CRYO_HIERARCHY.cane, goblet: CRYO_HIERARCHY.goblet,
    consentVerified: true, renewalDue: null as string | null,
  }));

  const [selected, setSelected] = useState(straws[0]?.id);
  useEffect(() => {
    if (straws.length && !straws.some((s) => s.id === selected)) setSelected(straws[0].id);
  }, [straws, selected]);

  const straw = straws.find((s) => s.id === selected) ?? straws[0];
  const embryo = EMBRYOS.find((e) => e.id === straw?.embryo);
  const custodyQuery = useCustodyHistory(hasRealData ? straw?.embryoId ?? null : null);
  const patientName = summaryQuery.data?.full_name ?? PATIENT.name;
  const patientUhid = summaryQuery.data?.uhid ?? PATIENT.id;

  if (!straw) {
    return (
      <div className="screen-enter mx-auto max-w-[1300px] space-y-5 p-4 sm:p-6 lg:p-8">
        <SectionTitle eyebrow="Laboratory" title="Cryostorage Management" description="No embryos in storage for this patient yet." />
      </div>
    );
  }

  return (
    <div className="screen-enter mx-auto max-w-[1300px] space-y-5 p-4 sm:p-6 lg:p-8">
      {renewOpen && selectedPatientId && (
        <RenewConsentModal patientId={selectedPatientId} onClose={() => setRenewOpen(false)} />
      )}
      <SectionTitle
        eyebrow="Laboratory"
        title="Cryostorage Management"
        description={`${patientName} · ${straws.length} vitrified blastocyst${straws.length === 1 ? '' : 's'} in long-term storage`}
        action={
          <Button
            variant="primary"
            icon={<FileSignature className="h-4 w-4" />}
            onClick={() => setRenewOpen(true)}
          >
            Renew Consent
          </Button>
        }
      />

      {/* ============ STATUS STRIP ============ */}
      <div className="grid gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { icon: Thermometer, label: 'Tank Temperature', value: CRYO_HIERARCHY.temperature, sub: 'Nominal · logged hourly', tone: 'completed' as const },
          {
            icon: ShieldCheck, label: 'Storage Consent',
            value: straws.every((s) => s.consentVerified) ? 'Verified' : 'Action needed',
            sub: hasRealData ? `${straws.filter((s) => s.consentVerified).length} of ${straws.length} straws verified` : CRYO_HIERARCHY.consent,
            tone: straws.every((s) => s.consentVerified) ? 'completed' as const : 'attention' as const,
          },
          {
            icon: CalendarClock, label: 'Next Renewal',
            value: straw.renewalDue ? fmtDate(straw.renewalDue) : '4 Aug 2027',
            sub: straw.renewalDue
              ? `${Math.max(0, Math.round((new Date(straw.renewalDue).getTime() - Date.now()) / 86400000))} days remaining`
              : '371 days remaining',
            tone: 'pending' as const,
          },
          {
            icon: Snowflake, label: 'Stored Embryos',
            value: `${straws.length} straw${straws.length === 1 ? '' : 's'}`,
            sub: `Grades ${straws.map((s) => s.grade).join(', ')}`,
            tone: 'active' as const,
          },
        ].map((s, i) => {
          const Icon = s.icon;
          return (
            <Card key={s.label} className="p-4" style={{ ['--i' as string]: i }}>
              <div className="flex items-start justify-between">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-50 text-sky-700 ring-1 ring-inset ring-sky-600/12">
                  <Icon className="h-[18px] w-[18px]" />
                </div>
                <Badge tone={s.tone} size="sm" dot={false}>
                  OK
                </Badge>
              </div>
              <p className="mt-3 text-[12px] font-medium uppercase tracking-[0.06em] text-ink-400">
                {s.label}
              </p>
              <p className="tnum mt-1 text-[18px] font-semibold text-ink-900">{s.value}</p>
              <p className="mt-0.5 text-[12px] text-ink-500">{s.sub}</p>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* ============ HIERARCHY ============ */}
        <Card className="lg:col-span-2">
          <CardHeader
            icon={<Container className="h-4 w-4" />}
            title="Storage Location Hierarchy"
            subtitle="Physical chain from dewar to individual straw"
          />

          <div className="px-5 pb-5">
            {/* breadcrumb hierarchy */}
            <div className="flex flex-wrap items-center gap-2">
              {[
                { key: 'tank', label: 'Tank', value: straw.tank, sub: 'Liquid nitrogen dewar' },
                { key: 'canister', label: 'Canister', value: straw.canister, sub: 'Of 6 canisters' },
                { key: 'cane', label: 'Cane', value: straw.cane, sub: 'Of 10 canes' },
                { key: 'goblet', label: 'Goblet', value: straw.goblet, sub: 'Of 8 goblets' },
              ].map((l, i, arr) => (
                <React.Fragment key={l.key}>
                  <div
                    className="animate-fade-up rounded-xl border border-sky-200/70 bg-gradient-to-b from-sky-50/80 to-white px-3.5 py-2.5"
                    style={{ animationDelay: `${i * 90}ms` }}
                  >
                    <p className="text-[11.5px] font-semibold uppercase tracking-[0.08em] text-sky-600">
                      {l.label}
                    </p>
                    <p className="tnum mt-0.5 text-[14px] font-semibold text-ink-900">{l.value}</p>
                    <p className="text-[11.5px] text-ink-400">{l.sub}</p>
                  </div>
                  {i < arr.length - 1 && <ChevronRight className="h-4 w-4 shrink-0 text-ink-300" />}
                </React.Fragment>
              ))}
            </div>

            {/* straws */}
            <div className="mt-5">
              <p className="mb-2.5 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-500">
                Straws in {straw.goblet}
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {straws.map((s, i) => {
                  const active = selected === s.id;
                  return (
                    <button
                      key={s.id}
                      onClick={() => setSelected(s.id)}
                      className={cn(
                        'lift group relative overflow-hidden rounded-xl border p-4 text-left transition-all',
                        active
                          ? 'border-sky-400 bg-sky-50/60 shadow-lift ring-1 ring-sky-500/20'
                          : 'border-ink-200/70 bg-white hover:border-sky-300'
                      )}
                    >
                      {/* frosted straw graphic */}
                      <div className="flex items-center gap-3">
                        <div className="relative flex h-16 w-6 flex-col overflow-hidden rounded-full border border-sky-200 bg-gradient-to-b from-white via-sky-50 to-sky-100">
                          <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-sky-300/70 to-transparent" />
                          <Snowflake className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 text-sky-500" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="tnum text-[14px] font-semibold text-ink-900">{s.id}</p>
                          <p className="tnum text-[13px] text-ink-600">
                            Embryo {s.embryo} · Grade {s.grade}
                          </p>
                          <p className="mt-1 text-[12px] text-ink-400">Frozen {s.frozen}</p>
                          <Badge tone="completed" size="sm" className="mt-1.5">
                            {s.status}
                          </Badge>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* selected detail */}
            <div className="mt-5 rounded-xl border border-ink-200/70 bg-ink-50/50 p-4">
              <p className="mb-3 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-500">
                Selected item detail
              </p>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Stored Item" value={`Embryo ${straw.embryo}`} />
                <Field label="Patient" value={patientName} />
                <Field label="Patient ID" value={patientUhid} mono />
                <Field label="Grade" value={straw.grade} mono />
                <Field label="Freeze Date" value={straw.frozen} />
                <Field label="Storage Status" value={straw.status} />
                <Field
                  label="Full Location"
                  value={`${straw.tank} / ${straw.canister} / ${straw.cane} / ${straw.goblet} / ${straw.id}`}
                  className="sm:col-span-2"
                />
                <Field label="Next Renewal" value={straw.renewalDue ? fmtDate(straw.renewalDue) : CRYO_HIERARCHY.renewal} />
              </div>
              {(() => {
                const realNote = hasRealData && straw.embryoId ? embryoById.get(straw.embryoId)?.embryologist_notes : null;
                const note = realNote ?? embryo?.note;
                return note ? (
                  <p className="mt-3 border-l-2 border-sky-300 pl-3 text-[13.5px] leading-relaxed text-ink-600">
                    {note}
                  </p>
                ) : null;
              })()}
            </div>
          </div>
        </Card>

        {/* ============ CHAIN OF CUSTODY ============ */}
        <Card>
          <CardHeader
            icon={<History className="h-4 w-4" />}
            title="Chain of Custody"
            subtitle="Every handling event is witnessed and logged"
          />
          <div className="stagger px-5 pb-5">
            {(() => {
              const realEvents = hasRealData ? custodyQuery.data ?? [] : [];
              const custody = realEvents.length
                ? realEvents.map((e) => ({
                    event: e.notes || e.event_type.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()),
                    at: new Date(e.occurred_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }),
                    by: null as string | null,
                  }))
                : CRYO_HIERARCHY.custody.map((c) => ({ event: c.event, at: c.at, by: c.by as string | null }));
              if (hasRealData && custodyQuery.isLoading) {
                return <p className="text-[13.5px] text-ink-400">Loading custody history…</p>;
              }
              if (hasRealData && custody.length === 0) {
                return <p className="text-[13.5px] text-ink-400">No custody events recorded for this straw yet.</p>;
              }
              return custody.map((c, i) => (
                <div key={i} style={{ ['--i' as string]: i }} className="relative flex gap-3 pb-4 last:pb-0">
                  {i < custody.length - 1 && <span className="absolute left-[11px] top-6 h-full w-px bg-ink-200" />}
                  <div className="relative z-10 mt-1 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full bg-sky-50 ring-1 ring-sky-200">
                    <span className="h-1.5 w-1.5 rounded-full bg-sky-500" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13.5px] leading-snug text-ink-800">{c.event}</p>
                    <p className="mt-0.5 text-[12px] text-ink-400">
                      <span className="tnum">{c.at}</span>
                      {c.by && <> · {c.by}</>}
                    </p>
                  </div>
                </div>
              ));
            })()}
          </div>

          <div className="border-t border-ink-100 p-5">
            <InfoNote tone="brand" icon={<ShieldCheck className="h-4 w-4" />}>
              Storage consent verified and on file. Automated renewal reminders are issued to the
              couple 60 days before expiry.
            </InfoNote>
          </div>
        </Card>
      </div>
    </div>
  );
}
