import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';

export interface MedicineOut {
  id: string;
  generic_name: string;
  brand_name: string | null;
  category: string | null;
  unit: string;
  reorder_level: number;
  total_available: number;
}

export interface SaleLineOut {
  id: string;
  medicine_id: string;
  batch_id: string;
  quantity: number;
  unit_price_paise: number;
}

export type PaymentMethod = 'cash' | 'card' | 'cheque' | 'online';

export interface SaleOut {
  id: string;
  bill_number: string;
  patient_id: string;
  prescribed_by_id: string | null;
  total_amount_paise: number;
  discount_paise: number;
  payment_method: PaymentMethod;
  status: string;
  created_at: string;
  lines: SaleLineOut[];
}

export function useMedicines() {
  return useQuery({
    queryKey: ['medicines'],
    queryFn: () => apiFetch<MedicineOut[]>('/pharmacy/medicines'),
  });
}

export function usePharmacySales() {
  return useQuery({
    queryKey: ['pharmacy-sales'],
    queryFn: () => apiFetch<SaleOut[]>('/pharmacy/sales'),
  });
}

// -------------------------------- billing ---------------------------------- #

export interface DispenseLineInput {
  medicine_id: string;
  quantity: number;
}

export interface DispenseRequest {
  patient_id: string;
  prescribed_by_id?: string | null;
  lines: DispenseLineInput[];
  discount_paise?: number;
  payment_method?: PaymentMethod;
}

/** Records a bill — the same FEFO-safe, idempotent, transactional stock
 * deduction the existing "Recent Dispensing" list already reads from.
 * No parallel billing/stock-deduction path is created here. */
export function useDispenseSale() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DispenseRequest) =>
      apiFetch<SaleOut>('/pharmacy/dispense', {
        method: 'POST',
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pharmacy-sales'] });
      qc.invalidateQueries({ queryKey: ['medicines'] });
      qc.invalidateQueries({ queryKey: ['pharmacy-stock'] });
    },
  });
}

// ---------------------------- medicine attributes ------------------------- #

export interface MedicineAttributeOut {
  id: string;
  attribute_type: string;
  name: string;
  description: string | null;
  is_active: boolean;
}

export function useMedicineAttributes(attributeType?: string) {
  return useQuery({
    queryKey: ['medicine-attributes', attributeType],
    queryFn: () =>
      apiFetch<MedicineAttributeOut[]>(`/pharmacy/attributes${attributeType ? `?attribute_type=${attributeType}` : ''}`),
  });
}

export function useCreateMedicineAttribute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { attribute_type: string; name: string; description?: string | null }) =>
      apiFetch<MedicineAttributeOut>('/pharmacy/attributes', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['medicine-attributes'] }),
  });
}

export function useUpdateMedicineAttribute() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; description?: string | null; is_active?: boolean }) =>
      apiFetch<MedicineAttributeOut>(`/pharmacy/attributes/${id}`, { method: 'PATCH', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['medicine-attributes'] }),
  });
}

// -------------------------------- medicine --------------------------------- #

export interface BatchOut {
  id: string;
  batch_number: string;
  expiry_date: string;
  quantity_available: number;
  selling_rate_paise: number;
}

export interface MedicineDetailOut {
  id: string;
  generic_name: string;
  brand_name: string | null;
  manufacturer: string | null;
  strength: string | null;
  dosage_form: string | null;
  category: string | null;
  unit: string;
  hsn_code: string | null;
  gst_percent: number;
  purchase_tax_percent: number;
  reorder_level: number;
  minimum_stock: number;
  maximum_stock: number | null;
  medicine_type_id: string | null;
  item_code: string | null;
  barcode: string | null;
  rack_number: string | null;
  mrp_paise: number | null;
  scheduled_drug: boolean;
  is_active: boolean;
  batches: BatchOut[];
  total_available: number;
  created_at: string;
  updated_at: string;
}

