import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';

export type PurchaseOrderStatus = 'pending_approval' | 'approved' | 'dispatched' | 'received' | 'rejected';

export interface PurchaseOrderOut {
  id: string;
  po_number: string;
  item_description: string;
  supplier: string;
  quantity_ordered: number;
  amount_paise: number;
  status: PurchaseOrderStatus;
}

export function usePurchaseOrders() {
  return useQuery({
    queryKey: ['purchase-orders'],
    queryFn: () => apiFetch<PurchaseOrderOut[]>('/purchasing/orders'),
  });
}

// ------------------------------- vendors --------------------------------- #

export type VendorPaymentType = 'credit' | 'cash' | 'card' | 'cheque' | 'rtgs' | 'transaction';

export interface VendorOut {
  id: string;
  name: string;
  account_code: string;
  city: string | null;
  gst_number: string | null;
  payment_type: VendorPaymentType;
  credit_period_days: number;
  purchase_limit_paise: number | null;
  days_to_deliver: number | null;
  bank_account_number: string | null;
  bank_name: string | null;
  ifsc_code: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  address: string | null;
  is_active: boolean;
}

export interface VendorCreate {
  name: string;
  account_code: string;
  city?: string | null;
  gst_number?: string | null;
  payment_type?: VendorPaymentType;
  credit_period_days?: number;
  purchase_limit_paise?: number | null;
  days_to_deliver?: number | null;
  bank_account_number?: string | null;
  bank_name?: string | null;
  ifsc_code?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  address?: string | null;
}

export function useVendors(includeInactive = false) {
  return useQuery({
    queryKey: ['vendors', includeInactive],
    queryFn: () => apiFetch<VendorOut[]>(`/purchasing/vendors${includeInactive ? '?include_inactive=true' : ''}`),
  });
}

export function useCreateVendor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: VendorCreate) => apiFetch<VendorOut>('/purchasing/vendors', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vendors'] }),
  });
}

export function useUpdateVendor() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ vendorId, ...body }: { vendorId: string } & Partial<VendorCreate> & { is_active?: boolean }) =>
      apiFetch<VendorOut>(`/purchasing/vendors/${vendorId}`, { method: 'PATCH', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['vendors'] }),
  });
}
