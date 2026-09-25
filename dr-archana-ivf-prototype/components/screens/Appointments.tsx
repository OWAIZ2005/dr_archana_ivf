'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useApp } from '@/lib/store';
import { cn, TONE, initialsOf } from '@/lib/utils';
import { Card, CardHeader, Badge, Button, Avatar, SectionTitle, Input, Select, Skeleton, Modal, InfoNote, Tabs, PillFilter } from '@/components/ui/primitives';
import { useCountUp } from '@/lib/hooks';
import {
  useAppointments,
  useCreateAppointment,
  useCheckInAppointment,
  useMarkNotArrived,
  useEditAppointment,
  useTodayByBatch,
  useUpdateAppointmentStatus,
  useRescheduleAppointment,
  useFutureAppointments,
  useClosedAppointments,
  useAppointmentsByChannel,
  useAppointmentBatches,
} from '@/lib/api/appointments';
import { usePatients, usePatientSummary, useCreatePatient } from '@/lib/api/patients';
import { useDoctors } from '@/lib/api/users';
import { useReminders, useCreateReminder, useCompleteReminder, useCancelReminder } from '@/lib/api/reminders';
import { useCreateCommunication } from '@/lib/api/communications';
import { ApiError } from '@/lib/api/client';
import type { AppointmentBatchOut, AppointmentChannel, AppointmentOut, BatchGroupOut, CommunicationChannel, ReminderOut } from '@/lib/api/types';
import { COMMUNICATION_OUTCOMES, NOT_ARRIVED_GRACE_PERIOD_MINUTES } from '@/lib/api/types';
import {
  CalendarClock,
  CalendarPlus,
  Search,
  Users2,
  CheckCircle2,
  Clock3,
  XCircle,
  Globe,
  ChevronRight,
  AlertTriangle,
  Phone,
  Mail,
  BellRing,
  Archive,
  CalendarDays,
  UserPlus,
} from 'lucide-react';

const STATUS_TONE: Record<string, keyof typeof TONE> = {
  registered: 'scheduled',
  arrived: 'active',
  waiting: 'attention',
  consultation: 'active',
  investigation: 'active',
  billing: 'pending',
  pharmacy: 'pending',
  follow_up: 'scheduled',
  completed: 'completed',
  cancelled: 'cancelled',
  no_show: 'critical',
};

const STATUS_LABEL: Record<string, string> = {
  registered: 'Registered',
  arrived: 'Arrived',
  waiting: 'Waiting',
  consultation: 'Consultation',
  investigation: 'Investigation',
  billing: 'Billing',
  pharmacy: 'Pharmacy',
  follow_up: 'Follow-up',
  completed: 'Completed',
  cancelled: 'Cancelled',
  no_show: 'No Show',
};

function MetricTile({ label, value, icon: Icon, tone }: { label: string; value: number; icon: any; tone: string }) {
  const v = useCountUp(value, 1000);
  return (
    <Card className="p-4">
      <div className={cn('flex h-9 w-9 items-center justify-center rounded-xl ring-1 ring-inset', tone)}>
        <Icon className="h-[18px] w-[18px]" />
      </div>
      <p className="tnum tracking-display mt-3 text-[24px] font-semibold leading-none text-ink-900">
        {Math.round(v)}
      </p>
      <p className="mt-1.5 text-[13px] font-medium text-ink-600">{label}</p>
    </Card>
  );
}

const DOCTOR_COLORS = ['#059669', '#0EA5E9', '#8B5CF6', '#F59E0B', '#EC4899', '#78716C'];

/** The only visit types that can ever land in a configured batch — pulled
 * live from the real batch config, not hardcoded, so this list always
 * matches whatever front-desk batches actually exist. Booking forms use
 * this instead of free text so an appointment is never silently placed
 * in "Unbatched" just because someone typed a category that doesn't
 * exist in any batch. */
function useVisitTypeOptions(): string[] {
  const batchesQuery = useAppointmentBatches();
  return useMemo(() => {
    const set = new Set<string>();
    for (const b of batchesQuery.data ?? []) {
      if (!b.is_active) continue;
      for (const t of b.visit_types) set.add(t);
    }
    return Array.from(set).sort();
  }, [batchesQuery.data]);
}

/** A Date as a local (not UTC) `datetime-local` input value — matching what
 * the browser shows for this same instant in a `<input type="datetime-local">`,
 * which `toISOString()` does not (it's always UTC). */
function toLocalDatetimeValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** "HH:MM" out of a `datetime-local` input value ("YYYY-MM-DDTHH:MM"), or
 * null when the value isn't complete yet. */
function timeOfDay(scheduledAtLocal: string): string | null {
  const idx = scheduledAtLocal.indexOf('T');
  if (idx === -1 || scheduledAtLocal.length < idx + 6) return null;
  return scheduledAtLocal.slice(idx + 1, idx + 6);
}

/** The active batch a visit type + time would actually land in, or null
 * when none matches — i.e. the appointment would fall into "Unbatched". */
function findMatchingBatch(
  visitType: string, scheduledAtLocal: string, batches: AppointmentBatchOut[]
): AppointmentBatchOut | null {
  const time = timeOfDay(scheduledAtLocal);
  if (!visitType || !time) return null;
  return (
    batches.find(
      (b) => b.is_active && b.visit_types.includes(visitType) && b.start_time.slice(0, 5) <= time && time < b.end_time.slice(0, 5)
    ) ?? null
  );
}

/** Warns before booking creates a silently "Unbatched" appointment — the
 * visit type is valid and the slot picker doesn't stop the user, but if no
 * configured batch covers this visit type at this time, the appointment
 * won't get a token, won't count against any batch's capacity, and won't
 * show up grouped in Today's Batches. Better to say so now than to have
 * front-desk staff discover it later in "Unbatched Appointments". */
function BatchMismatchWarning({ visitType, scheduledAt }: { visitType: string; scheduledAt: string }) {
  const batchesQuery = useAppointmentBatches();
  const batches = batchesQuery.data ?? [];
  const time = timeOfDay(scheduledAt);
  if (!visitType || !time || batches.length === 0) return null;
  if (findMatchingBatch(visitType, scheduledAt, batches)) return null;
  return (
    <InfoNote tone="amber" icon={<AlertTriangle className="h-4 w-4" />}>
      No configured batch covers <strong>{visitType}</strong> at this time — this appointment will be booked as
      "Unbatched": no token number, no capacity tracking, and it won't appear grouped under Today's Batches.
    </InfoNote>
  );
}

/** The "New Patient" quick-add step of the booking wizard. Checks for
 * likely duplicates by phone as the user types (reusing the existing
 * patient search — no separate duplicate-detection endpoint), and lets
 * them pick the existing record instead of registering a second one. */