export interface MedicineCreate {
  generic_name: string;
  brand_name?: string | null;
  manufacturer?: string | null;
  strength?: string | null;
  dosage_form?: string | null;
  category?: string | null;
  unit: string;
  hsn_code?: string | null;
  gst_percent?: number;
  purchase_tax_percent?: number;
  reorder_level?: number;
  minimum_stock?: number;
  maximum_stock?: number | null;
  medicine_type_id?: string | null;
  item_code?: string | null;
  barcode?: string | null;
  rack_number?: string | null;
  mrp_paise?: number | null;
  scheduled_drug?: boolean;
}

export type MedicineUpdate = Partial<MedicineCreate> & { is_active?: boolean };

export function useMedicine(medicineId: string | null) {
  return useQuery({
    queryKey: ['medicine', medicineId],
    queryFn: () => apiFetch<MedicineDetailOut>(`/pharmacy/medicines/${medicineId}`),
    enabled: !!medicineId,
  });
}

export function useCreateMedicine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: MedicineCreate) => apiFetch<MedicineDetailOut>('/pharmacy/medicines', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['medicines'] }),
  });
}

export function useUpdateMedicine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ medicineId, ...body }: { medicineId: string } & MedicineUpdate) =>
      apiFetch<MedicineDetailOut>(`/pharmacy/medicines/${medicineId}`, { method: 'PATCH', body }),
    onSuccess: (_, v) => {
      qc.invalidateQueries({ queryKey: ['medicine', v.medicineId] });
      qc.invalidateQueries({ queryKey: ['medicines'] });
      qc.invalidateQueries({ queryKey: ['pharmacy-stock'] });
    },
  });
}

export function useCorrectBatchExpiry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ batchId, expiryDate }: { batchId: string; expiryDate: string; medicineId: string }) =>
      apiFetch<BatchOut>(`/pharmacy/batches/${batchId}/expiry?expiry_date=${expiryDate}`, { method: 'PATCH' }),
    onSuccess: (_, v) => {
      qc.invalidateQueries({ queryKey: ['medicine', v.medicineId] });
      qc.invalidateQueries({ queryKey: ['pharmacy-stock'] });
    },
  });
}

// -------------------------------- purchases -------------------------------- #

export type PurchaseStatus = 'pending' | 'partially_received' | 'completed' | 'cancelled';

export interface PurchaseLineCreate {
  medicine_id: string;
  batch_number: string;
  quantity: number;
  free_quantity?: number;
  purchase_rate_paise: number;
  selling_price_paise: number;
  discount_percent?: number;
  expiry_date: string;
  hsn_code?: string | null;
  tax_percent?: number;
}

export interface PurchaseLineOut extends PurchaseLineCreate {
  id: string;
  gross_amount_paise: number;
  total_value_paise: number;
}

export interface PurchaseOut {
  id: string;
  purchase_number: string;
  vendor_id: string;
  invoice_number: string | null;
  invoice_date: string | null;
  entry_date: string;
  status: PurchaseStatus;
  taxable_value_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  total_discount_paise: number;
  total_value_paise: number;
  received_at: string | null;
  lines: PurchaseLineOut[];
}

export function usePharmacyPurchases() {
  return useQuery({
    queryKey: ['pharmacy-purchases'],
    queryFn: () => apiFetch<PurchaseOut[]>('/pharmacy/purchases'),
  });
}

export function useCreatePurchase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { vendor_id: string; invoice_number?: string | null; invoice_date?: string | null; entry_date: string; lines: PurchaseLineCreate[] }) =>
      apiFetch<PurchaseOut>('/pharmacy/purchases', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pharmacy-purchases'] }),
  });
}

export function useReceivePurchase() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (purchaseId: string) => apiFetch<PurchaseOut>(`/pharmacy/purchases/${purchaseId}/receive`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pharmacy-purchases'] });
      qc.invalidateQueries({ queryKey: ['pharmacy-stock'] });
      qc.invalidateQueries({ queryKey: ['medicines'] });
    },
  });
}

