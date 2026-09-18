import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { CoupleCreate, CoupleOut, PatientCreate, PatientDocumentOut, PatientListRow, PatientSummary } from './types';

export function usePatients(search?: string) {
  return useQuery({
    queryKey: ['patients', search ?? ''],
    queryFn: () =>
      apiFetch<PatientListRow[]>(`/patients${search ? `?search=${encodeURIComponent(search)}` : ''}`),
  });
}

/** Single-patient registration — for a front-desk walk-in/phone booking
 * that isn't part of an IVF couple record. Distinct from useCreateCouple,
 * which always creates two linked patients. */
export function useCreatePatient() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PatientCreate) => apiFetch<PatientSummary>('/patients', { method: 'POST', body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patients'] }),
  });
}

export function usePatientSummary(patientId: string | null) {
  return useQuery({
    queryKey: ['patient-summary', patientId],
    queryFn: () => apiFetch<PatientSummary>(`/patients/${patientId}/summary`),
    enabled: !!patientId,
  });
}

export function useCoupleForPatient(patientId: string | null) {
  return useQuery({
    queryKey: ['couple-for-patient', patientId],
    queryFn: () => apiFetch<CoupleOut | null>(`/patients/couples/by-patient/${patientId}`),
    enabled: !!patientId,
  });
}

export function usePatientDocuments(patientId: string | null) {
  return useQuery({
    queryKey: ['patient-documents', patientId],
    queryFn: () => apiFetch<PatientDocumentOut[]>(`/patients/${patientId}/documents`),
    enabled: !!patientId,
  });
}

export function useCreateCouple() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: CoupleCreate) => apiFetch<CoupleOut>('/patients/couples', { method: 'POST', body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
    },
  });
}

// ---- Mandatory documents (Aadhaar / visa) & visa support ----

export interface MandatoryDocumentStatus {
  patient_id: string;
  required_document_type: string;
  is_uploaded: boolean;
  is_verified: boolean;
}

export function useMandatoryDocumentStatus(patientId: string | null) {
  return useQuery({
    queryKey: ['mandatory-documents', patientId],
    queryFn: () => apiFetch<MandatoryDocumentStatus>(`/patients/${patientId}/mandatory-documents`),
    enabled: !!patientId,
  });
}

export type VisaSupportStatus = 'requested' | 'in_progress' | 'completed' | 'cancelled';

export interface VisaSupportRequestOut {
  id: string;
  patient_id: string;
  request_type: string;
  status: VisaSupportStatus;
  notes: string | null;
  handled_by_id: string | null;
  created_at: string;
}

export function useVisaSupportRequests(patientId: string | null) {
  return useQuery({
    queryKey: ['visa-support', patientId],
    queryFn: () => apiFetch<VisaSupportRequestOut[]>(`/patients/${patientId}/visa-support`),
    enabled: !!patientId,
  });
}

export function useCreateVisaSupportRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { patient_id: string; request_type: string; notes?: string | null }) =>
      apiFetch<VisaSupportRequestOut>('/patients/visa-support', { method: 'POST', body }),
    onSuccess: (_, vars) => queryClient.invalidateQueries({ queryKey: ['visa-support', vars.patient_id] }),
  });
}

export function useUpdateVisaSupportStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ requestId, status, notes }: { requestId: string; status: VisaSupportStatus; notes?: string | null }) =>
      apiFetch<VisaSupportRequestOut>(`/patients/visa-support/${requestId}/status`, { method: 'POST', body: { status, notes } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['visa-support'] }),
  });
}

export function useVerifyDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ documentId, approve, notes }: { documentId: string; approve: boolean; notes?: string | null }) =>
      apiFetch(`/patients/documents/${documentId}/verify`, { method: 'POST', body: { approve, notes } }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patient-documents'] });
      queryClient.invalidateQueries({ queryKey: ['mandatory-documents'] });
    },
  });
}

// ---- Document upload (multipart — bypasses apiFetch's JSON-only body) ----

export async function uploadPatientDocument(patientId: string, documentType: string, file: File): Promise<{ id: string; document_type: string; filename: string }> {
  const { API_BASE, tokenStore } = await import('./client');
  const token = tokenStore.get();
  const form = new FormData();
  form.append('file', file);

  const res = await fetch(`${API_BASE}/patients/${patientId}/documents?document_type=${encodeURIComponent(documentType)}`, {
    method: 'POST',
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    throw new Error(payload?.message ?? `Upload failed (HTTP ${res.status})`);
  }
  return res.json();
}

export function useUploadPatientDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ patientId, documentType, file }: { patientId: string; documentType: string; file: File }) =>
      uploadPatientDocument(patientId, documentType, file),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ['patient-documents', vars.patientId] });
      queryClient.invalidateQueries({ queryKey: ['mandatory-documents', vars.patientId] });
      queryClient.invalidateQueries({ queryKey: ['patient-summary', vars.patientId] });
    },
  });
}
