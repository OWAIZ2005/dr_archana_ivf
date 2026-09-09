import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { AppointmentCreate, AppointmentOut, AppointmentStatus } from './types';

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

export function useCreateAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AppointmentCreate) => apiFetch<AppointmentOut>('/appointments', { method: 'POST', body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['appointments'] }),
  });
}

export function useCheckInAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (appointmentId: string) =>
      apiFetch<AppointmentOut>(`/appointments/${appointmentId}/check-in`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['appointments'] }),
  });
}