// ------------------------------ sales returns ------------------------------ #

export interface SaleReturnOut {
  id: string;
  sale_id: string;
  reason: string | null;
  total_refund_paise: number;
  lines: { sale_line_id: string; medicine_id: string; batch_id: string; quantity: number; refund_amount_paise: number }[];
}

export function useCreateSaleReturn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ saleId, reason, lines }: { saleId: string; reason?: string | null; lines: { sale_line_id: string; quantity: number }[] }) =>
      apiFetch<SaleReturnOut>(`/pharmacy/sales/${saleId}/return`, { method: 'POST', body: { reason, lines } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pharmacy-sales'] });
      qc.invalidateQueries({ queryKey: ['pharmacy-stock'] });
    },
  });
}

// --------------------------------- stock ----------------------------------- #

export interface StockRowOut {
  batch_id: string;
  medicine_id: string;
  medicine_name: string;
  unit: string;
  batch_number: string;
  expiry_date: string;
  quantity_available: number;
  minimum_stock: number;
  maximum_stock: number | null;
  selling_rate_paise: number;
  status: 'in_stock' | 'low_stock' | 'out_of_stock' | 'expiring_soon' | 'expired';
}

export function usePharmacyStock() {
  return useQuery({
    queryKey: ['pharmacy-stock'],
    queryFn: () => apiFetch<StockRowOut[]>('/pharmacy/stock'),
  });
}

export interface StockAdjustmentOut {
  id: string;
  batch_id: string;
  medicine_id: string;
  system_stock: number;
  physical_stock: number;
  difference: number;
  reason: string | null;
  adjusted_by_id: string;
  created_at: string;
}

export function useAdjustStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { batch_id: string; physical_stock: number; reason?: string | null }) =>
      apiFetch<StockAdjustmentOut>('/pharmacy/stock/adjust', { method: 'POST', body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pharmacy-stock'] });
      qc.invalidateQueries({ queryKey: ['medicines'] });
    },
  });
}

// -------------------------------- indents ----------------------------------- #

export type IndentStatus = 'PENDING' | 'PARTIALLY_DELIVERED' | 'DELIVERED' | 'CANCELLED' | 'RETURNED';

export interface IndentItemOut {
  id: string;
  medicine_id: string;
  requested_quantity: number;
  delivered_quantity: number;
  returned_quantity: number;
  notes: string | null;
}

export interface IndentOut {
  id: string;
  indent_number: string;
  department: string;
  room: string | null;
  request_date: string;
  requested_by_id: string;
  status: IndentStatus;
  notes: string | null;
  items: IndentItemOut[];
  created_at: string;
  updated_at: string;
}

export function useIndents(filters: { status?: IndentStatus; department?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.department) params.set('department', filters.department);
  const qs = params.toString();
  return useQuery({
    queryKey: ['pharmacy-indents', filters],
    queryFn: () => apiFetch<IndentOut[]>(`/pharmacy/indents${qs ? `?${qs}` : ''}`),
  });
}

export function useIndent(indentId: string | null) {
  return useQuery({
    queryKey: ['pharmacy-indent', indentId],
    queryFn: () => apiFetch<IndentOut>(`/pharmacy/indents/${indentId}`),
    enabled: !!indentId,
  });
}

export function useIndentAvailableStock(medicineIds: string[]) {
  const params = new URLSearchParams();
  for (const id of medicineIds) params.append('medicine_id', id);
  return useQuery({
    queryKey: ['pharmacy-indent-stock', medicineIds],
    queryFn: () => apiFetch<{ medicine_id: string; available: number }[]>(`/pharmacy/indents/stock/available?${params.toString()}`),
    enabled: medicineIds.length > 0,
  });
}