function NewPatientQuickForm({
  onCreated, onUseExisting,
}: {
  onCreated: (patientId: string) => void;
  onUseExisting: (patientId: string) => void;
}) {
  const { toast } = useApp();
  const [fullName, setFullName] = useState('');
  const [gender, setGender] = useState('female');
  const [phone, setPhone] = useState('');
  const [dob, setDob] = useState('');
  const [error, setError] = useState<string | null>(null);
  const createPatient = useCreatePatient();
  const dupQuery = usePatients(phone.length >= 6 ? phone : undefined);
  const duplicates = phone.length >= 6 ? (dupQuery.data ?? []) : [];

  const submit = () => {
    setError(null);
    if (!fullName.trim() || !phone.trim()) { setError('Name and mobile number are required.'); return; }
    createPatient.mutate(
      { full_name: fullName.trim(), gender, phone: phone.trim(), date_of_birth: dob || null },
      {
        onSuccess: (patient) => {
          toast({ title: 'Patient registered', body: `UHID ${patient.uhid}`, tone: 'success' });
          onCreated(patient.id);
        },
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not register this patient.'),
      }
    );
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Input label="Patient name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        <Select label="Gender" value={gender} onChange={(e) => setGender(e.target.value)}>
          <option value="female">Female</option>
          <option value="male">Male</option>
          <option value="other">Other</option>
        </Select>
        <Input label="Mobile number" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <Input label="Date of birth (optional)" type="date" value={dob} onChange={(e) => setDob(e.target.value)} />
      </div>

      {duplicates.length > 0 && (
        <div className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="flex items-center gap-1.5 text-[13px] font-semibold text-amber-800">
            <AlertTriangle className="h-3.5 w-3.5" /> Possible existing patient{duplicates.length > 1 ? 's' : ''} found
          </p>
          {duplicates.map((p) => (
            <button
              key={p.id}
              onClick={() => onUseExisting(p.id)}
              className="flex w-full items-center justify-between rounded-lg border border-amber-200 bg-white px-3 py-2 text-left hover:bg-amber-50/60"
            >
              <span className="text-[13px]">
                <span className="font-medium text-ink-900">{p.full_name}</span>
                <span className="ml-2 text-ink-500">{p.uhid} · {p.phone}</span>
              </span>
              <span className="text-[12px] font-medium text-brand-700">Use this patient</span>
            </button>
          ))}
        </div>
      )}

      <Button variant="primary" loading={createPatient.isPending} disabled={!fullName.trim() || !phone.trim()} onClick={submit}>
        Register Patient
      </Button>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          <p className="text-[13.5px] leading-relaxed text-rose-700">{error}</p>
        </div>
      )}
    </div>
  );
}

function BookingModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { toast } = useApp();
  const patientsQuery = usePatients();
  const doctorsQuery = useDoctors();
  const createAppointment = useCreateAppointment();
  const [mode, setMode] = useState<'existing' | 'new'>('existing');
  const [patientId, setPatientId] = useState('');
  const [newPatientLabel, setNewPatientLabel] = useState<string | null>(null);
  const [doctorId, setDoctorId] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  const [visitType, setVisitType] = useState('');
  const [channel, setChannel] = useState<AppointmentChannel>('walk_in');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const visitTypeOptions = useVisitTypeOptions();

  const reset = () => {
    setMode('existing');
    setPatientId('');
    setNewPatientLabel(null);
    setDoctorId('');
    setScheduledAt('');
    setVisitType('');
    setChannel('walk_in');
    setNotes('');
    setError(null);
  };

  const submit = () => {
    setError(null);
    createAppointment.mutate(
      { patient_id: patientId, doctor_id: doctorId, scheduled_at: new Date(scheduledAt).toISOString(), visit_type: visitType, channel, notes: notes.trim() || null },
      {
        onSuccess: () => {
          toast({ title: 'Appointment booked', body: 'Added to the clinical schedule.', tone: 'success' });
          reset();
          onClose();
        },
        onError: (err) => setError(err instanceof ApiError ? err.message : 'Could not book the appointment.'),
      }
    );
  };

  const patientChosen = !!patientId;

  return (
    <Modal
      open={open}
      onClose={() => { reset(); onClose(); }}
      title="Book Appointment"
      subtitle={mode === 'new' && !patientChosen ? 'Step 1 of 2 — register the patient, then schedule their visit' : 'Schedule a new visit on the clinical calendar'}
      footer={
        patientChosen || mode === 'existing' ? (
          <>
            <Button onClick={() => { reset(); onClose(); }}>Cancel</Button>
            <Button
              variant="primary"
              loading={createAppointment.isPending}
              disabled={!patientId || !doctorId || !scheduledAt || !visitType}
              onClick={submit}
            >
              {createAppointment.isPending ? 'Booking…' : 'Schedule Appointment'}
            </Button>
          </>
        ) : (
          <Button onClick={() => { reset(); onClose(); }}>Cancel</Button>
        )
      }
    >
      {mode === 'new' && !patientChosen ? (
        <NewPatientQuickForm
          onCreated={(id) => { setPatientId(id); setNewPatientLabel('newly registered patient'); }}
          onUseExisting={(id) => { setPatientId(id); setNewPatientLabel(null); }}
        />
      ) : (
        <div className="space-y-4">
          {!patientChosen ? (
            <>
              <Select label="Patient" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
                <option value="">Select a patient…</option>
                {(patientsQuery.data ?? []).map((p) => (
                  <option key={p.id} value={p.id}>{p.full_name} — {p.uhid}</option>
                ))}
              </Select>
              <button onClick={() => setMode('new')} className="flex items-center gap-1.5 text-[13px] font-medium text-brand-700 hover:text-brand-800">
                <UserPlus className="h-3.5 w-3.5" /> New patient instead
              </button>
            </>
          ) : (
            <InfoNote tone="brand">
              {newPatientLabel ? `Scheduling for the ${newPatientLabel}.` : 'Patient selected.'}{' '}
              <button onClick={() => { setPatientId(''); setNewPatientLabel(null); }} className="font-medium underline">Change</button>
            </InfoNote>
          )}
          <Select label="Doctor" value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
            <option value="">Select a doctor…</option>
            {(doctorsQuery.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>{d.full_name}</option>
            ))}
          </Select>
          <Input label="Date & Time" type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
          <Select label="Visit Type" value={visitType} onChange={(e) => setVisitType(e.target.value)}>
            <option value="">Select a visit type…</option>
            {visitTypeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
          </Select>
          <Select label="Channel" value={channel} onChange={(e) => setChannel(e.target.value as AppointmentChannel)}>
            <option value="walk_in">Walk-in</option>
            <option value="phone">Phone</option>
            <option value="online">Online</option>
          </Select>
          <label className="block">
            <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Notes (optional)</span>
            <textarea
              className="min-h-[60px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900"
              value={notes} onChange={(e) => setNotes(e.target.value)}
            />
          </label>
          <BatchMismatchWarning visitType={visitType} scheduledAt={scheduledAt} />
          {error && (
            <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
              <p className="text-[13.5px] leading-relaxed text-rose-700">{error}</p>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

/** REGISTERED appointments still in the future/near-now render as
 * "Scheduled" (blue); once their time has passed without check-in they
 * become "Late / Awaiting Arrival" (amber) — purely a computed display
 * state, no separate backend status, matching how the workflow only
 * moves REGISTERED -> ARRIVED/CANCELLED/NO_SHOW on an explicit action. */
/** Re-renders every 30s so countdown labels/grace-period prompts stay
 * live without a full refetch — purely a display tick, no network call. */
function useNowTicker(intervalMs = 30_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function formatCountdown(msRemaining: number): string {
  const totalMinutes = Math.max(0, Math.ceil(msRemaining / 60_000));
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function arrivalDisplay(
  appt: AppointmentOut, now: number
): { label: string; tone: keyof typeof TONE; dotClass: string; graceExpired: boolean } {
  if (appt.status === 'arrived' || appt.checked_in_at) return { label: 'Arrived', tone: 'active', dotClass: 'bg-emerald-500', graceExpired: false };
  if (appt.status === 'no_show') return { label: 'Not Arrived', tone: 'critical', dotClass: 'bg-rose-500', graceExpired: false };
  if (appt.status === 'cancelled') return { label: 'Cancelled', tone: 'cancelled', dotClass: 'bg-ink-400', graceExpired: false };
  if (appt.status !== 'registered') return { label: STATUS_LABEL[appt.status] ?? appt.status, tone: STATUS_TONE[appt.status] ?? 'neutral', dotClass: 'bg-ink-400', graceExpired: false };

  if (appt.marked_not_arrived_at) {
    const elapsedMs = now - new Date(appt.marked_not_arrived_at).getTime();
    const graceMs = NOT_ARRIVED_GRACE_PERIOD_MINUTES * 60_000;
    if (elapsedMs >= graceMs) {
      return { label: 'Reschedule Needed', tone: 'critical', dotClass: 'bg-rose-500', graceExpired: true };
    }
    return { label: `Not Arrived — ${formatCountdown(graceMs - elapsedMs)} left`, tone: 'attention', dotClass: 'bg-amber-500', graceExpired: false };
  }

  const isPast = new Date(appt.scheduled_at).getTime() < now;
  return isPast
    ? { label: 'Late / Awaiting Arrival', tone: 'attention', dotClass: 'bg-amber-500', graceExpired: false }
    : { label: 'Scheduled', tone: 'scheduled', dotClass: 'bg-sky-500', graceExpired: false };
}

/** Fixes a booking mistake — wrong visit type or doctor picked — without
 * touching the date/time (that's what Reschedule is for). Editing the
 * visit type re-resolves which batch the appointment lands in for its
 * existing time, so correcting "Consultation" to "ANC" here is exactly
 * how staff move a wrongly-typed appointment into the right batch. */
function EditAppointmentModal({
  appointment, doctors, onClose,
}: {
  appointment: AppointmentOut;
  doctors: { id: string; full_name: string }[];
  onClose: () => void;
}) {
  const { toast } = useApp();
  const editAppointment = useEditAppointment();
  const visitTypeOptions = useVisitTypeOptions();
  const [visitType, setVisitType] = useState(appointment.visit_type);
  const [doctorId, setDoctorId] = useState(appointment.doctor_id);
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    editAppointment.mutate(
      { appointmentId: appointment.id, visit_type: visitType, doctor_id: doctorId },
      {
        onSuccess: () => { toast({ title: 'Appointment updated', tone: 'success' }); onClose(); },
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not save these changes.'),
      }
    );
  };

  return (
    <Modal
      open onClose={onClose} title="Edit Appointment"
      subtitle={new Date(appointment.scheduled_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={editAppointment.isPending} onClick={submit}>Save Changes</Button>
        </>
      }
    >
      <div className="space-y-4">
        <InfoNote>Date and time aren't changed here — use Reschedule for that.</InfoNote>
        <Select label="Visit Type" value={visitType} onChange={(e) => setVisitType(e.target.value)}>
          {!visitTypeOptions.includes(visitType) && <option value={visitType}>{visitType} (not a configured batch type)</option>}
          {visitTypeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
        </Select>
        <Select label="Doctor" value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
          {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
        </Select>
        <BatchMismatchWarning
          visitType={visitType}
          scheduledAt={toLocalDatetimeValue(new Date(appointment.scheduled_at))}
        />
        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            <p className="text-[13.5px] leading-relaxed text-rose-700">{error}</p>
          </div>
        )}
      </div>
    </Modal>
  );
}

function RescheduleModal({ appointment, onClose }: { appointment: AppointmentOut; onClose: () => void }) {
  const { toast } = useApp();
  const reschedule = useRescheduleAppointment();
  const [newDateTime, setNewDateTime] = useState('');
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    if (!newDateTime || !reason.trim()) { setError('New date/time and a reason are both required.'); return; }
    reschedule.mutate(
      { appointmentId: appointment.id, new_scheduled_at: new Date(newDateTime).toISOString(), reason: reason.trim() },
      {
        onSuccess: () => { toast({ title: 'Appointment rescheduled', tone: 'success' }); onClose(); },
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not reschedule this appointment.'),
      }
    );
  };

  return (
    <Modal
      open onClose={onClose} title="Reschedule Appointment" subtitle={appointment.visit_type}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={reschedule.isPending} onClick={submit}>Reschedule</Button>
        </>
      }
    >
      <div className="space-y-4">
        <InfoNote>
          Current: {new Date(appointment.scheduled_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
        </InfoNote>
        <Input label="New date & time" type="datetime-local" value={newDateTime} onChange={(e) => setNewDateTime(e.target.value)} />
        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Reason for rescheduling</span>
          <textarea
            className="min-h-[70px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900"
            placeholder="Patient requested rescheduling…" value={reason} onChange={(e) => setReason(e.target.value)}
          />
        </label>
        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            <p className="text-[13.5px] leading-relaxed text-rose-700">{error}</p>
          </div>
        )}
      </div>
    </Modal>
  );
}

/** Records that a staff member attempted to reach a patient — never
 * claims the call actually connected. tel:/mailto: links do the actual
 * dialing/composing (no telephony/email vendor is wired up); this modal
 * just logs the attempt and its outcome afterward. */
function ContactPatientModal({
  patientId, appointmentId, onClose,
}: {
  patientId: string;
  appointmentId: string | null;
  onClose: () => void;
}) {
  const { toast } = useApp();
  const patientQuery = usePatientSummary(patientId);
  const createComm = useCreateCommunication();
  const [channel, setChannel] = useState<CommunicationChannel>('call');
  const [outcome, setOutcome] = useState<string>(COMMUNICATION_OUTCOMES[0]);
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);

  const patient = patientQuery.data;

  const submit = () => {
    setError(null);
    createComm.mutate(
      { patient_id: patientId, appointment_id: appointmentId, channel, outcome, notes: notes.trim() || null },
      {
        onSuccess: () => { toast({ title: 'Contact attempt recorded', tone: 'success' }); onClose(); },
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not record this contact attempt.'),
      }
    );
  };

  return (
    <Modal
      open onClose={onClose} title="Contact Patient" subtitle={patient?.full_name}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={createComm.isPending} onClick={submit}>Save</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-2">
          {patient?.phone ? (
            <a
              href={`tel:${patient.phone}`}
              onClick={() => setChannel('call')}
              className={cn(
                'flex flex-col items-center gap-1.5 rounded-xl border p-3 text-[13px] font-medium transition-colors',
                channel === 'call' ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-ink-200 text-ink-600 hover:bg-ink-50'
              )}
            >
              <Phone className="h-4 w-4" /> Call {patient.phone}
            </a>
          ) : (
            <button
              type="button"
              disabled
              className="flex cursor-not-allowed flex-col items-center gap-1.5 rounded-xl border border-ink-100 p-3 text-[13px] font-medium text-ink-300"
            >
              <Phone className="h-4 w-4" /> No phone on file
            </button>
          )}
          {patient?.email ? (
            <a
              href={`mailto:${patient.email}`}
              onClick={() => setChannel('email')}
              className={cn(
                'flex flex-col items-center gap-1.5 rounded-xl border p-3 text-[13px] font-medium transition-colors',
                channel === 'email' ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-ink-200 text-ink-600 hover:bg-ink-50'
              )}
            >
              <Mail className="h-4 w-4" /> Email {patient.email}
            </a>
          ) : (
            <button
              type="button"
              disabled
              className="flex cursor-not-allowed flex-col items-center gap-1.5 rounded-xl border border-ink-100 p-3 text-[13px] font-medium text-ink-300"
            >
              <Mail className="h-4 w-4" /> No email on file
            </button>
          )}
        </div>
        <Select label="Outcome" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
          {COMMUNICATION_OUTCOMES.map((o) => <option key={o} value={o}>{o}</option>)}
        </Select>
        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Notes (optional)</span>
          <textarea
            className="min-h-[60px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900"
            value={notes} onChange={(e) => setNotes(e.target.value)}
          />
        </label>
        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            <p className="text-[13.5px] leading-relaxed text-rose-700">{error}</p>
          </div>
        )}
      </div>
    </Modal>
  );
}

function BatchAppointmentRow({
  appt, patientName, doctorName, onOpenPatient, onReschedule, onContact, onEdit,
}: {
  appt: AppointmentOut;
  patientName: string;
  doctorName: string;
  onOpenPatient: () => void;
  onReschedule: () => void;
  onContact: () => void;
  onEdit: () => void;
}) {
  const { toast, can } = useApp();
  const checkIn = useCheckInAppointment();
  const markNotArrived = useMarkNotArrived();
  const updateStatus = useUpdateAppointmentStatus();
  const now = useNowTicker();
  const display = arrivalDisplay(appt, now);
  const canAct = appt.status === 'registered';
  // Both Front Desk and the Prescription Department hold
  // appointments.complete — prescription (dispensing) is the actual last
  // step of a real visit, so it's not exclusive to whoever checked the
  // patient in. Only offered once the patient has actually arrived.
  const canComplete = appt.status === 'arrived' && can('appointments.complete');
  const isNotArrivedFlagged = !!appt.marked_not_arrived_at;
  const needsContact = isNotArrivedFlagged || display.label === 'Late / Awaiting Arrival' || appt.status === 'no_show';

  return (
    <div className="border-b border-ink-100 last:border-0">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <button onClick={onOpenPatient} className="flex min-w-0 items-center gap-3 text-left">
          <Avatar initials={initialsOf(patientName)} size="sm" gradient="from-ink-400 to-ink-600" />
          <div className="min-w-0">
            <p className="truncate text-[14px] font-medium text-ink-900">
              {appt.token_number != null && <span className="tnum mr-1.5 text-ink-400">#{appt.token_number}</span>}
              {patientName}
            </p>
            <p className="tnum text-[12px] text-ink-500">
              {new Date(appt.scheduled_at).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })} · {appt.visit_type} · {doctorName}
              {appt.channel === 'phone' && <Phone className="ml-1 inline h-3 w-3 text-ink-400" />}
            </p>
            {appt.notes && <p className="mt-0.5 truncate text-[12px] italic text-ink-400">{appt.notes}</p>}
          </div>
        </button>
        <div className="flex shrink-0 items-center gap-2">
          <span className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-medium" style={{ backgroundColor: 'rgba(0,0,0,0.03)' }}>
            <span className={cn('h-2 w-2 rounded-full', display.dotClass)} />
            {display.label}
          </span>
          {needsContact && <Button size="sm" variant="ghost" onClick={onContact}>Contact</Button>}
          {canAct && (
            <>
              <Button size="sm" variant="secondary" onClick={() => checkIn.mutate(appt.id)} loading={checkIn.isPending}>Arrived</Button>
              {!isNotArrivedFlagged && (
                <Button
                  size="sm" variant="ghost"
                  onClick={() => markNotArrived.mutate(appt.id, { onError: (e) => toast({ title: 'Could not update', body: e instanceof ApiError ? e.message : undefined, tone: 'error' }) })}
                  loading={markNotArrived.isPending}
                >
                  Not Arrived
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={onReschedule}>Reschedule</Button>
              <Button size="sm" variant="ghost" onClick={onEdit}>Edit</Button>
            </>
          )}
          {canComplete && (
            <Button
              size="sm" variant="primary"
              onClick={() =>
                updateStatus.mutate(
                  { appointmentId: appt.id, status: 'completed' },
                  { onError: (e) => toast({ title: 'Could not mark completed', body: e instanceof ApiError ? e.message : undefined, tone: 'error' }) }
                )
              }
              loading={updateStatus.isPending}
            >
              Mark Completed
            </Button>
          )}
        </div>
      </div>
      {display.graceExpired && (
        <div className="flex flex-wrap items-center justify-between gap-3 bg-rose-50 px-4 py-2.5">
          <p className="flex items-center gap-1.5 text-[12.5px] font-medium text-rose-700">
            <AlertTriangle className="h-3.5 w-3.5" />
            {NOT_ARRIVED_GRACE_PERIOD_MINUTES / 60}h have passed with no arrival — reschedule this appointment?
          </p>
          <div className="flex gap-2">
            <Button size="sm" variant="primary" onClick={onReschedule}>Reschedule Now</Button>
            <Button size="sm" variant="ghost" onClick={onContact}>Contact Patient</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function TodayBatchesView({ day }: { day: string }) {
  const { openPatient } = useApp();
  const groupsQuery = useTodayByBatch(day);
  const patientsQuery = usePatients();
  const doctorsQuery = useDoctors();
  const [rescheduleTarget, setRescheduleTarget] = useState<AppointmentOut | null>(null);
  const [contactTarget, setContactTarget] = useState<AppointmentOut | null>(null);
  const [editTarget, setEditTarget] = useState<AppointmentOut | null>(null);

  const patientNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of patientsQuery.data ?? []) map[p.id] = p.full_name;
    return map;
  }, [patientsQuery.data]);
  const doctorNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const d of doctorsQuery.data ?? []) map[d.id] = d.full_name;
    return map;
  }, [doctorsQuery.data]);

  const groups: BatchGroupOut[] = groupsQuery.data ?? [];

  if (groupsQuery.isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-2xl" />)}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {rescheduleTarget && <RescheduleModal appointment={rescheduleTarget} onClose={() => setRescheduleTarget(null)} />}
      {contactTarget && (
        <ContactPatientModal patientId={contactTarget.patient_id} appointmentId={contactTarget.id} onClose={() => setContactTarget(null)} />
      )}
      {editTarget && (
        <EditAppointmentModal appointment={editTarget} doctors={doctorsQuery.data ?? []} onClose={() => setEditTarget(null)} />
      )}
      {groups.map((group, i) => (
        <Card key={group.batch?.id ?? `unbatched-${i}`} className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-ink-100 bg-ink-50/60 px-4 py-3">
            <div>
              <p className="text-[14px] font-semibold text-ink-900">{group.batch?.name ?? 'Unbatched Appointments'}</p>
              {group.batch && <p className="text-[12px] text-ink-500">{group.batch.visit_types.join(' / ')}</p>}
            </div>
            <span className="tnum text-[12.5px] font-medium text-ink-500">
              {group.booked_count} appointment{group.booked_count === 1 ? '' : 's'}
              {group.remaining !== null && group.batch && (
                <span className={cn('ml-1.5', group.remaining <= 0 ? 'font-semibold text-rose-600' : 'text-ink-400')}>
                  ({group.booked_count}/{group.batch.capacity})
                </span>
              )}
            </span>
          </div>
          {group.appointments.length === 0 ? (
            <p className="px-4 py-6 text-center text-[13.5px] text-ink-500">No appointments scheduled for this batch.</p>
          ) : (
            group.appointments.map((appt) => (
              <BatchAppointmentRow
                key={appt.id}
                appt={appt}
                patientName={patientNameById[appt.patient_id] ?? 'Unknown patient'}
                doctorName={(doctorNameById[appt.doctor_id] ?? 'Unassigned').replace('Dr. ', '')}
                onOpenPatient={() => openPatient(appt.patient_id)}
                onReschedule={() => setRescheduleTarget(appt)}
                onContact={() => setContactTarget(appt)}
                onEdit={() => setEditTarget(appt)}
              />
            ))
          )}
        </Card>
      ))}
    </div>
  );
}

/** Cancelling always needs a reason (the backend records it against the
 * appointment's history), so this collects one the same way every other
 * reason-requiring action in this screen does — a Modal with a required
 * textarea — rather than `window.prompt()`, which isn't just inconsistent
 * with the rest of the app but can throw outright in some embedded/kiosk
 * browser contexts, silently failing the cancel with no feedback at all. */
function CancelAppointmentModal({
  appointment, onClose,
}: {
  appointment: AppointmentOut;
  onClose: () => void;
}) {
  const { toast } = useApp();
  const updateStatus = useUpdateAppointmentStatus();
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    if (!reason.trim()) { setError('A reason for cancelling is required.'); return; }
    setError(null);
    updateStatus.mutate(
      { appointmentId: appointment.id, status: 'cancelled', reason: reason.trim() },
      {
        onSuccess: () => { toast({ title: 'Appointment cancelled', tone: 'success' }); onClose(); },
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not cancel this appointment.'),
      }
    );
  };

  return (
    <Modal
      open onClose={onClose} title="Cancel Appointment" subtitle={appointment.visit_type}
      footer={
        <>
          <Button onClick={onClose}>Back</Button>
          <Button variant="danger" loading={updateStatus.isPending} onClick={submit}>Cancel Appointment</Button>
        </>
      }
    >
      <div className="space-y-4">
        <InfoNote>
          {new Date(appointment.scheduled_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
        </InfoNote>
        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Reason for cancelling</span>
          <textarea
            className="min-h-[70px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900"
            placeholder="Patient requested cancellation…" value={reason} onChange={(e) => setReason(e.target.value)}
          />
        </label>
        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            <p className="text-[13.5px] leading-relaxed text-rose-700">{error}</p>
          </div>
        )}
      </div>
    </Modal>
  );
}

