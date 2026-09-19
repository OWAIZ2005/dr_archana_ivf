/**
 * TypeScript mirrors of backend Pydantic response/request schemas.
 * Field names match the backend exactly (snake_case) rather than being
 * re-cased, so there's no silent drift between what the API actually
 * returns and what the frontend assumes it returns.
 */

// ---- auth -------------------------------------------------------------

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_seconds: number;
}

export interface UserSummary {
  id: string;
  employee_code: string;
  full_name: string;
  email: string;
  department: string | null;
  is_active: boolean;
  role_code: string;
  /** Permission codes the user's role grants (from GET /auth/me). Used to
   * hide capabilities the user lacks — the backend still enforces every
   * action. Absent when the summary comes from an endpoint that omits it. */
  permissions?: string[];
  /** Settings.IDLE_TIMEOUT_MINUTES, from GET /auth/me only — see
   * lib/idleLock.tsx, which uses this instead of a hardcoded guess. */
  idle_timeout_minutes?: number | null;
}

// ---- patients -----------------------------------------------------------

export interface PatientListRow {
  id: string;
  uhid: string;
  full_name: string;
  date_of_birth: string | null;
  gender: string;
  phone: string | null;
}

export interface PatientSummary {
  id: string;
  uhid: string;
  full_name: string;
  date_of_birth: string | null;
  gender: string;
  blood_group: string | null;
  nationality: string | null;
  is_international: boolean;
  photo_document_id: string | null;
  phone: string | null;
  email: string | null;
  allergies: string | null;
  created_at: string;
}

export interface PatientCreate {
  full_name: string;
  date_of_birth?: string | null;
  gender: string;
  blood_group?: string | null;
  nationality?: string | null;
  is_international?: boolean;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  occupation?: string | null;
  emergency_contact?: string | null;
  referral_source?: string | null;
  allergies?: string | null;
}

export interface CoupleCreate {
  female_patient: PatientCreate;
  male_patient: PatientCreate;
  relationship_info?: string | null;
  infertility_type?: string | null;
  infertility_duration?: string | null;
  previous_iui_cycles?: number;
  previous_ivf_cycles?: number;
  previous_treatment_notes?: string | null;
}

export interface CoupleOut {
  id: string;
  female_patient: PatientSummary;
  male_patient: PatientSummary;
  relationship_info: string | null;
  infertility_type: string | null;
  infertility_duration: string | null;
}

export interface PatientDocumentOut {
  id: string;
  document_type: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  signed: boolean;
  verification_status: 'not_required' | 'pending' | 'verified' | 'rejected';
  verified_by_id: string | null;
  verified_at: string | null;
  created_at: string;
}

// ---- appointments -------------------------------------------------------

export type AppointmentStatus =
  | 'registered'
  | 'arrived'
  | 'waiting'
  | 'consultation'
  | 'investigation'
  | 'billing'
  | 'pharmacy'
  | 'follow_up'
  | 'completed'
  | 'cancelled'
  | 'no_show';
export type AppointmentChannel = 'walk_in' | 'phone' | 'online';

export interface AppointmentOut {
  id: string;
  patient_id: string;
  doctor_id: string;
  scheduled_at: string;
  visit_type: string;
  channel: AppointmentChannel;
  status: AppointmentStatus;
  checked_in_at: string | null;
  cancellation_reason: string | null;
  marked_not_arrived_at: string | null;
  notes: string | null;
  token_number: number | null;
  batch_id: string | null;
}

export const NOT_ARRIVED_GRACE_PERIOD_MINUTES = 120;

export interface AppointmentCreate {
  patient_id: string;
  doctor_id: string;
  scheduled_at: string;
  visit_type: string;
  channel: AppointmentChannel;
  notes?: string | null;
}

export interface AppointmentBatchOut {
  id: string;
  name: string;
  start_time: string;
  end_time: string;
  visit_types: string[];
  display_order: number;
  is_active: boolean;
  capacity: number | null;
}

export interface AppointmentBatchCreate {
  name: string;
  start_time: string;
  end_time: string;
  visit_types: string[];
  display_order?: number;
  capacity?: number | null;
}

export interface AppointmentBatchUpdate {
  name?: string;
  start_time?: string;
  end_time?: string;
  visit_types?: string[];
  display_order?: number;
  is_active?: boolean;
  capacity?: number | null;
}

export interface BatchGroupOut {
  batch: AppointmentBatchOut | null;
  appointments: AppointmentOut[];
  booked_count: number;
  remaining: number | null;
}

export interface AppointmentHistoryOut {
  id: string;
  appointment_id: string;
  old_scheduled_at: string;
  new_scheduled_at: string;
  reason: string | null;
  changed_by_id: string;
  changed_at: string;
}

// ---- reminders ------------------------------------------------------------

export type ReminderStatus = 'pending' | 'completed' | 'cancelled';

export interface ReminderOut {
  id: string;
  patient_id: string;
  appointment_id: string | null;
  reason: string;
  due_at: string;
  status: ReminderStatus;
  notes: string | null;
  created_by_id: string;
  completed_by_id: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ReminderCreate {
  patient_id: string;
  appointment_id?: string | null;
  reason: string;
  due_at: string;
  notes?: string | null;
}

export interface ReminderUpdate {
  reason?: string;
  due_at?: string;
  notes?: string | null;
}

// ---- communications (contact log) -----------------------------------------

export type CommunicationChannel = 'call' | 'email';

export const COMMUNICATION_OUTCOMES = [
  'Patient will attend later',
  'Patient requested rescheduling',
  'Patient cancelled',
  'Unable to reach',
  'Patient confirmed attendance',
  'Other',
] as const;

export interface CommunicationOut {
  id: string;
  patient_id: string;
  appointment_id: string | null;
  channel: CommunicationChannel;
  outcome: string;
  notes: string | null;
  contacted_by_id: string;
  contacted_at: string;
}

export interface CommunicationCreate {
  patient_id: string;
  appointment_id?: string | null;
  channel: CommunicationChannel;
  outcome: string;
  notes?: string | null;
}

// ---- reports/dashboard ----------------------------------------------------

export interface DashboardMetrics {
  appointments_today: number;
  patients_waiting: number;
  active_ivf_cycles: number;
  todays_collection_paise: number;
}

export interface CycleDistributionRow {
  stage: string;
  count: number;
}

export interface OutcomeRow {
  outcome: string;
  count: number;
}

export interface RevenueTrendRow {
  month: string;
  revenue_paise: number;
}

export interface DoctorPerformanceRow {
  doctor_id: string;
  consultations: number;
}