export function useCreateIndent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { department: string; room?: string | null; request_date: string; notes?: string | null; items: { medicine_id: string; requested_quantity: number; notes?: string | null }[] }) =>
      apiFetch<IndentOut>('/pharmacy/indents', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pharmacy-indents'] }),
  });
}

export function useDeliverIndent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ indentId, ...body }: { indentId: string; notes?: string | null; lines: { indent_item_id: string; quantity: number }[] }) =>
      apiFetch<IndentOut>(`/pharmacy/indents/${indentId}/deliver`, { method: 'POST', body }),
    onSuccess: (_, v) => {
      qc.invalidateQueries({ queryKey: ['pharmacy-indents'] });
      qc.invalidateQueries({ queryKey: ['pharmacy-indent', v.indentId] });
      qc.invalidateQueries({ queryKey: ['pharmacy-indent-stock'] });
      qc.invalidateQueries({ queryKey: ['pharmacy-stock'] });
      qc.invalidateQueries({ queryKey: ['medicines'] });
    },
  });
}

export function useReturnIndent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ indentId, ...body }: { indentId: string; reason?: string | null; lines: { indent_item_id: string; quantity: number }[] }) =>
      apiFetch<{ id: string; processed: boolean }>(`/pharmacy/indents/${indentId}/return`, { method: 'POST', body }),
    onSuccess: (_, v) => {
      qc.invalidateQueries({ queryKey: ['pharmacy-indents'] });
      qc.invalidateQueries({ queryKey: ['pharmacy-indent', v.indentId] });
      qc.invalidateQueries({ queryKey: ['pharmacy-indent-stock'] });
      qc.invalidateQueries({ queryKey: ['pharmacy-stock'] });
      qc.invalidateQueries({ queryKey: ['medicines'] });
    },
  });
}

// ============================================================================
// PHASE 2 — Medicine Templates
// ============================================================================

export type TemplateStatus = 'ACTIVE' | 'INACTIVE';

export interface TemplateItemOut { id: string; medicine_id: string; default_quantity: number; notes: string | null }
export interface TemplateOut {
  id: string; name: string; description: string | null; status: TemplateStatus;
  items: TemplateItemOut[]; created_at: string; updated_at: string;
}

export function useTemplates(filters: { status?: TemplateStatus; search?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.search) params.set('search', filters.search);
  const qs = params.toString();
  return useQuery({ queryKey: ['pharmacy-templates', filters], queryFn: () => apiFetch<TemplateOut[]>(`/pharmacy/templates${qs ? `?${qs}` : ''}`) });
}

export function useTemplate(templateId: string | null) {
  return useQuery({ queryKey: ['pharmacy-template', templateId], queryFn: () => apiFetch<TemplateOut>(`/pharmacy/templates/${templateId}`), enabled: !!templateId });
}

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string | null; items: { medicine_id: string; default_quantity: number; notes?: string | null }[] }) =>
      apiFetch<TemplateOut>('/pharmacy/templates', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pharmacy-templates'] }),
  });
}

export function useUpdateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ templateId, ...body }: { templateId: string; name?: string; description?: string | null; status?: TemplateStatus }) =>
      apiFetch<TemplateOut>(`/pharmacy/templates/${templateId}`, { method: 'PATCH', body }),
    onSuccess: (_, v) => { qc.invalidateQueries({ queryKey: ['pharmacy-templates'] }); qc.invalidateQueries({ queryKey: ['pharmacy-template', v.templateId] }); },
  });
}

export function useAddTemplateItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ templateId, ...body }: { templateId: string; medicine_id: string; default_quantity: number; notes?: string | null }) =>
      apiFetch<TemplateOut>(`/pharmacy/templates/${templateId}/items`, { method: 'POST', body }),
    onSuccess: (_, v) => qc.invalidateQueries({ queryKey: ['pharmacy-template', v.templateId] }),
  });
}

