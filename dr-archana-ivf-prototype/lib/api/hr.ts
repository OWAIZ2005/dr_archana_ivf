import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiUpload, API_BASE, tokenStore } from './client';

export type LeaveStatus = 'pending' | 'approved' | 'rejected';
export type EmploymentStatus = 'active' | 'inactive';
export type AttendanceStatus = 'present' | 'half_day' | 'absent';
export type AttendanceSource = 'manual' | 'biometric_import';
export type AttendanceImportStatus = 'previewed' | 'confirmed';
export type PayrollStatus = 'draft' | 'calculated' | 'approved' | 'paid';

export interface EmployeeOut {
  id: string;
  full_name: string;
  department: string;
  designation: string;
  phone: string | null;
  email: string | null;
  joined_date: string;
  leave_balance_days: number;
  employment_status: EmploymentStatus;
  monthly_salary_rupees: number | null;
  working_hours_per_day: number;
  biometric_id: string | null;
}

export interface EmployeeCreateInput {
  full_name: string;
  department: string;
  designation: string;
  phone?: string | null;
  email?: string | null;
  joined_date: string;
  monthly_salary_rupees?: number | null;
  working_hours_per_day?: number;
  biometric_id?: string | null;
}

export interface EmployeeUpdateInput extends Partial<EmployeeCreateInput> {
  employment_status?: EmploymentStatus;
}

export interface LeaveRequestOut {
  id: string;
  employee_id: string;
  leave_type: string;
  from_date: string;
  to_date: string;
  status: LeaveStatus;
}

export function useEmployees(params?: { department?: string; employment_status?: EmploymentStatus; q?: string }) {
  const qs = new URLSearchParams();
  if (params?.department) qs.set('department', params.department);
  if (params?.employment_status) qs.set('employment_status', params.employment_status);
  if (params?.q) qs.set('q', params.q);
  const suffix = qs.toString() ? `?${qs}` : '';
  return useQuery({
    queryKey: ['employees', params ?? {}],
    queryFn: () => apiFetch<EmployeeOut[]>(`/hr/employees${suffix}`),
  });
}

export function useCreateEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: EmployeeCreateInput) => apiFetch<EmployeeOut>('/hr/employees', { method: 'POST', body: data }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
  });
}

export function useUpdateEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: EmployeeUpdateInput }) =>
      apiFetch<EmployeeOut>(`/hr/employees/${id}`, { method: 'PATCH', body: data }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
  });
}

export function useSetEmployeeActive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      apiFetch<EmployeeOut>(`/hr/employees/${id}/${active ? 'activate' : 'deactivate'}`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
  });
}

export function useLeaveRequests() {
  return useQuery({
    queryKey: ['leave-requests'],
    queryFn: () => apiFetch<LeaveRequestOut[]>('/hr/leave-requests'),
  });
}

export function useDecideLeaveRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ leaveId, approve }: { leaveId: string; approve: boolean }) =>
      apiFetch<LeaveRequestOut>(`/hr/leave-requests/${leaveId}/decide?approve=${approve}`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leave-requests'] });
      queryClient.invalidateQueries({ queryKey: ['employees'] });
    },
  });
}

/* ============================================================
   ATTENDANCE
   ============================================================ */

export interface AttendanceRecordOut {
  id: string;
  employee_id: string;
  attendance_date: string;
  entry_time: string | null;
  exit_time: string | null;
  working_minutes: number | null;
  status: AttendanceStatus;
  source: AttendanceSource;
  missing_entry: boolean;
  missing_exit: boolean;
  resolved_at: string | null;
}

export interface AttendanceImportOut {
  id: string;
  filename: string;
  status: AttendanceImportStatus;
  records_found: number;
  matched_count: number;
  unknown_count: number;
  duplicate_count: number;
  error_count: number;
  created_at: string;
  confirmed_at: string | null;
}

export interface AttendanceImportRowOut {
  id: string;
  row_number: number;
  biometric_id: string;
  employee_id: string | null;
  attendance_date: string | null;
  entry_time: string | null;
  exit_time: string | null;
  is_unknown: boolean;
  is_duplicate: boolean;
  error: string | null;
}

export function useAttendanceRecords(params?: { from_date?: string; to_date?: string; department?: string; employee_id?: string; status?: AttendanceStatus }) {
  const qs = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([k, v]) => v && qs.set(k, v));
  const suffix = qs.toString() ? `?${qs}` : '';
  return useQuery({
    queryKey: ['attendance-records', params ?? {}],
    queryFn: () => apiFetch<AttendanceRecordOut[]>(`/hr/attendance/records${suffix}`),
  });
}

export function useAttendanceIssues() {
  return useQuery({
    queryKey: ['attendance-issues'],
    queryFn: () => apiFetch<AttendanceRecordOut[]>('/hr/attendance/issues'),
  });
}

export function useResolveAttendanceRecord() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (recordId: string) => apiFetch<AttendanceRecordOut>(`/hr/attendance/records/${recordId}/resolve`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attendance-issues'] });
      queryClient.invalidateQueries({ queryKey: ['attendance-records'] });
    },
  });
}