// =========================================================================
// Future Appointment Details
// =========================================================================

function FutureAppointmentsTab() {
  const { openPatient } = useApp();
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [q, setQ] = useState('');
  const [rescheduleTarget, setRescheduleTarget] = useState<AppointmentOut | null>(null);
  const [contactTarget, setContactTarget] = useState<AppointmentOut | null>(null);
  const [cancelTarget, setCancelTarget] = useState<AppointmentOut | null>(null);
  const patientsQuery = usePatients();
  const doctorsQuery = useDoctors();

  const futureQuery = useFutureAppointments({ from_date: fromDate || undefined, to_date: toDate || undefined, q: q || undefined });
  const rows = futureQuery.data ?? [];

  const patientNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of patientsQuery.data ?? []) map[p.id] = p.full_name;
    return map;
  }, [patientsQuery.data]);
  const doctorNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const d of doctorsQuery.data ?? []) map[d.id] = d.full_name;
    return map;
  }, [doctorsQuery.data]);

  return (
    <div className="space-y-4">
      {rescheduleTarget && <RescheduleModal appointment={rescheduleTarget} onClose={() => setRescheduleTarget(null)} />}
      {contactTarget && <ContactPatientModal patientId={contactTarget.patient_id} appointmentId={contactTarget.id} onClose={() => setContactTarget(null)} />}
      {cancelTarget && <CancelAppointmentModal appointment={cancelTarget} onClose={() => setCancelTarget(null)} />}
      <Card className="p-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <Input label="From" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          <Input label="To" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          <div className="flex-1">
            <Input label="Search patient" icon={<Search className="h-3.5 w-3.5" />} value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        </div>
      </Card>
      <Card className="overflow-hidden">
        {rows.length === 0 ? (
          <p className="px-5 py-16 text-center text-[14px] font-medium text-ink-700">No future appointments found.</p>
        ) : (
          rows.map((appt) => (
            <div key={appt.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 px-4 py-3 last:border-0">
              <button onClick={() => openPatient(appt.patient_id)} className="flex min-w-0 items-center gap-3 text-left">
                <Avatar initials={initialsOf(patientNameById[appt.patient_id] ?? '?')} size="sm" gradient="from-ink-400 to-ink-600" />
                <div className="min-w-0">
                  <p className="truncate text-[14px] font-medium text-ink-900">{patientNameById[appt.patient_id] ?? 'Unknown patient'}</p>
                  <p className="tnum text-[12px] text-ink-500">
                    {new Date(appt.scheduled_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })} · {appt.visit_type} · {(doctorNameById[appt.doctor_id] ?? 'Unassigned').replace('Dr. ', '')}
                  </p>
                </div>
              </button>
              <div className="flex shrink-0 items-center gap-2">
                <Badge tone={STATUS_TONE[appt.status] ?? 'neutral'} size="sm">{STATUS_LABEL[appt.status] ?? appt.status}</Badge>
                {appt.status === 'registered' && <Button size="sm" onClick={() => setRescheduleTarget(appt)}>Reschedule</Button>}
                <Button size="sm" variant="ghost" onClick={() => setContactTarget(appt)}>Contact</Button>
                {(appt.status === 'registered' || appt.status === 'arrived' || appt.status === 'waiting') && (
                  <Button size="sm" variant="ghost" onClick={() => setCancelTarget(appt)}>Cancel</Button>
                )}
              </div>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}

// =========================================================================
// Closed Appointment List
// =========================================================================

function ClosedAppointmentsTab() {
  const { openPatient } = useApp();
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const patientsQuery = usePatients();
  const doctorsQuery = useDoctors();

  const closedQuery = useClosedAppointments({
    from_date: fromDate || undefined, to_date: toDate || undefined,
    status: (statusFilter || undefined) as any,
  });
  const rows = closedQuery.data ?? [];

  const patientNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of patientsQuery.data ?? []) map[p.id] = p.full_name;
    return map;
  }, [patientsQuery.data]);
  const doctorNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const d of doctorsQuery.data ?? []) map[d.id] = d.full_name;
    return map;
  }, [doctorsQuery.data]);

  return (
    <div className="space-y-4">
      <Card className="p-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <Input label="From" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          <Input label="To" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          <Select label="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All closed</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="no_show">No Show</option>
          </Select>
        </div>
      </Card>
      <Card className="overflow-hidden">
        {rows.length === 0 ? (
          <p className="px-5 py-16 text-center text-[14px] font-medium text-ink-700">No closed appointments found.</p>
        ) : (
          rows.map((appt) => (
            <button
              key={appt.id}
              onClick={() => openPatient(appt.patient_id)}
              className="flex w-full flex-wrap items-center justify-between gap-3 border-b border-ink-100 px-4 py-3 text-left last:border-0 hover:bg-ink-50/60"
            >
              <div className="flex min-w-0 items-center gap-3">
                <Avatar initials={initialsOf(patientNameById[appt.patient_id] ?? '?')} size="sm" gradient="from-ink-400 to-ink-600" />
                <div className="min-w-0">
                  <p className="truncate text-[14px] font-medium text-ink-900">{patientNameById[appt.patient_id] ?? 'Unknown patient'}</p>
                  <p className="tnum text-[12px] text-ink-500">
                    {new Date(appt.scheduled_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })} · {appt.visit_type} · {(doctorNameById[appt.doctor_id] ?? 'Unassigned').replace('Dr. ', '')}
                  </p>
                  {appt.cancellation_reason && <p className="text-[12px] italic text-ink-400">{appt.cancellation_reason}</p>}
                </div>
              </div>
              <Badge tone={STATUS_TONE[appt.status] ?? 'neutral'} size="sm">{STATUS_LABEL[appt.status] ?? appt.status}</Badge>
            </button>
          ))
        )}
      </Card>
    </div>
  );
}