export function useUpdateTemplateItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ templateId, itemId, quantity }: { templateId: string; itemId: string; quantity: number }) =>
      apiFetch<TemplateOut>(`/pharmacy/templates/${templateId}/items/${itemId}`, { method: 'PATCH', body: { quantity } }),
    onSuccess: (_, v) => qc.invalidateQueries({ queryKey: ['pharmacy-template', v.templateId] }),
  });
}

export function useRemoveTemplateItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ templateId, itemId }: { templateId: string; itemId: string }) =>
      apiFetch<TemplateOut>(`/pharmacy/templates/${templateId}/items/${itemId}`, { method: 'DELETE' }),
    onSuccess: (_, v) => qc.invalidateQueries({ queryKey: ['pharmacy-template', v.templateId] }),
  });
}

// ============================================================================
// PHASE 3 — Purchase Returns
// ============================================================================

export interface ReturnableLineOut { purchase_line_id: string; medicine_id: string; batch_number: string; purchased_quantity: number; already_returned: number; returnable: number }
export interface PurchaseReturnItemOut { id: string; purchase_line_id: string; medicine_id: string; batch_id: string; quantity: number; purchase_rate_paise: number; tax_percent: number; total_paise: number }
export interface PurchaseReturnOut { id: string; return_number: string; purchase_id: string; vendor_id: string; return_date: string; reason: string | null; items: PurchaseReturnItemOut[]; created_at: string }

export function useReturnableLines(purchaseId: string | null) {
  return useQuery({ queryKey: ['pharmacy-returnable', purchaseId], queryFn: () => apiFetch<ReturnableLineOut[]>(`/pharmacy/purchases/${purchaseId}/returnable`), enabled: !!purchaseId });
}

export function usePurchaseReturns() {
  return useQuery({ queryKey: ['pharmacy-purchase-returns'], queryFn: () => apiFetch<PurchaseReturnOut[]>('/pharmacy/purchase-returns') });
}

export function useCreatePurchaseReturn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ purchaseId, ...body }: { purchaseId: string; reason?: string | null; lines: { purchase_line_id: string; quantity: number }[] }) =>
      apiFetch<PurchaseReturnOut>(`/pharmacy/purchases/${purchaseId}/return`, { method: 'POST', body }),
    onSuccess: (_, v) => {
      qc.invalidateQueries({ queryKey: ['pharmacy-purchase-returns'] });
      qc.invalidateQueries({ queryKey: ['pharmacy-returnable', v.purchaseId] });
      qc.invalidateQueries({ queryKey: ['pharmacy-stock'] });
      qc.invalidateQueries({ queryKey: ['medicines'] });
    },
  });
}

// ============================================================================
// PHASE 4 — Purchase Orders
// ============================================================================

export type POStatus = 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'PARTIALLY_RECEIVED' | 'FULLY_RECEIVED' | 'CANCELLED';

export interface POItemIn { medicine_id: string; ordered_quantity: number; purchase_rate_paise: number; discount_percent?: number; tax_percent?: number; expected_expiry?: string | null; notes?: string | null }
export interface POItemOut extends POItemIn { id: string; received_quantity: number }
export interface POOut {
  id: string; po_number: string; vendor_id: string; po_date: string; expected_delivery_date: string | null;
  payment_terms: string | null; notes: string | null; status: POStatus; created_by_id: string; approved_by_id: string | null;
  items: POItemOut[]; created_at: string; updated_at: string;
}

export function usePurchaseOrders(filters: { status?: POStatus; vendor_id?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.vendor_id) params.set('vendor_id', filters.vendor_id);
  const qs = params.toString();
  return useQuery({ queryKey: ['pharmacy-pos', filters], queryFn: () => apiFetch<POOut[]>(`/pharmacy/purchase-orders${qs ? `?${qs}` : ''}`) });
}