export function useUploadAttendanceImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return apiUpload<AttendanceImportOut>('/hr/attendance/imports', form);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['attendance-imports'] }),
  });
}

export function useAttendanceImportRows(importId: string | null) {
  return useQuery({
    queryKey: ['attendance-import-rows', importId],
    queryFn: () => apiFetch<AttendanceImportRowOut[]>(`/hr/attendance/imports/${importId}/rows`),
    enabled: !!importId,
  });
}

export function useConfirmAttendanceImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (importId: string) => apiFetch<AttendanceImportOut>(`/hr/attendance/imports/${importId}/confirm`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attendance-records'] });
      queryClient.invalidateQueries({ queryKey: ['attendance-issues'] });
      queryClient.invalidateQueries({ queryKey: ['hr-dashboard'] });
    },
  });
}

export type AttendancePeriodStatus = 'open' | 'finalized';

export interface MonthlyAttendanceRowOut {
  employee_id: string;
  full_name: string;
  department: string;
  days: Record<number, string | null>;
  working_days: number;
  processed_days: number;
  unprocessed_days: number;
  present_days: number;
  half_days: number;
  absent_days: number;
  attendance_percent: number;
  is_complete: boolean;
}

export interface AttendancePeriodOut {
  month: number;
  year: number;
  status: AttendancePeriodStatus;
  finalized_at: string | null;
  finalized_by_id: string | null;
  override_used: boolean;
  override_reason: string | null;
}

export interface PeriodSummaryOut {
  period: AttendancePeriodOut;
  working_days: number;
  processed_days: number;
  unprocessed_days: number;
  present_days: number;
  half_days: number;
  absent_days: number;
  employee_count: number;
}

export function useMonthlyAttendance(params: { month: number; year: number; department?: string; employee_id?: string }) {
  const qs = new URLSearchParams();
  qs.set('month', String(params.month));
  qs.set('year', String(params.year));
  if (params.department) qs.set('department', params.department);
  if (params.employee_id) qs.set('employee_id', params.employee_id);
  return useQuery({
    queryKey: ['attendance-monthly', params],
    queryFn: () => apiFetch<MonthlyAttendanceRowOut[]>(`/hr/attendance/monthly?${qs}`),
  });
}

export function usePeriodSummary(year: number, month: number) {
  return useQuery({
    queryKey: ['attendance-period', year, month],
    queryFn: () => apiFetch<PeriodSummaryOut>(`/hr/attendance/periods/${year}/${month}`),
  });
}

export function useFinalizePeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ year, month, override, reason }: { year: number; month: number; override?: boolean; reason?: string }) =>
      apiFetch<AttendancePeriodOut>(`/hr/attendance/periods/${year}/${month}/finalize`, { method: 'POST', body: { override: !!override, reason: reason ?? null } }),
    onSuccess: (_, { year, month }) => {
      queryClient.invalidateQueries({ queryKey: ['attendance-period', year, month] });
      queryClient.invalidateQueries({ queryKey: ['attendance-monthly'] });
      queryClient.invalidateQueries({ queryKey: ['payroll'] });
    },
  });
}

export function useReopenPeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ year, month }: { year: number; month: number }) =>
      apiFetch<AttendancePeriodOut>(`/hr/attendance/periods/${year}/${month}/reopen`, { method: 'POST' }),
    onSuccess: (_, { year, month }) => {
      queryClient.invalidateQueries({ queryKey: ['attendance-period', year, month] });
      queryClient.invalidateQueries({ queryKey: ['attendance-monthly'] });
      queryClient.invalidateQueries({ queryKey: ['payroll'] });
    },
  });
}

/* ============================================================
   PAYROLL
   ============================================================ */

export interface PayrollOut {
  id: string;
  employee_id: string;
  month: number;
  year: number;
  base_salary_rupees: number;
  working_days: number;
  present_days: number;
  half_days: number;
  absent_days: number;
  payable_days: number;
  per_day_rupees: number;
  deduction_rupees: number;
  overtime_hours: number;
  overtime_amount_rupees: number;
  net_salary_rupees: number;
  status: PayrollStatus;
  calculated_at: string;
  approved_at: string | null;
  paid_at: string | null;
}

export function usePayrollList(params?: { month?: number; year?: number; department?: string; employee_id?: string }) {
  const qs = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([k, v]) => v !== undefined && v !== '' && qs.set(k, String(v)));
  const suffix = qs.toString() ? `?${qs}` : '';
  return useQuery({
    queryKey: ['payroll', params ?? {}],
    queryFn: () => apiFetch<PayrollOut[]>(`/hr/payroll${suffix}`),
  });
}

export function useCalculatePayroll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { employee_id: string; month: number; year: number }) =>
      apiFetch<PayrollOut>('/hr/payroll/calculate', { method: 'POST', body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payroll'] });
      queryClient.invalidateQueries({ queryKey: ['hr-dashboard'] });
    },
  });
}

export function useApprovePayroll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payrollId: string) => apiFetch<PayrollOut>(`/hr/payroll/${payrollId}/approve`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['payroll'] }),
  });
}