// =========================================================================
// Phone Call Appointments
// =========================================================================

function PhoneCallBookingForm({ onBooked }: { onBooked: () => void }) {
  const { toast } = useApp();
  const patientsQuery = usePatients();
  const doctorsQuery = useDoctors();
  const createAppointment = useCreateAppointment();
  const [patientId, setPatientId] = useState('');
  const [doctorId, setDoctorId] = useState('');
  const [visitType, setVisitType] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  const visitTypeOptions = useVisitTypeOptions();

  const submit = () => {
    setError(null);
    if (!patientId || !doctorId || !scheduledAt || !visitType) { setError('Patient, doctor, appointment type and date/time are required.'); return; }
    createAppointment.mutate(
      {
        patient_id: patientId, doctor_id: doctorId, scheduled_at: new Date(scheduledAt).toISOString(),
        visit_type: visitType, channel: 'phone', notes: description.trim() || null,
      },
      {
        onSuccess: () => {
          toast({ title: 'Phone call appointment saved', tone: 'success' });
          setPatientId(''); setDoctorId(''); setVisitType(''); setScheduledAt(''); setDescription('');
          onBooked();
        },
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not save this appointment.'),
      }
    );
  };

  return (
    <Card className="space-y-4 p-4">
      <p className="text-[14px] font-semibold text-ink-900">New Phone Call Appointment</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Select label="Patient" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
          <option value="">Select a patient…</option>
          {(patientsQuery.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name} — {p.uhid}</option>)}
        </Select>
        <Select label="Doctor" value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
          <option value="">Select a doctor…</option>
          {(doctorsQuery.data ?? []).map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
        </Select>
        <Select label="Appointment Type" value={visitType} onChange={(e) => setVisitType(e.target.value)}>
          <option value="">Select a visit type…</option>
          {visitTypeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
        </Select>
        <Input label="Date & Time" type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
      </div>
      <label className="block">
        <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Description</span>
        <textarea
          className="min-h-[70px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900"
          value={description} onChange={(e) => setDescription(e.target.value)}
        />
      </label>
      <BatchMismatchWarning visitType={visitType} scheduledAt={scheduledAt} />
      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          <p className="text-[13.5px] leading-relaxed text-rose-700">{error}</p>
        </div>
      )}
      <Button variant="primary" loading={createAppointment.isPending} onClick={submit}>Save</Button>
    </Card>
  );
}