export function usePurchaseOrder(poId: string | null) {
  return useQuery({ queryKey: ['pharmacy-po', poId], queryFn: () => apiFetch<POOut>(`/pharmacy/purchase-orders/${poId}`), enabled: !!poId });
}

export function useCreatePO() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { vendor_id: string; po_date: string; expected_delivery_date?: string | null; payment_terms?: string | null; notes?: string | null; items: POItemIn[] }) =>
      apiFetch<POOut>('/pharmacy/purchase-orders', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pharmacy-pos'] }),
  });
}

function usePOAction(action: 'submit' | 'approve' | 'cancel') {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (poId: string) => apiFetch<POOut>(`/pharmacy/purchase-orders/${poId}/${action}`, { method: 'POST' }),
    onSuccess: (_, poId) => { qc.invalidateQueries({ queryKey: ['pharmacy-pos'] }); qc.invalidateQueries({ queryKey: ['pharmacy-po', poId] }); },
  });
}
export const useSubmitPO = () => usePOAction('submit');
export const useApprovePO = () => usePOAction('approve');
export const useCancelPO = () => usePOAction('cancel');

export function useReceivePO() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ poId, lines }: { poId: string; lines: { po_item_id: string; quantity: number; batch_number: string; expiry_date: string; selling_price_paise: number }[] }) =>
      apiFetch<POOut>(`/pharmacy/purchase-orders/${poId}/receive`, { method: 'POST', body: { lines } }),
    onSuccess: (_, v) => {
      qc.invalidateQueries({ queryKey: ['pharmacy-pos'] });
      qc.invalidateQueries({ queryKey: ['pharmacy-po', v.poId] });
      qc.invalidateQueries({ queryKey: ['pharmacy-stock'] });
      qc.invalidateQueries({ queryKey: ['medicines'] });
    },
  });
}

// ============================================================================
// PHASE 5 — Reports
// ============================================================================

function useReport<T>(key: string, path: string, params: Record<string, string | undefined> = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) qs.set(k, v);
  const s = qs.toString();
  return useQuery({ queryKey: [key, params], queryFn: () => apiFetch<T[]>(`/pharmacy/reports/${path}${s ? `?${s}` : ''}`) });
}

export const useCollectionReport = (p: { from_date?: string; to_date?: string } = {}) => useReport<{ bill_date: string; bill_number: string; patient_name: string; amount_paise: number; payment_method: string; collected_by: string }>('rpt-collection', 'collection', p);
export const useVendorReport = () => useReport<{ vendor_id: string; vendor_name: string; gst_number: string | null; purchase_count: number; purchase_value_paise: number }>('rpt-vendors', 'vendors', {});
export const useTopSellingReport = (p: { from_date?: string; to_date?: string } = {}) => useReport<{ medicine_name: string; quantity_sold: number; revenue_paise: number }>('rpt-top-selling', 'top-selling-medicines', p);
export const useDoctorSalesReport = (p: { from_date?: string; to_date?: string } = {}) => useReport<{ doctor_name: string; bill_count: number; total_paise: number }>('rpt-doctor-sales', 'doctor-wise-sales', p);
export const usePurchaseBookReport = (p: { vendor_id?: string; from_date?: string; to_date?: string } = {}) => useReport<{ invoice_number: string | null; vendor_name: string; purchase_date: string; medicine_name: string; quantity: number; tax_paise: number; discount_paise: number; total_paise: number }>('rpt-purchase-book', 'purchase-book', p);
export const useIndentReportData = (p: { department?: string } = {}) => useReport<{ indent_number: string; department: string; room: string | null; medicine_name: string; requested_quantity: number; delivered_quantity: number; returned_quantity: number; remaining_quantity: number; status: string; request_date: string }>('rpt-indents', 'indents', p);
export const usePurchaseOrderReport = () => useReport<{ po_number: string; vendor_name: string; po_date: string; ordered: number; received: number; remaining: number; status: string }>('rpt-pos', 'purchase-orders', {});
export const usePurchaseReturnReport = () => useReport<{ return_number: string; vendor_name: string; medicine_name: string; batch_number: string | null; quantity: number; return_date: string; reason: string | null }>('rpt-purchase-returns', 'purchase-returns', {});
export const useCustomerSalesReport = () => useReport<{ patient_id: string; patient_name: string; bill_count: number; total_sales_paise: number; discount_paise: number }>('rpt-customer-sales', 'customer-sales', {});
export const useBillMarginReport = (p: { from_date?: string; to_date?: string } = {}) => useReport<{ bill_number: string; selling_value_paise: number; purchase_cost_paise: number; margin_paise: number }>('rpt-bill-margin', 'bill-wise-margin', p);
export const useStockTransactionReport = () => useReport<{ occurred_at: string; medicine_name: string; batch_number: string; transaction_type: string; quantity_delta: number; reference_type: string; user_name: string }>('rpt-stock-txns', 'stock-transactions', {});

