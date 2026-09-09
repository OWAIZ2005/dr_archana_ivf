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
}

export interface AppointmentCreate {
  patient_id: string;
  doctor_id: string;
  scheduled_at: string;
  visit_type: string;
  channel: AppointmentChannel;
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