function PhoneCallAppointmentsTab() {
  const { openPatient } = useApp();
  const patientsQuery = usePatients();
  const doctorsQuery = useDoctors();
  const historyQuery = useAppointmentsByChannel({ channel: 'phone' });
  const [showForm, setShowForm] = useState(true);

  const patientNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of patientsQuery.data ?? []) map[p.id] = p.full_name;
    return map;
  }, [patientsQuery.data]);
  const patientPhoneById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of patientsQuery.data ?? []) map[p.id] = p.phone ?? '—';
    return map;
  }, [patientsQuery.data]);
  const doctorNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const d of doctorsQuery.data ?? []) map[d.id] = d.full_name;
    return map;
  }, [doctorsQuery.data]);

  const rows = historyQuery.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button variant="secondary" onClick={() => setShowForm((v) => !v)}>{showForm ? 'Hide form' : 'New Phone Call Appointment'}</Button>
      </div>
      {showForm && <PhoneCallBookingForm onBooked={() => {}} />}

      <div>
        <p className="mb-2 text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-400">Phone Call Appointment Details History</p>
        <Card className="overflow-hidden">
          <div className="hidden grid-cols-[40px_1.6fr_1fr_1fr_1fr_1fr_100px] items-center gap-3 border-b border-ink-200/70 bg-ink-50/60 px-4 py-2.5 md:grid">
            {['#', 'Patient', 'Mobile', 'Type', 'Doctor', 'Date & Time', 'Status'].map((h) => (
              <span key={h} className="text-[11.5px] font-semibold uppercase tracking-[0.08em] text-ink-400">{h}</span>
            ))}
          </div>
          {rows.length === 0 ? (
            <p className="px-5 py-16 text-center text-[14px] font-medium text-ink-700">No phone call appointments found.</p>
          ) : (
            rows.map((appt, i) => (
              <button
                key={appt.id}
                onClick={() => openPatient(appt.patient_id)}
                className="flex w-full flex-col gap-1 border-b border-ink-100 px-4 py-3 text-left last:border-0 hover:bg-ink-50/60 md:grid md:grid-cols-[40px_1.6fr_1fr_1fr_1fr_1fr_100px] md:items-center md:gap-3"
              >
                <span className="tnum text-[13px] text-ink-500">{i + 1}</span>
                <span className="truncate text-[13.5px] font-medium text-ink-900">{patientNameById[appt.patient_id] ?? 'Unknown patient'}</span>
                <span className="tnum text-[13px] text-ink-600">{patientPhoneById[appt.patient_id] ?? '—'}</span>
                <span className="text-[13px] text-ink-600">{appt.visit_type}</span>
                <span className="truncate text-[13px] text-ink-600">{(doctorNameById[appt.doctor_id] ?? 'Unassigned').replace('Dr. ', '')}</span>
                <span className="tnum text-[12.5px] text-ink-500">{new Date(appt.scheduled_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</span>
                <Badge tone={STATUS_TONE[appt.status] ?? 'neutral'} size="sm">{STATUS_LABEL[appt.status] ?? appt.status}</Badge>
              </button>
            ))
          )}
        </Card>
      </div>
    </div>
  );
}

// =========================================================================
// Reminders
// =========================================================================

