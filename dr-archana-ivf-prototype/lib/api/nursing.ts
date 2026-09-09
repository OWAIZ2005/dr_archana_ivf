import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';

export interface NursingRecordOut {
  id: string;
  patient_id: string;
  appointment_id: string | null;
  recorded_by_id: string;
  recorded_by_name: string | null;
  blood_pressure_systolic: number | null;
  blood_pressure_diastolic: number | null;
  temperature: number | null;
  notes: string | null;
  recorded_at: string;
  created_at: string;
}

export interface NursingRecordCreate {
  patient_id: string;
  appointment_id?: string | null;
  blood_pressure_systolic?: number | null;
  blood_pressure_diastolic?: number | null;
  temperature?: number | null;
  notes?: string | null;
}

export function useNursingRecords(patientId: string | null) {
  return useQuery({
    queryKey: ['nursing-records', patientId],
    queryFn: () => apiFetch<NursingRecordOut[]>(`/nursing/patients/${patientId}/records`),
    enabled: !!patientId,
  });
}

export function useCreateNursingRecord() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: NursingRecordCreate) =>
      apiFetch<NursingRecordOut>('/nursing/records', { method: 'POST', body }),
    onSuccess: (_, vars) =>
      queryClient.invalidateQueries({ queryKey: ['nursing-records', vars.patient_id] }),
  });
}