export function useMarkPayrollPaid() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payrollId: string) => apiFetch<PayrollOut>(`/hr/payroll/${payrollId}/mark-paid`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['payroll'] }),
  });
}

/* ============================================================
   PATIENT PROCESS / DELAYS
   ============================================================ */

export interface StageFlowOut {
  stage: string;
  threshold_minutes: number;
  normal: number;
  warning: number;
  delayed: number;
  critical: number;
  total: number;
}

export interface PatientDelayOut {
  appointment_id: string;
  event_id: string | null;
  patient_id: string;
  patient_name: string;
  stage: string;
  started_at: string;
  threshold_minutes: number;
  actual_minutes: number;
  delay_minutes: number;
  severity: 'normal' | 'warning' | 'delayed' | 'critical';
  doctor_name: string;
  delay_reason: string | null;
}

export function useProcessFlow() {
  return useQuery({
    queryKey: ['process-flow'],
    queryFn: () => apiFetch<StageFlowOut[]>('/hr/process/flow'),
    refetchInterval: 30000,
  });
}

export function useDelays(onlyDelayed = true) {
  return useQuery({
    queryKey: ['process-delays', onlyDelayed],
    queryFn: () => apiFetch<PatientDelayOut[]>(`/hr/process/delays?only_delayed=${onlyDelayed}`),
    refetchInterval: 30000,
  });
}

export function useProcessThresholds() {
  return useQuery({
    queryKey: ['process-thresholds'],
    queryFn: () => apiFetch<{ thresholds: Record<string, number> }>('/hr/process/thresholds'),
  });
}

export function useUpdateProcessThresholds() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (thresholds: Record<string, number>) =>
      apiFetch<{ thresholds: Record<string, number> }>('/hr/process/thresholds', { method: 'PUT', body: { thresholds } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['process-thresholds'] });
      queryClient.invalidateQueries({ queryKey: ['process-flow'] });
      queryClient.invalidateQueries({ queryKey: ['process-delays'] });
    },
  });
}

export function useDelayReasons() {
  return useQuery({ queryKey: ['delay-reasons'], queryFn: () => apiFetch<string[]>('/hr/process/delay-reasons') });
}

export function useSetDelayReason() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ eventId, reason }: { eventId: string; reason: string }) =>
      apiFetch(`/hr/process/events/${eventId}/reason`, { method: 'POST', body: { reason } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['process-delays'] }),
  });
}

/* ============================================================
   SETTINGS
   ============================================================ */

export interface HrSettingsOut {
  full_day_hours: number;
  half_day_min_hours: number;
  late_arrival_grace_minutes: number;
  early_departure_grace_minutes: number;
  standard_start_time: string;
  standard_end_time: string;
  working_days_per_month: number;
  half_day_pay_fraction: number;
  absent_day_pay_fraction: number;
  overtime_rate_per_hour_rupees: number;
  updated_at: string;
}

export function useHrSettings() {
  return useQuery({ queryKey: ['hr-settings'], queryFn: () => apiFetch<HrSettingsOut>('/hr/settings') });
}

export function useUpdateHrSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<HrSettingsOut>) => apiFetch<HrSettingsOut>('/hr/settings', { method: 'PUT', body: data }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hr-settings'] }),
  });
}

/* ============================================================
   ALERTS
   ============================================================ */

export interface HrAlertOut {
  key: string;
  severity: 'critical' | 'warning';
  category: string;
  title: string;
  body: string;
}

export function useHrAlerts() {
  return useQuery({ queryKey: ['hr-alerts'], queryFn: () => apiFetch<HrAlertOut[]>('/hr/alerts'), refetchInterval: 30000 });
}

export function useResolveHrAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => apiFetch(`/hr/alerts/${encodeURIComponent(key)}/resolve`, { method: 'POST', body: {} }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hr-alerts'] }),
  });
}

/* ============================================================
   DASHBOARD
   ============================================================ */

export interface HrDashboardOut {
  employees: {
    total_employees: number;
    present_today: number;
    half_day_today: number;
    absent_today: number;
    late_arrivals: number;
    currently_inside: number;
  };
  attendance: {
    attendance_percent: number;
    avg_working_hours: number;
    total_overtime_hours: number;
  };
  payroll: {
    current_month_calculated: number;
    pending_approval: number;
    total_salary_this_month_rupees: number;
    employees_with_deductions: number;
  };
  patient_ops: {
    patients_in_process: number;
    avg_waiting_time_minutes: number;
    avg_consultation_time_minutes: number;
    avg_pharmacy_time_minutes: number;
    active_delays: number;
    critical_delays: number;
  };
}

export function useHrDashboard() {
  return useQuery({ queryKey: ['hr-dashboard'], queryFn: () => apiFetch<HrDashboardOut>('/hr/dashboard/summary'), refetchInterval: 30000 });
}

/* ============================================================
   REPORTS (CSV export — direct authenticated download)
   ============================================================ */

export async function downloadHrReport(path: string, filename: string) {
  const token = tokenStore.get();
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Report export failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