function NewReminderForm({ onCreated }: { onCreated: () => void }) {
  const { toast } = useApp();
  const patientsQuery = usePatients();
  const createReminder = useCreateReminder();
  const [patientId, setPatientId] = useState('');
  const [reason, setReason] = useState('');
  const [dueAt, setDueAt] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    if (!patientId || !reason.trim() || !dueAt) { setError('Patient, reason and due date/time are required.'); return; }
    createReminder.mutate(
      { patient_id: patientId, reason: reason.trim(), due_at: new Date(dueAt).toISOString() },
      {
        onSuccess: () => {
          toast({ title: 'Reminder created', tone: 'success' });
          setPatientId(''); setReason(''); setDueAt('');
          onCreated();
        },
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not create this reminder.'),
      }
    );
  };

  return (
    <Card className="space-y-4 p-4">
      <p className="text-[14px] font-semibold text-ink-900">New Reminder</p>
      <div className="grid gap-3 sm:grid-cols-3">
        <Select label="Patient" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
          <option value="">Select a patient…</option>
          {(patientsQuery.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.full_name} — {p.uhid}</option>)}
        </Select>
        <Input label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        <Input label="Due date & time" type="datetime-local" value={dueAt} onChange={(e) => setDueAt(e.target.value)} />
      </div>
      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          <p className="text-[13.5px] leading-relaxed text-rose-700">{error}</p>
        </div>
      )}
      <Button variant="primary" loading={createReminder.isPending} onClick={submit}>Save Reminder</Button>
    </Card>
  );
}

function ReminderRow({ reminder, patientName }: { reminder: ReminderOut; patientName: string }) {
  const { toast } = useApp();
  const complete = useCompleteReminder();
  const cancel = useCancelReminder();
  const [contactOpen, setContactOpen] = useState(false);
  const overdue = reminder.status === 'pending' && new Date(reminder.due_at).getTime() < Date.now();

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 px-4 py-3 last:border-0">
      {contactOpen && <ContactPatientModal patientId={reminder.patient_id} appointmentId={reminder.appointment_id} onClose={() => setContactOpen(false)} />}
      <div className="min-w-0">
        <p className="truncate text-[14px] font-medium text-ink-900">{patientName}</p>
        <p className="text-[12.5px] text-ink-500">{reminder.reason}</p>
        <p className={cn('tnum text-[12px]', overdue ? 'font-medium text-rose-600' : 'text-ink-400')}>
          Due {new Date(reminder.due_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Badge tone={reminder.status === 'pending' ? (overdue ? 'attention' : 'scheduled') : reminder.status === 'completed' ? 'completed' : 'cancelled'} size="sm">
          {reminder.status === 'pending' ? (overdue ? 'Overdue' : 'Pending') : reminder.status === 'completed' ? 'Completed' : 'Cancelled'}
        </Badge>
        {reminder.status === 'pending' && (
          <>
            <Button size="sm" variant="ghost" onClick={() => setContactOpen(true)}>Contact</Button>
            <Button size="sm" variant="secondary" onClick={() => complete.mutate(reminder.id)} loading={complete.isPending}>Complete</Button>
            <Button size="sm" variant="ghost" onClick={() => cancel.mutate(reminder.id)} loading={cancel.isPending}>Cancel</Button>
          </>
        )}
      </div>
    </div>
  );
}

function RemindersTab() {
  const patientsQuery = usePatients();
  const [statusFilter, setStatusFilter] = useState<'pending' | 'completed' | 'cancelled'>('pending');
  const remindersQuery = useReminders(statusFilter);
  const rows = remindersQuery.data ?? [];

  const patientNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of patientsQuery.data ?? []) map[p.id] = p.full_name;
    return map;
  }, [patientsQuery.data]);

  return (
    <div className="space-y-4">
      <NewReminderForm onCreated={() => {}} />
      <Card className="p-3">
        <PillFilter
          label="Filter reminders by status"
          value={statusFilter}
          onChange={setStatusFilter}
          options={(['pending', 'completed', 'cancelled'] as const).map((s) => ({ id: s, label: s }))}
        />
      </Card>
      <Card className="overflow-hidden">
        {rows.length === 0 ? (
          <p className="px-5 py-16 text-center text-[14px] font-medium text-ink-700">No reminders found.</p>
        ) : (
          rows.map((r) => <ReminderRow key={r.id} reminder={r} patientName={patientNameById[r.patient_id] ?? 'Unknown patient'} />)
        )}
      </Card>
    </div>
  );
}

const STATUS_FILTERS = ['All', 'registered', 'arrived', 'waiting', 'consultation', 'investigation', 'billing', 'pharmacy', 'follow_up', 'completed', 'cancelled', 'no_show'];

