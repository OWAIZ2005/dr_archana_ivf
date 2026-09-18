import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { AppointmentBatchOut, AppointmentCreate, AppointmentHistoryOut, AppointmentOut, AppointmentStatus, BatchGroupOut } from './types';

export function useAppointments(day?: string, status?: AppointmentStatus) {
  const params = new URLSearchParams();
  if (day) params.set('day', day);
  if (status) params.set('status', status);
  const qs = params.toString();
  return useQuery({
    queryKey: ['appointments', day ?? 'today', status ?? 'all'],
    queryFn: () => apiFetch<AppointmentOut[]>(`/appointments${qs ? `?${qs}` : ''}`),
  });
}

export function usePatientAppointments(patientId: string | null) {
  return useQuery({
    queryKey: ['appointments-by-patient', patientId],
    queryFn: () => apiFetch<AppointmentOut[]>(`/appointments/by-patient/${patientId}`),
    enabled: !!patientId,
  });
}

function invalidateAppointmentQueries(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['appointments'] });
  queryClient.invalidateQueries({ queryKey: ['appointments-today-by-batch'] });
  queryClient.invalidateQueries({ queryKey: ['appointments-by-patient'] });
  queryClient.invalidateQueries({ queryKey: ['appointments-future'] });
  queryClient.invalidateQueries({ queryKey: ['appointments-closed'] });
  queryClient.invalidateQueries({ queryKey: ['appointments-by-channel'] });
}

export function useCreateAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AppointmentCreate) => apiFetch<AppointmentOut>('/appointments', { method: 'POST', body }),
    onSuccess: () => invalidateAppointmentQueries(queryClient),
  });
}

export function useCheckInAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (appointmentId: string) =>
      apiFetch<AppointmentOut>(`/appointments/${appointmentId}/check-in`, { method: 'POST' }),
    onSuccess: () => invalidateAppointmentQueries(queryClient),
  });
}

export function useEditAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ appointmentId, ...body }: { appointmentId: string; visit_type?: string; doctor_id?: string; notes?: string | null }) =>
      apiFetch<AppointmentOut>(`/appointments/${appointmentId}`, { method: 'PATCH', body }),
    onSuccess: () => invalidateAppointmentQueries(queryClient),
  });
}

export function useMarkNotArrived() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (appointmentId: string) =>
      apiFetch<AppointmentOut>(`/appointments/${appointmentId}/not-arrived`, { method: 'POST' }),
    onSuccess: () => invalidateAppointmentQueries(queryClient),
  });
}

export function useClearNotArrived() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (appointmentId: string) =>
      apiFetch<AppointmentOut>(`/appointments/${appointmentId}/clear-not-arrived`, { method: 'POST' }),
    onSuccess: () => invalidateAppointmentQueries(queryClient),
  });
}

export function useUpdateAppointmentStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ appointmentId, status, reason }: { appointmentId: string; status: AppointmentStatus; reason?: string | null }) =>
      apiFetch<AppointmentOut>(`/appointments/${appointmentId}/status`, { method: 'POST', body: { status, reason: reason ?? null } }),
    onSuccess: () => invalidateAppointmentQueries(queryClient),
  });
}

export function useRescheduleAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ appointmentId, new_scheduled_at, reason }: { appointmentId: string; new_scheduled_at: string; reason: string }) =>
      apiFetch<AppointmentOut>(`/appointments/${appointmentId}/reschedule`, { method: 'POST', body: { new_scheduled_at, reason } }),
    onSuccess: () => invalidateAppointmentQueries(queryClient),
  });
}

export function useAppointmentHistory(appointmentId: string | null) {
  return useQuery({
    queryKey: ['appointment-history', appointmentId],
    queryFn: () => apiFetch<AppointmentHistoryOut[]>(`/appointments/${appointmentId}/history`),
    enabled: !!appointmentId,
  });
}

export function useAppointmentBatches() {
  return useQuery({
    queryKey: ['appointment-batches'],
    queryFn: () => apiFetch<AppointmentBatchOut[]>('/appointments/batches'),
    staleTime: 5 * 60_000,
  });
}

export function useTodayByBatch(day?: string) {
  const qs = day ? `?day=${day}` : '';
  return useQuery({
    queryKey: ['appointments-today-by-batch', day ?? 'today'],
    queryFn: () => apiFetch<BatchGroupOut[]>(`/appointments/today-by-batch${qs}`),
  });
}

export interface AppointmentListFilters {
  from_date?: string;
  to_date?: string;
  doctor_id?: string;
  status?: AppointmentStatus;
  channel?: string;
  q?: string;
}

function toQueryString(filters: AppointmentListFilters): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) if (v) params.set(k, v);
  const qs = params.toString();
  return qs ? `?${qs}` : '';
}

export function useFutureAppointments(filters: AppointmentListFilters = {}) {
  return useQuery({
    queryKey: ['appointments-future', filters],
    queryFn: () => apiFetch<AppointmentOut[]>(`/appointments/future${toQueryString(filters)}`),
  });
}

export function useClosedAppointments(filters: AppointmentListFilters = {}) {
  return useQuery({
    queryKey: ['appointments-closed', filters],
    queryFn: () => apiFetch<AppointmentOut[]>(`/appointments/closed${toQueryString(filters)}`),
  });
}

export function useAppointmentsByChannel(filters: AppointmentListFilters & { channel: string }) {
  return useQuery({
    queryKey: ['appointments-by-channel', filters],
    queryFn: () => apiFetch<AppointmentOut[]>(`/appointments/by-channel${toQueryString(filters)}`),
  });
}
