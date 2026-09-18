import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { CommunicationCreate, CommunicationOut } from './types';

export function usePatientCommunications(patientId: string | null) {
  return useQuery({
    queryKey: ['communications', patientId],
    queryFn: () => apiFetch<CommunicationOut[]>(`/communications?patient_id=${patientId}`),
    enabled: !!patientId,
  });
}

export function useCreateCommunication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CommunicationCreate) => apiFetch<CommunicationOut>('/communications', { method: 'POST', body }),
    onSuccess: (_, vars) => queryClient.invalidateQueries({ queryKey: ['communications', vars.patient_id] }),
  });
}
