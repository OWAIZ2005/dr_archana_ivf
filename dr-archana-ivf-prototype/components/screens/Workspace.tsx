'use client';

import React, { useMemo, useState } from 'react';
import { useApp } from '@/lib/store';
import {
  PATIENT,
  PARTNER,
  MONITORING_HISTORY,
  INVESTIGATIONS,
  CONSULTATIONS,
  MEDICATIONS,
  PACKAGE,
  TIMELINE,
  type StatusTone,
} from '@/lib/data';
import { usePatientSummary, useCoupleForPatient, usePatientDocuments } from '@/lib/api/patients';
import { usePatientConsultations } from '@/lib/api/clinical';
import { useLabOrders, type LabOrderStatus } from '@/lib/api/laboratory';
import { useActiveCycle } from '@/lib/api/ivf';
import { useInvoices } from '@/lib/api/billing';
import { usePrescriptions, useCreatePrescription, openPrescriptionPdf, type PrescriptionLineCreate } from '@/lib/api/prescription';
import { useConsentForms, useCreateConsentForm, useSignConsentForm, useMRDRecords, useCreateMRDRecord } from '@/lib/api/clinicalDocuments';
import { useNursingRecords, useCreateNursingRecord } from '@/lib/api/nursing';
import { usePatientAppointments } from '@/lib/api/appointments';
import { ApiError } from '@/lib/api/client';
import { cn, TONE, formatINR, ageFromDOB, initialsOf } from '@/lib/utils';
import {
  Card,
  CardHeader,
  Badge,
  Button,
  Avatar,
  Tabs,
  Field,
  DataRow,
  InfoNote,
  ProgressBar,
  ActionRow,
  Modal,
  Input,
  Select,
} from '@/components/ui/primitives';
import { GrowthChart } from '@/components/ui/charts';
import {
  Heart,
  Link2,
  Phone,
  Mail,
  MapPin,
  Droplet,
  AlertCircle,
  Activity,
  ClipboardList,
  FileText,
  Receipt,
  Pill,
  FlaskConical,
  Stethoscope,
  CalendarPlus,
  ChevronRight,
  Printer,
  ShieldCheck,
  TrendingUp,
  FolderOpen,
  Download,
  Plus,
  Trash2,
  PenLine,
} from 'lucide-react';

const STATIC_DOCUMENTS = [
  { name: 'IVF Treatment Consent', date: '12 Jul 2026', size: '284 KB', signed: true },
  { name: 'ICSI Procedure Consent', date: '12 Jul 2026', size: '196 KB', signed: true },
  { name: 'Cryopreservation Consent', date: '3 Aug 2026', size: '212 KB', signed: true },
  { name: 'Baseline Ultrasound Report', date: '22 Jul 2026', size: '1.2 MB', signed: false },
  { name: 'Hormonal Profile — Lab', date: '6 Jul 2026', size: '486 KB', signed: false },
  { name: 'Semen Analysis Report', date: '9 Jul 2026', size: '318 KB', signed: false },
];

const LAB_STATUS_LABEL: Record<LabOrderStatus, string> = {
  ordered: 'Ordered',
  sample_collected: 'Sample Collected',
  in_progress: 'In Progress',
  report_ready: 'Report Ready',
  delivered: 'Delivered',
};
const LAB_STATUS_TONE: Record<LabOrderStatus, keyof typeof TONE> = {
  ordered: 'scheduled',
  sample_collected: 'attention',
  in_progress: 'active',
  report_ready: 'completed',
  delivered: 'neutral',
};


/* ============================================================
   PATIENT HEADER — used across clinical screens (Workspace,
   Timeline, Monitoring, Plan). Reads whichever patient was last
   opened via useApp().openPatient — the old build's single
   hardcoded PATIENT constant is now only a fallback for the
   seeded demo record, matched by uhid, purely for visual
   continuity of that one demo story.
   ============================================================ */
export function PatientHeader({ compact }: { compact?: boolean }) {
  const { go, openPatient, selectedPatientId } = useApp();
  const summaryQuery = usePatientSummary(selectedPatientId);
  const coupleQuery = useCoupleForPatient(selectedPatientId);

  if (!selectedPatientId) {
    return (
      <Card className="flex flex-col items-center gap-3 p-8 text-center">
        <p className="text-[14.5px] font-medium text-ink-700">No patient selected</p>
        <p className="text-[13.5px] text-ink-500">Open a patient from the registry to view their chart.</p>
        <Button size="sm" onClick={() => go('patients')}>Go to Patient Registry</Button>
      </Card>
    );
  }

  if (summaryQuery.isLoading || !summaryQuery.data) {
    return (
      <Card className="p-5">
        <div className="flex items-center gap-5">
          <div className="h-16 w-16 animate-pulse rounded-full bg-ink-100" />
          <div className="flex-1 space-y-2">
            <div className="h-5 w-48 animate-pulse rounded bg-ink-100" />
            <div className="h-3.5 w-64 animate-pulse rounded bg-ink-100" />
          </div>
        </div>
      </Card>
    );
  }

  const summary = summaryQuery.data;
  const isDemoPatient = summary.uhid === PATIENT.id;
  const couple = coupleQuery.data;
  const partner = couple
    ? couple.female_patient.id === selectedPatientId
      ? couple.male_patient
      : couple.female_patient
    : null;
  const age = ageFromDOB(summary.date_of_birth);

  return (
    <Card className="overflow-hidden">
      <div className="relative">
        {/* accent wash */}
        <div className="absolute inset-x-0 top-0 h-[76px] bg-gradient-to-r from-brand-50 via-emerald-50/60 to-transparent" />

        <div className="relative flex flex-wrap items-start gap-5 p-5">
          <div className="relative">
            <Avatar initials={initialsOf(summary.full_name)} size="xl" gradient="from-brand-500 to-teal-600" ring />
            <span className="absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 ring-2 ring-white">
              <Activity className="h-2.5 w-2.5 text-white" strokeWidth={3} />
            </span>
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="tracking-display text-[20px] font-semibold text-ink-900 sm:text-[24px]">{summary.full_name}</h1>
              <Badge tone="active" wrap className="max-w-full">
                {isDemoPatient ? `Active IVF Cycle — Stimulation Day ${PATIENT.cycleDay}` : 'Patient Chart'}
              </Badge>
            </div>

            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13.5px] text-ink-500">
              <span className="tnum font-medium text-ink-700">{summary.uhid}</span>
              {age !== null && <span>{age} years</span>}
              {summary.blood_group && (
                <span className="flex items-center gap-1">
                  <Droplet className="h-3 w-3 text-rose-500" /> {summary.blood_group}
                </span>
              )}
              {summary.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="h-3 w-3" /> {summary.phone}
                </span>
              )}
            </div>

            {/* Couple linkage — deliberately prominent. Each partner is still an
                individual patient record; this only navigates between them. */}
            {partner && (
              <div className="mt-3.5 inline-flex flex-wrap items-center gap-3 rounded-xl border border-brand-200/70 bg-brand-50/60 py-2 pl-2 pr-3">
                <Avatar initials={initialsOf(partner.full_name)} size="sm" gradient="from-sky-500 to-blue-600" />
                <div>
                  <div className="flex items-center gap-1.5">
                    <Link2 className="h-3 w-3 text-brand-600" />
                    <span className="text-[12px] font-semibold uppercase tracking-[0.08em] text-brand-700">
                      Linked Partner
                    </span>
                  </div>
                  <p className="mt-0.5 text-[14px] font-medium text-ink-900">
                    {partner.full_name}
                    {ageFromDOB(partner.date_of_birth) !== null && ` · ${ageFromDOB(partner.date_of_birth)} yrs`}
                    <span className="tnum ml-2 text-[12.5px] font-normal text-ink-500">{partner.uhid}</span>
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  iconRight={<ChevronRight className="h-3.5 w-3.5" />}
                  onClick={() => openPatient(partner.id)}
                >
                  View Partner
                </Button>
              </div>
            )}
          </div>

          <div className="flex shrink-0 flex-col gap-2">
            <Button variant="primary" size="sm" icon={<Activity className="h-4 w-4" />} onClick={() => go('monitoring')}>
              Review Monitoring
            </Button>
            <Button size="sm" icon={<CalendarPlus className="h-4 w-4" />} onClick={() => go('timeline')}>
              View Timeline
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}

