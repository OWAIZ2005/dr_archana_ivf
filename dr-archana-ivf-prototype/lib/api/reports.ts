import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiFetchBlob } from './client';
import type { CycleDistributionRow, DashboardMetrics, DoctorPerformanceRow, OutcomeRow, RevenueTrendRow } from './types';

export function useDashboardMetrics() {
  return useQuery({
    queryKey: ['dashboard-metrics'],
    queryFn: () => apiFetch<DashboardMetrics>('/reports/dashboard'),
    refetchInterval: 60_000,
  });
}

export function useCycleDistribution() {
  return useQuery({
    queryKey: ['cycle-distribution'],
    queryFn: () => apiFetch<CycleDistributionRow[]>('/reports/cycle-distribution'),
  });
}

export function useOutcomes(fromDate: string, toDate: string) {
  return useQuery({
    queryKey: ['outcomes', fromDate, toDate],
    queryFn: () => apiFetch<OutcomeRow[]>(`/reports/outcomes?from_date=${fromDate}&to_date=${toDate}`),
  });
}

export function useRevenueTrend(months = 6) {
  return useQuery({
    queryKey: ['revenue-trend', months],
    queryFn: () => apiFetch<RevenueTrendRow[]>(`/reports/revenue-trend?months=${months}`),
  });
}

export function useDoctorPerformance() {
  return useQuery({
    queryKey: ['doctor-performance'],
    queryFn: () => apiFetch<DoctorPerformanceRow[]>('/reports/doctor-performance'),
  });
}

// ---- Discharge summary ----

export interface DischargeSummary {
  patient: { id: string; uhid: string; full_name: string; date_of_birth: string | null };
  couple: { id: string; partner_name: string } | null;
  cycles: { id: string; cycle_number: string; protocol: string; treatment: string; stage: string; started_at: string }[];
  consultations: { id: string; type: string; notes: string; date: string }[];
  investigations: { id: string; test_name: string; status: string; date: string }[];
  prescriptions: { id: string; category: string | null; line_count: number; date: string }[];
  monitoring_visits: { id: string; cycle_day: number; date: string; endometrium_mm: number; doctor_note: string | null }[];
  injections: { id: string; medicine_name: string; dose: string; status: string; administered_at: string | null }[];
  oocyte_assessments: { id: string; retrieval_date: string; oocytes_retrieved: number; mature_oocytes: number; normally_fertilised: number }[];
  embryos: { id: string; label: string; day: number; grade: string; status: string }[];
  embryo_transfers: { id: string; transfer_date: string; completed: boolean }[];
  current_storage: { id: string; address: string; embryo_id: string }[];
  pregnancy_outcomes: { id: string; outcome: string; transfer_date: string | null; estimated_due_date: string | null }[];
}

export function useDischargeSummary(patientId: string | null) {
  return useQuery({
    queryKey: ['discharge-summary', patientId],
    queryFn: () => apiFetch<DischargeSummary>(`/reports/discharge-summary/${patientId}`),
    enabled: !!patientId,
  });
}

// ===========================================================================
// Asynchronous report-generation jobs (Celery). Distinct from the live
// analytics endpoints above: a job is queued, a worker builds an artifact in
// the background, and the client polls for status then downloads.
// ===========================================================================

export type ReportJobType = 'patient_summary' | 'discharge_summary';
export type ReportJobStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export interface ReportJob {
  id: string;
  report_type: ReportJobType;
  parameters: Record<string, unknown>;
  status: ReportJobStatus;
  requested_by_id: string;
  error: string | null;
  content_type: string | null;
  byte_size: number | null;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface ReportJobPage {
  items: ReportJob[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface SubmitReportJobBody {
  report_type: ReportJobType;
  parameters: Record<string, unknown>;
  options?: { simulate_work_seconds?: number };
}

export function useReportJobs(status?: ReportJobStatus) {
  return useQuery({
    queryKey: ['report-jobs', status ?? 'all'],
    queryFn: () => apiFetch<ReportJobPage>(`/reports/jobs${status ? `?status=${status}` : ''}`),
  });
}

/** Polls one job until it reaches a terminal state, then stops on its own. */
export function useReportJob(jobId: string | null) {
  return useQuery({
    queryKey: ['report-job', jobId],
    queryFn: () => apiFetch<ReportJob>(`/reports/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const s = (query.state.data as ReportJob | undefined)?.status;
      return s === 'succeeded' || s === 'failed' ? false : 1500;
    },
  });
}

export function useSubmitReportJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmitReportJobBody) =>
      apiFetch<ReportJob>('/reports/jobs', { method: 'POST', body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['report-jobs'] }),
  });
}

/** Downloads a finished job's artifact as a Blob. */
export function fetchReportJobResult(jobId: string): Promise<Blob> {
  return apiFetchBlob(`/reports/jobs/${jobId}/result`);
}