export function Appointments() {
  const { openPatient, can } = useApp();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('All');
  const [doctorFilter, setDoctorFilter] = useState<string | null>(null);
  const [bookingOpen, setBookingOpen] = useState(false);
  const [view, setView] = useState<'batches' | 'list' | 'future' | 'closed' | 'phone' | 'reminders'>('batches');
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  // Future Appointments and Reminders are the prescription department's
  // ahead-of-visit-day workload now, not front desk's — hidden here (and
  // enforced again on the backend via appointments.manage_future /
  // reminders.manage) rather than just left reachable in the UI for a
  // role that no longer has the permission to act on them.
  const canManageFuture = can('appointments.manage_future');
  const canManageReminders = can('reminders.manage');
  const availableTabs = [
    { id: 'batches' as const, label: "Today's Batches" },
    { id: 'list' as const, label: 'Full List' },
    canManageFuture && { id: 'future' as const, label: 'Future Appointments' },
    canManageReminders && { id: 'reminders' as const, label: 'Reminders' },
    { id: 'phone' as const, label: 'Phone Call Appointments' },
    { id: 'closed' as const, label: 'Closed Appointments' },
  ].filter((t): t is { id: typeof view; label: string } => !!t);

  // A role that lost access to whichever tab was last selected (or a
  // stale value from before a permission change) falls back to the one
  // tab everyone with this screen can always see, rather than rendering
  // a tab body for a view no longer in the list above.
  useEffect(() => {
    if (!availableTabs.some((t) => t.id === view)) setView('batches');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canManageFuture, canManageReminders]);

  const appointmentsQuery = useAppointments();
  const patientsQuery = usePatients();
  const doctorsQuery = useDoctors();
  const loading = appointmentsQuery.isLoading;

  const patientNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of patientsQuery.data ?? []) map[p.id] = p.full_name;
    return map;
  }, [patientsQuery.data]);

  const doctors = doctorsQuery.data ?? [];

  const rows = useMemo(() => {
    let r = appointmentsQuery.data ?? [];
    if (status !== 'All') r = r.filter((b) => b.status === status);
    if (doctorFilter) r = r.filter((b) => b.doctor_id === doctorFilter);
    if (q.trim()) {
      const t = q.toLowerCase();
      r = r.filter(
        (b) => (patientNameById[b.patient_id] ?? '').toLowerCase().includes(t) || b.visit_type.toLowerCase().includes(t)
      );
    }
    return r;
  }, [appointmentsQuery.data, q, status, doctorFilter, patientNameById]);

  const metrics = useMemo(() => {
    const all = appointmentsQuery.data ?? [];
    return {
      total: all.length,
      waiting: all.filter((a) => a.status === 'waiting').length,
      completed: all.filter((a) => a.status === 'completed').length,
      cancelled: all.filter((a) => a.status === 'cancelled').length,
      noShow: all.filter((a) => a.status === 'no_show').length,
      inConsultation: all.filter((a) => a.status === 'consultation').length,
    };
  }, [appointmentsQuery.data]);

  const doctorName = (id: string) => doctors.find((d) => d.id === id)?.full_name ?? 'Unassigned';
  const doctorColor = (id: string) => DOCTOR_COLORS[doctors.findIndex((d) => d.id === id) % DOCTOR_COLORS.length] ?? '#78716C';

  return (
    <div className="screen-enter mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6 lg:p-8">
      <BookingModal open={bookingOpen} onClose={() => setBookingOpen(false)} />
      <SectionTitle
        eyebrow="Front Desk"
        title="Appointment Management"
        description="Doctor-wise schedules, walk-ins, online bookings and queue — all in one live book"
        action={
          <Button variant="primary" icon={<CalendarPlus className="h-4 w-4" />} onClick={() => setBookingOpen(true)}>
            Book Appointment
          </Button>
        }
      />

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3 xl:grid-cols-6">
        <MetricTile label="Total Today" value={metrics.total} icon={CalendarClock} tone="bg-brand-50 text-brand-700 ring-brand-600/12" />
        <MetricTile label="In Consultation" value={metrics.inConsultation} icon={Users2} tone="bg-emerald-50 text-emerald-700 ring-emerald-600/12" />
        <MetricTile label="Waiting" value={metrics.waiting} icon={Clock3} tone="bg-amber-50 text-amber-700 ring-amber-600/12" />
        <MetricTile label="Completed" value={metrics.completed} icon={CheckCircle2} tone="bg-sky-50 text-sky-700 ring-sky-600/12" />
        <MetricTile label="Cancelled" value={metrics.cancelled} icon={XCircle} tone="bg-rose-50 text-rose-700 ring-rose-600/12" />
        <MetricTile label="No Shows" value={metrics.noShow} icon={Globe} tone="bg-ink-100 text-ink-600 ring-ink-500/12" />
      </div>

      <Tabs
        tabs={availableTabs}
        active={view}
        onChange={(id) => setView(id as typeof view)}
      />

      {view === 'batches' && <TodayBatchesView day={today} />}
      {view === 'future' && <FutureAppointmentsTab />}
      {view === 'reminders' && <RemindersTab />}
      {view === 'phone' && <PhoneCallAppointmentsTab />}
      {view === 'closed' && <ClosedAppointmentsTab />}

      {view === 'list' && (
        <>
      {/* Doctor schedule strip */}
      <Card className="p-3">
        <div className="scroll-area flex gap-2 overflow-x-auto">
          <button
            onClick={() => setDoctorFilter(null)}
            className={cn(
              'shrink-0 rounded-xl border px-3.5 py-2.5 text-left transition-all',
              !doctorFilter ? 'border-brand-400 bg-brand-50/60' : 'border-ink-200/70 bg-white hover:border-ink-300'
            )}
          >
            <p className="text-[13.5px] font-semibold text-ink-900">All Doctors</p>
            <p className="tnum text-[12px] text-ink-500">{metrics.total} appointments</p>
          </button>
          {doctors.map((d) => {
            const todayCount = (appointmentsQuery.data ?? []).filter((a) => a.doctor_id === d.id).length;
            return (
              <button
                key={d.id}
                onClick={() => setDoctorFilter(d.id)}
                className={cn(
                  'shrink-0 rounded-xl border px-3.5 py-2.5 text-left transition-all',
                  doctorFilter === d.id ? 'border-brand-400 bg-brand-50/60' : 'border-ink-200/70 bg-white hover:border-ink-300'
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: doctorColor(d.id) }} />
                  <p className="whitespace-nowrap text-[13.5px] font-semibold text-ink-900">{d.full_name}</p>
                </div>
                <p className="text-[12px] text-ink-500">{d.department ?? 'Reproductive Medicine'}</p>
                <p className="tnum mt-0.5 text-[12px] font-medium text-ink-600">{todayCount} today</p>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Controls */}
      <Card className="p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="lg:min-w-[240px] lg:flex-1">
            <Input placeholder="Search patient or visit type…" icon={<Search className="h-3.5 w-3.5" />} value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <PillFilter
            label="Filter by status"
            value={status}
            onChange={setStatus}
            options={STATUS_FILTERS.map((s) => ({ id: s, label: s === 'All' ? 'All' : STATUS_LABEL[s] }))}
          />
        </div>
      </Card>

      {/* Book */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="flex items-center gap-4 p-4">
              <Skeleton className="h-10 w-10 rounded-full" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3.5 w-40" />
                <Skeleton className="h-3 w-56" />
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="overflow-hidden">
          <div className="hidden grid-cols-[80px_1.8fr_1.4fr_1fr_1fr_110px] items-center gap-4 border-b border-ink-200/70 bg-ink-50/60 px-5 py-2.5 md:grid">
            {['Time', 'Patient', 'Visit Type', 'Doctor', 'Channel', 'Status'].map((h) => (
              <span key={h} className="text-[12px] font-semibold uppercase tracking-[0.09em] text-ink-400">
                {h}
              </span>
            ))}
          </div>
          <div className="stagger">
            {rows.map((b, i) => {
              const patientName = patientNameById[b.patient_id] ?? 'Unknown patient';
              const time = new Date(b.scheduled_at);
              return (
                <button
                  key={b.id}
                  style={{ ['--i' as string]: i }}
                  onClick={() => openPatient(b.patient_id)}
                  className="flex w-full flex-col gap-2 border-b border-ink-100 px-4 py-3.5 text-left last:border-0 transition-colors hover:bg-ink-50/60 sm:px-5 md:grid md:grid-cols-[80px_1.8fr_1.4fr_1fr_1fr_110px] md:items-center md:gap-4"
                >
                  <span className="tnum text-[14px] font-semibold text-ink-900">
                    {time.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })}
                  </span>
                  <div className="flex items-center gap-3">
                    <Avatar initials={initialsOf(patientName)} size="sm" gradient="from-ink-400 to-ink-600" />
                    <div className="min-w-0">
                      <p className="truncate text-[14px] font-medium text-ink-900">{patientName}</p>
                    </div>
                  </div>
                  <span className="text-[13.5px] text-ink-700">{b.visit_type}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: doctorColor(b.doctor_id) }} />
                    <span className="truncate text-[13px] text-ink-600">{doctorName(b.doctor_id).replace('Dr. ', '')}</span>
                  </div>
                  <span className="text-[13px] text-ink-500">{b.channel.replace('_', ' ')}</span>
                  <Badge tone={STATUS_TONE[b.status] ?? 'neutral'} size="sm">
                    {STATUS_LABEL[b.status] ?? b.status}
                  </Badge>
                </button>
              );
            })}
          </div>
          {rows.length === 0 && (
            <div className="px-5 py-16 text-center">
              <p className="text-[14px] font-medium text-ink-700">No appointments match your filters</p>
            </div>
          )}
        </Card>
      )}
        </>
      )}
    </div>
  );
}