/* ============================================================
   WRITE PRESCRIPTION MODAL
   ============================================================ */
function WritePrescriptionModal({ patientId, open, onClose }: { patientId: string | null; open: boolean; onClose: () => void }) {
  const [category, setCategory] = useState('');
  const [notes, setNotes] = useState('');
  const [lines, setLines] = useState<PrescriptionLineCreate[]>([
    { medicine_name: '', dosage: '', frequency: '', timing: '', duration: '', instructions: '' },
  ]);
  const createPrescription = useCreatePrescription();

  const updateLine = (i: number, patch: Partial<PrescriptionLineCreate>) =>
    setLines((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));

  const reset = () => {
    setCategory('');
    setNotes('');
    setLines([{ medicine_name: '', dosage: '', frequency: '', timing: '', duration: '', instructions: '' }]);
    createPrescription.reset();
  };

  const canSubmit = !!patientId && lines.every((l) => l.medicine_name.trim() && l.dosage.trim() && l.frequency.trim());

  return (
    <Modal
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="Write Prescription"
      subtitle="Add one or more medicine lines for this patient"
      width="max-w-2xl"
      footer={
        <div className="flex items-center justify-between gap-3">
          {createPrescription.isError && (
            <p className="text-[13px] text-rose-600">
              {createPrescription.error instanceof ApiError ? createPrescription.error.message : 'Failed to save prescription.'}
            </p>
          )}
          <div className="ml-auto flex gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                reset();
                onClose();
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={!canSubmit || createPrescription.isPending}
              loading={createPrescription.isPending}
              onClick={() => {
                if (!patientId) return;
                createPrescription.mutate(
                  { patient_id: patientId, category: category.trim() || null, notes: notes.trim() || null, lines },
                  {
                    onSuccess: () => {
                      reset();
                      onClose();
                    },
                  }
                );
              }}
            >
              Save Prescription
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Input label="Category (optional)" placeholder="e.g. Stimulation, Luteal support" value={category} onChange={(e) => setCategory(e.target.value)} />

        <div className="space-y-3">
          {lines.map((l, i) => (
            <div key={i} className="rounded-xl border border-ink-200 p-3">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-[12.5px] font-semibold uppercase tracking-[0.06em] text-ink-400">Medicine {i + 1}</p>
                {lines.length > 1 && (
                  <button
                    className="text-ink-400 hover:text-rose-600"
                    onClick={() => setLines((ls) => ls.filter((_, idx) => idx !== i))}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Input label="Medicine name" value={l.medicine_name} onChange={(e) => updateLine(i, { medicine_name: e.target.value })} />
                <Input label="Dosage" placeholder="e.g. 250 IU" value={l.dosage} onChange={(e) => updateLine(i, { dosage: e.target.value })} />
                <Input label="Frequency" placeholder="e.g. Once daily" value={l.frequency} onChange={(e) => updateLine(i, { frequency: e.target.value })} />
                <Input label="Timing (optional)" placeholder="e.g. Morning" value={l.timing ?? ''} onChange={(e) => updateLine(i, { timing: e.target.value })} />
                <Input label="Duration (optional)" placeholder="e.g. 10 days" value={l.duration ?? ''} onChange={(e) => updateLine(i, { duration: e.target.value })} />
                <Input label="Instructions (optional)" placeholder="e.g. Subcutaneous" value={l.instructions ?? ''} onChange={(e) => updateLine(i, { instructions: e.target.value })} />
              </div>
            </div>
          ))}
        </div>

        <Button
          size="sm"
          icon={<Plus className="h-4 w-4" />}
          onClick={() => setLines((ls) => [...ls, { medicine_name: '', dosage: '', frequency: '', timing: '', duration: '', instructions: '' }])}
        >
          Add another medicine
        </Button>

        <Input label="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
    </Modal>
  );
}

/* ============================================================
   NEW CONSENT FORM MODAL
   ============================================================ */
function NewConsentFormModal({ patientId, open, onClose }: { patientId: string | null; open: boolean; onClose: () => void }) {
  const [formType, setFormType] = useState('IVF Treatment Consent');
  const [content, setContent] = useState('');
  const createConsentForm = useCreateConsentForm();

  const reset = () => {
    setFormType('IVF Treatment Consent');
    setContent('');
    createConsentForm.reset();
  };

  return (
    <Modal
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="New Consent Form"
      subtitle="Create a consent form draft for this patient to review and sign"
      footer={
        <div className="flex items-center justify-between gap-3">
          {createConsentForm.isError && (
            <p className="text-[13px] text-rose-600">
              {createConsentForm.error instanceof ApiError ? createConsentForm.error.message : 'Failed to create consent form.'}
            </p>
          )}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={() => { reset(); onClose(); }}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={!patientId || !content.trim() || createConsentForm.isPending}
              loading={createConsentForm.isPending}
              onClick={() => {
                if (!patientId) return;
                createConsentForm.mutate(
                  { patient_id: patientId, form_type: formType, content },
                  { onSuccess: () => { reset(); onClose(); } }
                );
              }}
            >
              Create Draft
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Select label="Form type" value={formType} onChange={(e) => setFormType(e.target.value)}>
          <option>IVF Treatment Consent</option>
          <option>ICSI Procedure Consent</option>
          <option>Cryopreservation Consent</option>
          <option>Donor Gamete Consent</option>
          <option>Anaesthesia Consent</option>
        </Select>
        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Content</span>
          <textarea
            className="min-h-[140px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900"
            placeholder="Enter the consent form text the patient will review and sign…"
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </label>
      </div>
    </Modal>
  );
}

/* ============================================================
   ADD NURSING RECORD MODAL
   ============================================================ */
function AddNursingRecordModal({ patientId, open, onClose }: { patientId: string | null; open: boolean; onClose: () => void }) {
  const [systolic, setSystolic] = useState('');
  const [diastolic, setDiastolic] = useState('');
  const [temperature, setTemperature] = useState('');
  const [notes, setNotes] = useState('');
  const [appointmentId, setAppointmentId] = useState('');
  const createRecord = useCreateNursingRecord();
  const appointmentsQuery = usePatientAppointments(open ? patientId : null);

  const reset = () => {
    setSystolic('');
    setDiastolic('');
    setTemperature('');
    setNotes('');
    setAppointmentId('');
    createRecord.reset();
  };
  const close = () => { reset(); onClose(); };

  const numOrNull = (v: string) => (v.trim() === '' ? null : Number(v));
  const hasAny =
    systolic.trim() !== '' || diastolic.trim() !== '' || temperature.trim() !== '' || notes.trim() !== '';

  return (
    <Modal
      open={open}
      onClose={close}
      title="Add Nursing Record"
      subtitle="Vitals and observations for this patient. Patient, nurse and time are recorded automatically."
      footer={
        <div className="flex items-center justify-between gap-3">
          {createRecord.isError && (
            <p className="text-[13px] text-rose-600">
              {createRecord.error instanceof ApiError ? createRecord.error.message : 'Failed to save nursing record.'}
            </p>
          )}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!patientId || !hasAny || createRecord.isPending}
              loading={createRecord.isPending}
              onClick={() => {
                if (!patientId) return;
                createRecord.mutate(
                  {
                    patient_id: patientId,
                    appointment_id: appointmentId || null,
                    blood_pressure_systolic: numOrNull(systolic),
                    blood_pressure_diastolic: numOrNull(diastolic),
                    temperature: numOrNull(temperature),
                    notes: notes.trim() || null,
                  },
                  { onSuccess: close }
                );
              }}
            >
              Save Record
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {(appointmentsQuery.data ?? []).length > 0 && (
          <Select label="Visit (optional)" value={appointmentId} onChange={(e) => setAppointmentId(e.target.value)}>
            <option value="">— Not linked to a visit —</option>
            {(appointmentsQuery.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {new Date(a.scheduled_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} · {a.visit_type}
              </option>
            ))}
          </Select>
        )}

        <div>
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Blood Pressure</span>
          <div className="flex items-center gap-2">
            <Input type="number" inputMode="numeric" placeholder="Systolic" value={systolic} onChange={(e) => setSystolic(e.target.value)} className="w-28" />
            <span className="text-ink-400">/</span>
            <Input type="number" inputMode="numeric" placeholder="Diastolic" value={diastolic} onChange={(e) => setDiastolic(e.target.value)} className="w-28" />
            <span className="text-[13px] text-ink-500">mmHg</span>
          </div>
        </div>

        <div className="sm:w-56">
          <Input label="Temperature" type="number" inputMode="decimal" placeholder="e.g. 98.4" hint="degF" value={temperature} onChange={(e) => setTemperature(e.target.value)} />
        </div>

        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Notes</span>
          <textarea
            className="min-h-[110px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900"
            placeholder="Observations, patient comfort, complaints…"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>
      </div>
    </Modal>
  );
}

/* ============================================================
   NEW MRD RECORD MODAL
   ============================================================ */
function NewMRDRecordModal({ patientId, open, onClose }: { patientId: string | null; open: boolean; onClose: () => void }) {
  const [recordType, setRecordType] = useState('Registration');
  const [notes, setNotes] = useState('');
  const createMRDRecord = useCreateMRDRecord();

  const reset = () => {
    setRecordType('Registration');
    setNotes('');
    createMRDRecord.reset();
  };

  return (
    <Modal
      open={open}
      onClose={() => { reset(); onClose(); }}
      title="New MRD Record"
      subtitle="Add a Medical Records Department entry for this patient"
      footer={
        <div className="flex items-center justify-between gap-3">
          {createMRDRecord.isError && (
            <p className="text-[13px] text-rose-600">
              {createMRDRecord.error instanceof ApiError ? createMRDRecord.error.message : 'Failed to create MRD record.'}
            </p>
          )}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={() => { reset(); onClose(); }}>
              Cancel
            </Button>
            <Button
              variant="primary"
              disabled={!patientId || !notes.trim() || createMRDRecord.isPending}
              loading={createMRDRecord.isPending}
              onClick={() => {
                if (!patientId) return;
                createMRDRecord.mutate(
                  { patient_id: patientId, record_type: recordType, fields: { notes } },
                  { onSuccess: () => { reset(); onClose(); } }
                );
              }}
            >
              Save Record
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Select label="Record type" value={recordType} onChange={(e) => setRecordType(e.target.value)}>
          <option>Registration</option>
          <option>Correction Request</option>
          <option>Retrieval Log</option>
          <option>Disposal Notice</option>
        </Select>
        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Notes</span>
          <textarea
            className="min-h-[100px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>
      </div>
    </Modal>
  );
}

/* ============================================================
   CONSENT FORM ROW
   ============================================================ */
function ConsentFormRow({
  form,
  style,
}: {
  form: { id: string; form_type: string; status: 'draft' | 'signed' | 'withdrawn'; signed_at: string | null; created_at: string };
  style?: React.CSSProperties;
}) {
  const signConsentForm = useSignConsentForm();
  const tone = form.status === 'signed' ? 'completed' : form.status === 'withdrawn' ? 'critical' : 'attention';
  return (
    <div style={style} className="flex items-center justify-between gap-4 px-5 py-3">
      <div className="min-w-0">
        <p className="text-[13.5px] font-semibold text-ink-900">{form.form_type}</p>
        <p className="text-[12.5px] text-ink-500">
          {form.status === 'signed' && form.signed_at
            ? `Signed ${new Date(form.signed_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}`
            : `Created ${new Date(form.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}`}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Badge tone={tone} size="sm">
          {form.status}
        </Badge>
        {form.status === 'draft' && (
          <Button size="sm" loading={signConsentForm.isPending} onClick={() => signConsentForm.mutate(form.id)}>
            Mark Signed
          </Button>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   WORKSPACE
   ============================================================ */
export function Workspace() {
  const { go, toast, selectedPatientId } = useApp();
  const [tab, setTab] = useState('summary');
  const latest = MONITORING_HISTORY[MONITORING_HISTORY.length - 1];

  const coupleQuery = useCoupleForPatient(selectedPatientId);
  const consultationsQuery = usePatientConsultations(selectedPatientId);
  const labOrdersQuery = useLabOrders();
  const activeCycleQuery = useActiveCycle(coupleQuery.data?.id ?? null);
  const documentsQuery = usePatientDocuments(selectedPatientId);
  const invoicesQuery = useInvoices(selectedPatientId);
  const prescriptionsQuery = usePrescriptions(selectedPatientId);
  const consentFormsQuery = useConsentForms(selectedPatientId);
  const mrdRecordsQuery = useMRDRecords(selectedPatientId);
  const nursingRecordsQuery = useNursingRecords(selectedPatientId);
  const [writePrescriptionOpen, setWritePrescriptionOpen] = useState(false);
  const [newConsentOpen, setNewConsentOpen] = useState(false);
  const [newMrdOpen, setNewMrdOpen] = useState(false);
  const [newNursingOpen, setNewNursingOpen] = useState(false);

  const hasRealConsultations = (consultationsQuery.data ?? []).length > 0;
  const realConsultations = useMemo(
    () =>
      (consultationsQuery.data ?? []).map((c) => ({
        type: c.consultation_type,
        date: new Date(c.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }),
        doctor: 'Consultant',
        note: c.notes,
      })),
    [consultationsQuery.data]
  );
  const consultations = hasRealConsultations ? realConsultations : CONSULTATIONS;

  const patientLabOrders = useMemo(
    () => (labOrdersQuery.data ?? []).filter((o) => o.patient_id === selectedPatientId),
    [labOrdersQuery.data, selectedPatientId]
  );
  const hasRealInvestigations = patientLabOrders.length > 0;
  const realInvestigations = useMemo(
    () =>
      patientLabOrders.map((o) => ({
        name: o.test_name,
        status: LAB_STATUS_LABEL[o.status],
        tone: LAB_STATUS_TONE[o.status],
        sampleType: o.sample_type ?? '—',
        date: new Date(o.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }),
      })),
    [patientLabOrders]
  );

  const realMedications = activeCycleQuery.data?.treatment_plans?.[0]?.medication_plan ?? null;
  const hasRealMedications = !!realMedications && realMedications.length > 0;
  const medications = hasRealMedications
    ? realMedications!.map((m) => ({ name: m.name, dose: m.dose, route: m.route, since: '—', status: m.status, tone: (m.status === 'active' ? 'active' : 'completed') as StatusTone }))
    : MEDICATIONS;

  const hasRealDocuments = (documentsQuery.data ?? []).length > 0;
  const documents = hasRealDocuments
    ? (documentsQuery.data ?? []).map((d) => ({
        name: d.original_filename,
        date: new Date(d.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }),
        size: d.size_bytes >= 1_000_000 ? `${(d.size_bytes / 1_000_000).toFixed(1)} MB` : `${Math.round(d.size_bytes / 1000)} KB`,
        signed: d.signed,
      }))
    : STATIC_DOCUMENTS;

  const realInvoices = invoicesQuery.data ?? [];
  const hasRealBilling = realInvoices.length > 0;
  const billingTotals = hasRealBilling
    ? {
        value: realInvoices.reduce((s, i) => s + i.total_amount_paise, 0) / 100,
        paid: realInvoices.reduce((s, i) => s + i.paid_amount_paise, 0) / 100,
        outstanding: realInvoices.reduce((s, i) => s + i.outstanding_paise, 0) / 100,
      }
    : { value: PACKAGE.value, paid: PACKAGE.paid, outstanding: PACKAGE.outstanding };
  const billingCollectedPct = billingTotals.value > 0 ? Math.round((billingTotals.paid / billingTotals.value) * 100) : 0;

  const TABS = [
    { id: 'summary', label: 'Clinical Summary' },
    { id: 'timeline', label: 'Timeline' },
    { id: 'consultations', label: 'Consultations', count: consultations.length },
    { id: 'nursing', label: 'Nursing', count: (nursingRecordsQuery.data ?? []).length },
    { id: 'investigations', label: 'Investigations', count: hasRealInvestigations ? realInvestigations.length : INVESTIGATIONS.length },
    { id: 'cycle', label: 'IVF Cycle' },
    { id: 'prescriptions', label: 'Prescriptions', count: (prescriptionsQuery.data ?? []).length || medications.length },
    { id: 'documents', label: 'Documents' },
    { id: 'billing', label: 'Billing' },
  ];

  return (
    <div className="screen-enter mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6 lg:p-8">
      <WritePrescriptionModal patientId={selectedPatientId} open={writePrescriptionOpen} onClose={() => setWritePrescriptionOpen(false)} />
      <NewConsentFormModal patientId={selectedPatientId} open={newConsentOpen} onClose={() => setNewConsentOpen(false)} />
      <NewMRDRecordModal patientId={selectedPatientId} open={newMrdOpen} onClose={() => setNewMrdOpen(false)} />
      <AddNursingRecordModal patientId={selectedPatientId} open={newNursingOpen} onClose={() => setNewNursingOpen(false)} />
      <PatientHeader />

      <Card className="overflow-hidden">
        <div className="px-4 pt-2">
          <Tabs tabs={TABS} active={tab} onChange={setTab} />
        </div>

        <div className="p-5">
          {/* ---------------- SUMMARY ---------------- */}
          {tab === 'summary' && (
            <div className="animate-fade-up grid gap-5 lg:grid-cols-3">
              <div className="min-w-0 space-y-5 lg:col-span-2">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Card className="p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <Heart className="h-4 w-4 text-brand-600" />
                      <h3 className="text-[14.5px] font-semibold text-ink-900">Fertility Overview</h3>
                    </div>
                    <DataRow label="Diagnosis" value={PATIENT.infertilityType} />
                    <DataRow label="Duration" value={PATIENT.duration} />
                    <DataRow label="Previous IUI" value={`${PATIENT.previousIUI} cycles`} />
                    <DataRow label="Previous IVF" value={`${PATIENT.previousIVF} cycles`} />
                    <DataRow label="AMH" value={PATIENT.amh} />
                    <DataRow label="Antral Follicle Count" value={PATIENT.afc} />
                    <DataRow label="Protocol" value={PATIENT.protocol} tone="active" />
                  </Card>

                  <Card className="p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <ShieldCheck className="h-4 w-4 text-brand-600" />
                      <h3 className="text-[14.5px] font-semibold text-ink-900">Medical Information</h3>
                    </div>
                    <DataRow label="Blood Group" value={PATIENT.bloodGroup} />
                    <DataRow label="BMI" value={PATIENT.bmi} />
                    <DataRow label="Allergies" value={PATIENT.allergies} />
                    <DataRow label="Occupation" value={PATIENT.occupation} />
                    <DataRow label="Registered" value={PATIENT.registeredOn} />
                    <DataRow label="Consultant" value="Dr. Archana" />
                    <DataRow label="Referral" value="Dr. Sudha Menon" />
                  </Card>
                </div>

                {/* Today's monitoring */}
                <Card>
                  <CardHeader
                    icon={<Activity className="h-4 w-4" />}
                    title={`Today's Monitoring — Day ${latest.day}`}
                    subtitle={`Recorded ${latest.date} · Awaiting clinical sign-off`}
                    action={<Badge tone="attention" size="sm">Needs review</Badge>}
                  />
                  <div className="grid grid-cols-2 gap-3 px-5 pb-5 sm:grid-cols-5">
                    {[
                      { l: 'Endometrium', v: `${latest.endometrium}`, u: 'mm' },
                      { l: 'Lead Follicle', v: `${Math.max(...latest.right, ...latest.left)}`, u: 'mm' },
                      { l: 'Estradiol', v: latest.estradiol.toLocaleString('en-IN'), u: 'pg/mL' },
                      { l: 'LH', v: `${latest.lh}`, u: 'mIU/mL' },
                      { l: 'Progesterone', v: `${latest.progesterone}`, u: 'ng/mL' },
                    ].map((m) => (
                      <div key={m.l} className="rounded-xl border border-ink-200/70 bg-ink-50/50 p-3">
                        <p className="text-[12px] font-medium uppercase tracking-[0.06em] text-ink-400">
                          {m.l}
                        </p>
                        <p className="tnum mt-1.5 text-[19px] font-semibold leading-none text-ink-900">
                          {m.v}
                          <span className="ml-1 text-[12px] font-normal text-ink-400">{m.u}</span>
                        </p>
                      </div>
                    ))}
                  </div>
                  <div className="px-5 pb-5">
                    <InfoNote tone="brand" icon={<Stethoscope className="h-4 w-4" />}>
                      <span className="font-medium">Doctor&apos;s review:</span> {latest.note}
                    </InfoNote>
                  </div>
                </Card>

                {/* Follicle growth */}
                <Card>
                  <CardHeader
                    icon={<TrendingUp className="h-4 w-4" />}
                    title="Follicular Growth Trend"
                    subtitle="Lead follicle and endometrial progression across the cycle"
                  />
                  <div className="px-5 pb-5">
                    <GrowthChart
                      xLabels={MONITORING_HISTORY.map((m) => `Day ${m.day}`)}
                      yUnit="millimetres"
                      series={[
                        {
                          name: 'Lead follicle (mm)',
                          color: '#059669',
                          values: MONITORING_HISTORY.map((m) => Math.max(...m.right, ...m.left)),
                        },
                        {
                          name: 'Endometrium (mm)',
                          color: '#8B5CF6',
                          values: MONITORING_HISTORY.map((m) => m.endometrium),
                        },
                      ]}
                    />
                  </div>
                </Card>
              </div>

              {/* Right rail */}
              <div className="space-y-4">
                <Card className="p-4">
                  <h3 className="mb-3 text-[14.5px] font-semibold text-ink-900">Current Cycle</h3>
                  <div className="rounded-xl bg-gradient-to-br from-brand-600 to-brand-800 p-4 text-white">
                    <p className="text-[12px] uppercase tracking-[0.08em] text-brand-200">Cycle ID</p>
                    <p className="tnum mt-0.5 text-[15px] font-semibold">{PATIENT.cycleId}</p>
                    <div className="mt-3.5 flex items-end justify-between">
                      <div>
                        <p className="text-[12px] text-brand-200">Current day</p>
                        <p className="tnum text-[28px] font-semibold leading-none">Day {PATIENT.cycleDay}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-[12px] text-brand-200">Phase</p>
                        <p className="text-[14px] font-medium">{PATIENT.phase}</p>
                      </div>
                    </div>
                    <div className="mt-3.5">
                      <div className="mb-1.5 flex justify-between text-[12px] text-brand-200">
                        <span>Stimulation progress</span>
                        <span className="tnum">Day 8 of ~10</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/20">
                        <div
                          className="h-full rounded-full bg-white transition-[width] duration-[1400ms] ease-spring"
                          style={{ width: '80%' }}
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 space-y-0">
                    <DataRow label="Treatment" value={PATIENT.treatment} />
                    <DataRow label="Next Review" value="30 July 2026" />
                    <DataRow label="Expected Retrieval" value="2 August 2026" />
                  </div>
                </Card>

                <Card className="p-4">
                  <h3 className="mb-3 text-[14.5px] font-semibold text-ink-900">Clinical Actions</h3>
                  <div className="space-y-2">
                    <ActionRow label="Review Monitoring" description="Day 8 scan and hormones" icon={<Activity className="h-4 w-4" />} onClick={() => go('monitoring')} />
                    <ActionRow label="Update Medication" description="Adjust stimulation dosage" icon={<Pill className="h-4 w-4" />} onClick={() => toast({ title: 'Medication updated', body: 'Gonal-F 225 IU continued. Recorded in audit trail.', tone: 'success' })} />
                    <ActionRow label="Add Clinical Note" description="Document today's assessment" icon={<FileText className="h-4 w-4" />} onClick={() => toast({ title: 'Clinical note saved', body: "Saved to Priya's treatment timeline.", tone: 'success' })} />
                    <ActionRow label="Schedule Follow-up" description="Book next monitoring visit" icon={<CalendarPlus className="h-4 w-4" />} onClick={() => toast({ title: 'Follow-up scheduled', body: '30 July 2026, 9:30 AM — Scan Room 2.', tone: 'success' })} />
                  </div>
                </Card>

                <Card className="p-4">
                  <h3 className="mb-3 text-[14.5px] font-semibold text-ink-900">Partner Summary</h3>
                  <div className="flex items-center gap-3 rounded-xl bg-ink-50 p-3">
                    <Avatar initials={PARTNER.initials} size="md" gradient="from-sky-500 to-blue-600" />
                    <div className="min-w-0">
                      <p className="text-[14px] font-semibold text-ink-900">{PARTNER.name}</p>
                      <p className="tnum text-[12.5px] text-ink-500">{PARTNER.id}</p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <DataRow label="Age" value={`${PARTNER.age} years`} />
                    <DataRow label="Blood Group" value={PARTNER.bloodGroup} />
                    <DataRow label="Occupation" value={PARTNER.occupation} />
                  </div>
                  <div className="mt-3 rounded-xl border border-amber-200/70 bg-amber-50/60 p-3">
                    <p className="text-[12px] font-semibold uppercase tracking-wide text-amber-700">
                      Semen Analysis
                    </p>
                    <p className="mt-1 text-[13px] leading-relaxed text-amber-900">
                      {PARTNER.semenAnalysis.verdict}
                    </p>
                    <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[12.5px]">
                      <span className="text-amber-700">Count</span>
                      <span className="tnum font-medium text-amber-900">{PARTNER.semenAnalysis.concentration}</span>
                      <span className="text-amber-700">Motility</span>
                      <span className="tnum font-medium text-amber-900">{PARTNER.semenAnalysis.motility}</span>
                    </div>
                  </div>
                </Card>
              </div>
            </div>
          )}

          {/* ---------------- TIMELINE ---------------- */}
          {tab === 'timeline' && (
            <div className="animate-fade-up">
              <div className="mb-4 flex items-center justify-between">
                <p className="text-[14px] text-ink-500">Condensed journey view</p>
                <Button size="sm" iconRight={<ChevronRight className="h-3.5 w-3.5" />} onClick={() => go('timeline')}>
                  Open full timeline
                </Button>
              </div>
              <div className="stagger space-y-2">
                {TIMELINE.map((s, i) => (
                  <div
                    key={s.id}
                    style={{ ['--i' as string]: i }}
                    className={cn(
                      'flex items-center gap-3.5 rounded-xl border p-3.5',
                      s.status === 'active' ? 'border-brand-300 bg-brand-50/50' : 'border-ink-200/70 bg-white'
                    )}
                  >
                    <span
                      className={cn(
                        'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[12px] font-bold text-white',
                        s.status === 'completed' ? 'bg-brand-600' : s.status === 'active' ? 'bg-amber-500' : 'bg-ink-300'
                      )}
                    >
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[14.5px] font-medium text-ink-900">{s.title}</p>
                      <p className="text-[12.5px] text-ink-500">{s.date}</p>
                    </div>
                    <Badge tone={s.status === 'completed' ? 'completed' : s.status === 'active' ? 'active' : 'pending'} size="sm">
                      {s.status === 'completed' ? 'Completed' : s.status === 'active' ? 'In progress' : 'Upcoming'}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ---------------- CONSULTATIONS ---------------- */}
          {tab === 'consultations' && (
            <div className="animate-fade-up stagger space-y-3">
              {consultations.length === 0 && <p className="px-1 py-8 text-center text-[14px] text-ink-500">No consultations recorded yet.</p>}
              {consultations.map((c, i) => (
                <Card key={i} style={{ ['--i' as string]: i }} className="p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                        <Stethoscope className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-[14.5px] font-semibold text-ink-900">{c.type}</p>
                        <p className="text-[12.5px] text-ink-500">
                          {c.date} · {c.doctor}
                        </p>
                      </div>
                    </div>
                    <Button size="sm" variant="ghost" icon={<Printer className="h-3.5 w-3.5" />}>
                      Print
                    </Button>
                  </div>
                  <p className="mt-3 border-l-2 border-brand-200 pl-3 text-[14px] leading-relaxed text-ink-600">
                    {c.note}
                  </p>
                </Card>
              ))}
            </div>
          )}

          {/* ---------------- NURSING ---------------- */}
          {tab === 'nursing' && (
            <div className="animate-fade-up space-y-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[13px] text-ink-500">Vitals and observations recorded by nursing staff.</p>
                <Button
                  size="sm"
                  variant="primary"
                  icon={<Activity className="h-4 w-4" />}
                  disabled={!selectedPatientId}
                  onClick={() => setNewNursingOpen(true)}
                >
                  Add Nursing Record
                </Button>
              </div>

              {(nursingRecordsQuery.data ?? []).length === 0 ? (
                <p className="px-1 py-8 text-center text-[14px] text-ink-500">No nursing records yet for this patient.</p>
              ) : (
                <div className="stagger space-y-3">
                  {(nursingRecordsQuery.data ?? []).map((r, i) => (
                    <Card key={r.id} style={{ ['--i' as string]: i }} className="p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="tnum text-[13px] font-semibold text-ink-600">
                          {new Date(r.recorded_at).toLocaleString('en-IN', {
                            day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
                          })}
                        </p>
                        <p className="text-[12.5px] text-ink-500">Recorded by: {r.recorded_by_name ?? '—'}</p>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-x-8 gap-y-1.5 text-[13.5px]">
                        {(r.blood_pressure_systolic != null || r.blood_pressure_diastolic != null) && (
                          <span>
                            <span className="text-ink-500">BP: </span>
                            <span className="tnum font-semibold text-ink-900">
                              {r.blood_pressure_systolic ?? '—'}/{r.blood_pressure_diastolic ?? '—'}
                            </span>
                            <span className="text-ink-400"> mmHg</span>
                          </span>
                        )}
                        {r.temperature != null && (
                          <span>
                            <span className="text-ink-500">Temperature: </span>
                            <span className="tnum font-semibold text-ink-900">{r.temperature}</span>
                            <span className="text-ink-400"> °F</span>
                          </span>
                        )}
                      </div>
                      {r.notes && (
                        <p className="mt-2 border-l-2 border-brand-200 pl-3 text-[13.5px] leading-relaxed text-ink-600">
                          {r.notes}
                        </p>
                      )}
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ---------------- INVESTIGATIONS ---------------- */}
          {tab === 'investigations' && (
            <div className="animate-fade-up">
              {hasRealInvestigations ? (
                <Card className="overflow-hidden">
                  <div className="hidden grid-cols-[2fr_1fr_1fr_100px] gap-4 border-b border-ink-200/70 bg-ink-50/60 px-5 py-2.5 md:grid">
                    {['Investigation', 'Sample Type', 'Date', 'Status'].map((h) => (
                      <span key={h} className="text-[12px] font-semibold uppercase tracking-[0.09em] text-ink-400">
                        {h}
                      </span>
                    ))}
                  </div>
                  <div className="stagger">
                    {realInvestigations.map((iv, i) => (
                      <div
                        key={iv.name + i}
                        style={{ ['--i' as string]: i }}
                        className="flex flex-col gap-1.5 border-b border-ink-100 px-4 py-3 last:border-0 hover:bg-ink-50/60 sm:px-5 md:grid md:grid-cols-[2fr_1fr_1fr_100px] md:items-center md:gap-4"
                      >
                        <div className="flex items-center justify-between gap-3 md:contents">
                          <span className="text-[14px] font-medium text-ink-800">{iv.name}</span>
                          <Badge tone={iv.tone} size="sm" className="md:hidden">
                            {iv.status}
                          </Badge>
                        </div>
                        <span className="text-[13px] text-ink-500">{iv.sampleType}</span>
                        <span className="text-[13px] text-ink-500">{iv.date}</span>
                        <Badge tone={iv.tone} size="sm" className="hidden md:inline-flex">
                          {iv.status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </Card>
              ) : (
                <Card className="overflow-hidden">
                  <div className="hidden grid-cols-[2fr_1fr_1fr_1fr_100px] gap-4 border-b border-ink-200/70 bg-ink-50/60 px-5 py-2.5 md:grid">
                    {['Investigation', 'Result', 'Reference', 'Date', 'Status'].map((h) => (
                      <span key={h} className="text-[12px] font-semibold uppercase tracking-[0.09em] text-ink-400">
                        {h}
                      </span>
                    ))}
                  </div>
                  <div className="stagger">
                    {INVESTIGATIONS.map((iv, i) => (
                      <div
                        key={iv.name}
                        style={{ ['--i' as string]: i }}
                        className="flex flex-col gap-1.5 border-b border-ink-100 px-4 py-3 last:border-0 hover:bg-ink-50/60 sm:px-5 md:grid md:grid-cols-[2fr_1fr_1fr_1fr_100px] md:items-center md:gap-4"
                      >
                        <div className="flex items-center justify-between gap-3 md:contents">
                          <span className="text-[14px] font-medium text-ink-800">{iv.name}</span>
                          <Badge tone={iv.flag === 'normal' ? 'completed' : 'attention'} size="sm" className="md:hidden">
                            {iv.flag === 'normal' ? 'Normal' : 'Low'}
                          </Badge>
                        </div>
                        <span className="tnum text-[14px] font-semibold text-ink-900">{iv.value}</span>
                        <span className="tnum text-[13px] text-ink-500">Ref {iv.ref}</span>
                        <span className="text-[13px] text-ink-500">{iv.date}</span>
                        <Badge tone={iv.flag === 'normal' ? 'completed' : 'attention'} size="sm" className="hidden md:inline-flex">
                          {iv.flag === 'normal' ? 'Normal' : 'Low'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* ---------------- CYCLE ---------------- */}
          {tab === 'cycle' && (
            <div className="animate-fade-up space-y-4">
              <InfoNote tone="brand" icon={<FlaskConical className="h-4 w-4" />}>
                Cycle <span className="tnum font-semibold">{PATIENT.cycleId}</span> — {PATIENT.treatment} on a{' '}
                {PATIENT.protocol}. Currently on stimulation day {PATIENT.cycleDay}.
              </InfoNote>
              <div className="grid gap-4 sm:grid-cols-3">
                <ActionRow label="Stimulation & Monitoring" description="Follicle tracking and hormones" icon={<Activity className="h-4 w-4" />} onClick={() => go('monitoring')} />
                <ActionRow label="Treatment Plan" description="Protocol, stages and consent" icon={<ClipboardList className="h-4 w-4" />} onClick={() => go('plan')} />
                <ActionRow label="Embryology Workspace" description="Oocytes, embryos and grading" icon={<FlaskConical className="h-4 w-4" />} onClick={() => go('embryology')} />
              </div>
            </div>
          )}

          {/* ---------------- PRESCRIPTIONS ---------------- */}
          {tab === 'prescriptions' && (
            <div className="animate-fade-up space-y-4">
              <div className="flex justify-end">
                <Button
                  variant="primary"
                  icon={<PenLine className="h-4 w-4" />}
                  onClick={() => setWritePrescriptionOpen(true)}
                  disabled={!selectedPatientId}
                >
                  Write Prescription
                </Button>
              </div>

              {(prescriptionsQuery.data ?? []).length > 0 ? (
                <div className="stagger space-y-3">
                  {(prescriptionsQuery.data ?? []).map((p, i) => (
                    <Card key={p.id} style={{ ['--i' as string]: i }} className="p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[13px] font-semibold text-ink-500">
                          {new Date(p.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                          {p.category && <span className="text-ink-400"> · {p.category}</span>}
                        </p>
                        <Button
                          size="sm"
                          variant="ghost"
                          icon={<Printer className="h-3.5 w-3.5" />}
                          onClick={() =>
                            openPrescriptionPdf(p.id).catch(() =>
                              toast({ title: 'Could not open the prescription PDF', tone: 'error' })
                            )
                          }
                        >
                          Print Prescription
                        </Button>
                      </div>
                      <div className="mt-3 space-y-2">
                        {p.lines.map((l) => (
                          <div key={l.id} className="flex flex-wrap items-center gap-3 rounded-lg bg-ink-50/70 px-3 py-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                              <Pill className="h-4 w-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="text-[13.5px] font-semibold text-ink-900">
                                {l.medicine_name} <span className="tnum font-normal text-ink-500">· {l.dosage}</span>
                              </p>
                              <p className="text-[12.5px] text-ink-500">
                                {l.frequency}
                                {l.timing ? ` · ${l.timing}` : ''}
                                {l.duration ? ` · ${l.duration}` : ''}
                              </p>
                              {l.instructions && <p className="text-[12px] text-ink-400">{l.instructions}</p>}
                            </div>
                          </div>
                        ))}
                      </div>
                      {p.notes && <p className="mt-2 text-[12.5px] text-ink-500">Notes: {p.notes}</p>}
                    </Card>
                  ))}
                </div>
              ) : (
                <div className="stagger space-y-2.5">
                  {medications.map((m, i) => (
                    <Card key={m.name} style={{ ['--i' as string]: i }} className="flex flex-wrap items-center gap-4 p-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                        <Pill className="h-5 w-5" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-[14.5px] font-semibold text-ink-900">
                          {m.name} <span className="tnum font-normal text-ink-500">· {m.dose}</span>
                        </p>
                        <p className="text-[13px] text-ink-500">{m.route}</p>
                      </div>
                      {m.since !== '—' && <span className="text-[13px] text-ink-500">Since {m.since}</span>}
                      <Badge tone={m.tone} size="sm">
                        {m.status}
                      </Badge>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ---------------- DOCUMENTS ---------------- */}
          {tab === 'documents' && (
            <div className="animate-fade-up space-y-6">
              <div className="stagger grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {documents.length === 0 && (
                  <p className="col-span-full px-1 py-8 text-center text-[14px] text-ink-500">No documents uploaded yet for this patient.</p>
                )}
                {documents.map((d, i) => (
                  <Card key={d.name} style={{ ['--i' as string]: i }} interactive className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-ink-100 text-ink-500">
                        <FolderOpen className="h-5 w-5" />
                      </div>
                      {d.signed && <Badge tone="completed" size="sm">Signed</Badge>}
                    </div>
                    <p className="mt-3 text-[14px] font-semibold leading-snug text-ink-900">{d.name}</p>
                    <p className="mt-1 text-[12.5px] text-ink-500">
                      {d.date} · {d.size}
                    </p>
                    <button className="mt-2.5 flex items-center gap-1 text-[12.5px] font-medium text-brand-700 hover:text-brand-800">
                      <Download className="h-3 w-3" /> Download
                    </button>
                  </Card>
                ))}
              </div>

              <Card>
                <CardHeader
                  icon={<ShieldCheck className="h-4 w-4" />}
                  title="Consent Forms"
                  subtitle={`${(consentFormsQuery.data ?? []).length} forms on record`}
                  action={
                    <Button size="sm" icon={<Plus className="h-4 w-4" />} onClick={() => setNewConsentOpen(true)} disabled={!selectedPatientId}>
                      New Consent Form
                    </Button>
                  }
                />
                <div className="stagger divide-y divide-ink-100">
                  {(consentFormsQuery.data ?? []).length === 0 && (
                    <p className="px-5 py-8 text-center text-[14px] text-ink-500">No consent forms recorded for this patient yet.</p>
                  )}
                  {(consentFormsQuery.data ?? []).map((f, i) => (
                    <ConsentFormRow key={f.id} form={f} style={{ ['--i' as string]: i }} />
                  ))}
                </div>
              </Card>

              <Card>
                <CardHeader
                  icon={<FileText className="h-4 w-4" />}
                  title="MRD Records"
                  subtitle={`${(mrdRecordsQuery.data ?? []).length} records on file`}
                  action={
                    <Button size="sm" icon={<Plus className="h-4 w-4" />} onClick={() => setNewMrdOpen(true)} disabled={!selectedPatientId}>
                      New MRD Record
                    </Button>
                  }
                />
                <div className="stagger divide-y divide-ink-100">
                  {(mrdRecordsQuery.data ?? []).length === 0 && (
                    <p className="px-5 py-8 text-center text-[14px] text-ink-500">No MRD records on file for this patient yet.</p>
                  )}
                  {(mrdRecordsQuery.data ?? []).map((r, i) => (
                    <div key={r.id} style={{ ['--i' as string]: i }} className="flex items-center justify-between gap-4 px-5 py-3">
                      <div className="min-w-0">
                        <p className="text-[13.5px] font-semibold text-ink-900">{r.record_type}</p>
                        <p className="truncate text-[12.5px] text-ink-500">
                          {typeof r.fields?.notes === 'string' ? r.fields.notes : JSON.stringify(r.fields)}
                        </p>
                      </div>
                      <span className="tnum shrink-0 text-[12.5px] text-ink-400">
                        {new Date(r.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* ---------------- BILLING ---------------- */}
          {tab === 'billing' && (
            <div className="animate-fade-up space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                {[
                  { l: hasRealBilling ? 'Total Billed' : 'Package Value', v: billingTotals.value, tone: 'neutral' as const },
                  { l: 'Amount Paid', v: billingTotals.paid, tone: 'completed' as const },
                  { l: 'Outstanding', v: billingTotals.outstanding, tone: 'attention' as const },
                ].map((s) => (
                  <Card key={s.l} className="p-4">
                    <p className="text-[12.5px] font-medium uppercase tracking-[0.06em] text-ink-400">{s.l}</p>
                    <p className={cn('tnum mt-1.5 text-[24px] font-semibold', TONE[s.tone].text)}>
                      {formatINR(Math.round(s.v))}
                    </p>
                  </Card>
                ))}
              </div>
              <Card className="p-4">
                <div className="mb-2 flex justify-between text-[13.5px]">
                  <span className="text-ink-600">Package utilisation</span>
                  <span className="tnum font-medium text-ink-900">{billingCollectedPct}% collected</span>
                </div>
                <ProgressBar value={billingCollectedPct} height={8} />
              </Card>
              <Button variant="primary" iconRight={<ChevronRight className="h-4 w-4" />} onClick={() => go('billing')}>
                Open full billing workspace
              </Button>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
