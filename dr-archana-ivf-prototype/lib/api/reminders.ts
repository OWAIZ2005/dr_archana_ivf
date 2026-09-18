import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { ReminderCreate, ReminderOut, ReminderStatus, ReminderUpdate } from './types';

export function useReminders(status?: ReminderStatus, patientId?: string) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (patientId) params.set('patient_id', patientId);
  const qs = params.toString();
  return useQuery({
    queryKey: ['reminders', status ?? 'all', patientId ?? 'all'],
    queryFn: () => apiFetch<ReminderOut[]>(`/reminders${qs ? `?${qs}` : ''}`),
  });
}

function invalidateReminders(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['reminders'] });
}

export function useCreateReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ReminderCreate) => apiFetch<ReminderOut>('/reminders', { method: 'POST', body }),
    onSuccess: () => invalidateReminders(queryClient),
  });
}

export function useUpdateReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ reminderId, ...body }: { reminderId: string } & ReminderUpdate) =>
      apiFetch<ReminderOut>(`/reminders/${reminderId}`, { method: 'PATCH', body }),
    onSuccess: () => invalidateReminders(queryClient),
  });
}

export function useCompleteReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reminderId: string) => apiFetch<ReminderOut>(`/reminders/${reminderId}/complete`, { method: 'POST' }),
    onSuccess: () => invalidateReminders(queryClient),
  });
}

export function useCancelReminder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (reminderId: string) => apiFetch<ReminderOut>(`/reminders/${reminderId}/cancel`, { method: 'POST' }),
    onSuccess: () => invalidateReminders(queryClient),
  });
}