export function useCollectionSummary(p: { from_date?: string; to_date?: string } = {}) {
  const qs = new URLSearchParams();
  if (p.from_date) qs.set('from_date', p.from_date);
  if (p.to_date) qs.set('to_date', p.to_date);
  const s = qs.toString();
  return useQuery({
    queryKey: ['rpt-collection-summary', p],
    queryFn: () => apiFetch<{ gross_paise: number; discount_paise: number; net_paise: number; cash_paise: number; card_paise: number; cheque_paise: number; online_paise: number; bill_count: number }>(`/pharmacy/reports/collection-summary${s ? `?${s}` : ''}`),
  });
}

// ============================================================================
// PHASE 6 — Settings & Indent Templates
// ============================================================================

export interface PharmacySettingsOut {
  pharmacy_name: string; address: string | null; phone: string | null; email: string | null; gstin: string | null;
  invoice_header: string | null; invoice_footer: string | null; show_gst: boolean; show_doctor: boolean;
  show_patient_details: boolean; show_batch: boolean; show_expiry: boolean; show_mrp: boolean; show_payment_info: boolean; updated_at: string;
}

export function usePharmacySettings() {
  return useQuery({ queryKey: ['pharmacy-settings'], queryFn: () => apiFetch<PharmacySettingsOut>('/pharmacy/settings') });
}

export function useUpdatePharmacySettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<PharmacySettingsOut>) => apiFetch<PharmacySettingsOut>('/pharmacy/settings', { method: 'PUT', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pharmacy-settings'] }),
  });
}

export interface IndentTemplateItemOut { id: string; medicine_id: string; default_quantity: number; notes: string | null }
export interface IndentTemplateOut {
  id: string; name: string; description: string | null; department: string | null; room: string | null;
  status: TemplateStatus; items: IndentTemplateItemOut[]; created_at: string; updated_at: string;
}

export function useIndentTemplates(status?: TemplateStatus) {
  return useQuery({ queryKey: ['indent-templates', status], queryFn: () => apiFetch<IndentTemplateOut[]>(`/pharmacy/indent-templates${status ? `?status=${status}` : ''}`) });
}

export function useCreateIndentTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string | null; department?: string | null; room?: string | null; items: { medicine_id: string; default_quantity: number; notes?: string | null }[] }) =>
      apiFetch<IndentTemplateOut>('/pharmacy/indent-templates', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['indent-templates'] }),
  });
}

export function useUpdateIndentTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ templateId, ...body }: { templateId: string; status?: TemplateStatus; name?: string; description?: string | null }) =>
      apiFetch<IndentTemplateOut>(`/pharmacy/indent-templates/${templateId}`, { method: 'PATCH', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['indent-templates'] }),
  });
}

export function useDuplicateIndentTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (templateId: string) => apiFetch<IndentTemplateOut>(`/pharmacy/indent-templates/${templateId}/duplicate`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['indent-templates'] }),
  });
}
