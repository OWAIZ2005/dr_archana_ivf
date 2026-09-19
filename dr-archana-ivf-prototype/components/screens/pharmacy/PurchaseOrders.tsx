'use client';

import React, { useMemo, useState } from 'react';
import { useApp } from '@/lib/store';
import { Badge, Button, Card, InfoNote, Input, Modal, RemoveLineButton, Select } from '@/components/ui/primitives';
import { formatINR } from '@/lib/utils';
import { ApiError } from '@/lib/api/client';
import {
  useApprovePO, useCancelPO, useCreatePO, usePurchaseOrder, usePurchaseOrders, useReceivePO, useSubmitPO,
  type MedicineOut, type POItemIn, type POOut, type POStatus,
} from '@/lib/api/pharmacy';
import type { VendorOut } from '@/lib/api/purchasing';
import { Plus } from 'lucide-react';

const PO_STATUS_LABEL: Record<POStatus, string> = {
  DRAFT: 'Draft', PENDING_APPROVAL: 'Pending Approval', APPROVED: 'Approved',
  PARTIALLY_RECEIVED: 'Partially Received', FULLY_RECEIVED: 'Fully Received', CANCELLED: 'Cancelled',
};
const PO_STATUS_TONE: Record<POStatus, 'completed' | 'attention' | 'critical' | 'neutral'> = {
  DRAFT: 'neutral', PENDING_APPROVAL: 'attention', APPROVED: 'attention', PARTIALLY_RECEIVED: 'attention', FULLY_RECEIVED: 'completed', CANCELLED: 'critical',
};

export function PurchaseOrdersTab({
  vendors, medicines, medicineNameById, canCreate, canApprove, canReceive,
}: { vendors: VendorOut[]; medicines: MedicineOut[]; medicineNameById: Record<string, string>; canCreate: boolean; canApprove: boolean; canReceive: boolean }) {
  const [statusFilter, setStatusFilter] = useState<'' | POStatus>('');
  const [addOpen, setAddOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const posQuery = usePurchaseOrders({ status: statusFilter || undefined });
  const pos = posQuery.data ?? [];
  const vendorNameById = useMemo(() => Object.fromEntries(vendors.map((v) => [v.id, v.name])), [vendors]);

  return (
    <div className="animate-fade-up space-y-4 p-5">
      <NewPOModal open={addOpen} onClose={() => setAddOpen(false)} vendors={vendors} medicines={medicines} />
      {detailId && (
        <PODetailModal poId={detailId} medicineNameById={medicineNameById} vendorNameById={vendorNameById}
          canApprove={canApprove} canReceive={canReceive} onClose={() => setDetailId(null)} />
      )}

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="w-56">
          <Select label="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as '' | POStatus)}>
            <option value="">All statuses</option>
            {(Object.keys(PO_STATUS_LABEL) as POStatus[]).map((s) => <option key={s} value={s}>{PO_STATUS_LABEL[s]}</option>)}
          </Select>
        </div>
        {canCreate && <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setAddOpen(true)}>New Purchase Order</Button>}
      </div>

      {posQuery.isLoading ? (
        <p className="py-10 text-center text-[14px] text-ink-500">Loading purchase orders…</p>
      ) : pos.length === 0 ? (
        <InfoNote>No purchase orders match.</InfoNote>
      ) : (
        <div className="stagger space-y-2.5">
          {pos.map((po) => {
            const ordered = po.items.reduce((s, i) => s + i.ordered_quantity, 0);
            const received = po.items.reduce((s, i) => s + i.received_quantity, 0);
            return (
              <Card key={po.id} className="p-4" interactive onClick={() => setDetailId(po.id)}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-[14px] font-semibold text-ink-900">{po.po_number} <span className="tnum font-normal text-ink-400">· {vendorNameById[po.vendor_id] ?? 'Vendor'}</span></p>
                    <p className="text-[12px] text-ink-500">{po.po_date} · Ordered {ordered} · Received {received}</p>
                  </div>
                  <Badge tone={PO_STATUS_TONE[po.status]} size="sm">{PO_STATUS_LABEL[po.status]}</Badge>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function NewPOModal({ open, onClose, vendors, medicines }: { open: boolean; onClose: () => void; vendors: VendorOut[]; medicines: MedicineOut[] }) {
  const { toast } = useApp();
  const createPO = useCreatePO();
  const [vendorId, setVendorId] = useState('');
  const [poDate, setPoDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [expectedDate, setExpectedDate] = useState('');
  const [paymentTerms, setPaymentTerms] = useState('');
  const [lines, setLines] = useState<(POItemIn & { key: number })[]>([{ key: 0, medicine_id: '', ordered_quantity: 1, purchase_rate_paise: 0, tax_percent: 12 }]);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setVendorId(''); setPoDate(new Date().toISOString().slice(0, 10)); setExpectedDate(''); setPaymentTerms('');
    setLines([{ key: 0, medicine_id: '', ordered_quantity: 1, purchase_rate_paise: 0, tax_percent: 12 }]); setError(null); createPO.reset();
  };
  const close = () => { reset(); onClose(); };
  const addLine = () => setLines((l) => [...l, { key: l.length ? Math.max(...l.map((x) => x.key)) + 1 : 0, medicine_id: '', ordered_quantity: 1, purchase_rate_paise: 0, tax_percent: 12 }]);
  const updateLine = (key: number, patch: Partial<POItemIn>) => setLines((l) => l.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const removeLine = (key: number) => setLines((l) => (l.length > 1 ? l.filter((r) => r.key !== key) : l));

  return (
    <Modal
      open={open} onClose={close} title="New Purchase Order" subtitle="Creating a PO never changes stock — stock increases only when it is received."
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button
              variant="primary" disabled={!vendorId || createPO.isPending} loading={createPO.isPending}
              onClick={() => {
                setError(null);
                const validLines = lines.filter((l) => l.medicine_id && l.ordered_quantity > 0);
                if (validLines.length === 0) { setError('Add at least one medicine.'); return; }
                createPO.mutate(
                  {
                    vendor_id: vendorId, po_date: poDate, expected_delivery_date: expectedDate || null, payment_terms: paymentTerms.trim() || null,
                    items: validLines.map(({ key, ...rest }) => rest),
                  },
                  { onSuccess: (po) => { close(); toast({ title: `PO ${po.po_number} created (Draft)`, tone: 'success' }); }, onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not create the purchase order.') }
                );
              }}
            >
              Save as Draft
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <Select label="Vendor" value={vendorId} onChange={(e) => setVendorId(e.target.value)}>
            <option value="">Select a vendor…</option>
            {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
          </Select>
          <Input label="PO date" type="date" value={poDate} onChange={(e) => setPoDate(e.target.value)} />
          <Input label="Expected delivery" type="date" value={expectedDate} onChange={(e) => setExpectedDate(e.target.value)} />
        </div>
        <Input label="Payment terms (optional)" value={paymentTerms} onChange={(e) => setPaymentTerms(e.target.value)} />

        <div className="space-y-2.5">
          {lines.map((line) => (
            <Card key={line.key} className="p-3">
              <div className="grid gap-2.5 sm:grid-cols-4">
                <div className="sm:col-span-2">
                  <Select label="Medicine" value={line.medicine_id} onChange={(e) => updateLine(line.key, { medicine_id: e.target.value })}>
                    <option value="">Select…</option>
                    {medicines.map((m) => <option key={m.id} value={m.id}>{m.brand_name ?? m.generic_name}</option>)}
                  </Select>
                </div>
                <Input label="Ordered qty" type="number" min={1} value={String(line.ordered_quantity)} onChange={(e) => updateLine(line.key, { ordered_quantity: Number(e.target.value) || 0 })} />
                <Input label="Rate (₹)" type="number" value={String((line.purchase_rate_paise || 0) / 100)} onChange={(e) => updateLine(line.key, { purchase_rate_paise: Math.round(Number(e.target.value) * 100) || 0 })} />
                <Input label="Tax %" type="number" value={String(line.tax_percent ?? 0)} onChange={(e) => updateLine(line.key, { tax_percent: Number(e.target.value) || 0 })} />
                <Input label="Discount %" type="number" value={String(line.discount_percent ?? 0)} onChange={(e) => updateLine(line.key, { discount_percent: Number(e.target.value) || 0 })} />
                <Input label="Expected expiry" type="date" value={line.expected_expiry ?? ''} onChange={(e) => updateLine(line.key, { expected_expiry: e.target.value || null })} />
              </div>
              <RemoveLineButton label="Remove line" onClick={() => removeLine(line.key)} />
            </Card>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={addLine}>Add medicine</Button>
        </div>
      </div>
    </Modal>
  );
}

function PODetailModal({
  poId, medicineNameById, vendorNameById, canApprove, canReceive, onClose,
}: { poId: string; medicineNameById: Record<string, string>; vendorNameById: Record<string, string>; canApprove: boolean; canReceive: boolean; onClose: () => void }) {
  const { toast } = useApp();
  const poQuery = usePurchaseOrder(poId);
  const submitPO = useSubmitPO();
  const approvePO = useApprovePO();
  const cancelPO = useCancelPO();
  const receivePO = useReceivePO();
  const [receiving, setReceiving] = useState(false);
  const [receiveLines, setReceiveLines] = useState<Record<string, { quantity: number; batch_number: string; expiry_date: string; selling_price_paise: number }>>({});
  const [error, setError] = useState<string | null>(null);

  const po = poQuery.data;

  const startReceive = () => { setReceiving(true); setReceiveLines({}); setError(null); receivePO.reset(); };

  return (
    <Modal
      open onClose={onClose} title={po?.po_number ?? 'Purchase Order'} subtitle={po ? vendorNameById[po.vendor_id] : undefined}
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            {receiving ? (
              <>
                <Button variant="ghost" onClick={() => setReceiving(false)}>Cancel</Button>
                <Button
                  variant="primary" loading={receivePO.isPending}
                  onClick={() => {
                    setError(null);
                    const lines = Object.entries(receiveLines).filter(([, v]) => v.quantity > 0 && v.batch_number && v.expiry_date)
                      .map(([po_item_id, v]) => ({ po_item_id, ...v }));
                    if (lines.length === 0) { setError('Enter quantity, batch number and expiry for at least one line.'); return; }
                    receivePO.mutate(
                      { poId, lines },
                      { onSuccess: () => { setReceiving(false); toast({ title: 'Goods received — stock updated', tone: 'success' }); }, onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not receive against this PO.') }
                    );
                  }}
                >
                  Confirm Receipt
                </Button>
              </>
            ) : (
              <>
                <Button variant="ghost" onClick={onClose}>Close</Button>
                {po?.status === 'DRAFT' && (
                  <Button variant="secondary" loading={submitPO.isPending} onClick={() => submitPO.mutate(poId, { onSuccess: () => toast({ title: 'Submitted for approval', tone: 'success' }) })}>Submit for Approval</Button>
                )}
                {po?.status === 'PENDING_APPROVAL' && canApprove && (
                  <Button variant="primary" loading={approvePO.isPending} onClick={() => approvePO.mutate(poId, { onSuccess: () => toast({ title: 'PO approved', tone: 'success' }), onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not approve.') })}>Approve</Button>
                )}
                {po && ['APPROVED', 'PARTIALLY_RECEIVED'].includes(po.status) && canReceive && (
                  <Button variant="primary" onClick={startReceive}>Receive</Button>
                )}
                {po && !['FULLY_RECEIVED', 'CANCELLED'].includes(po.status) && canApprove && (
                  <Button variant="ghost" onClick={() => cancelPO.mutate(poId, { onSuccess: () => toast({ title: 'PO cancelled', tone: 'success' }) })}>Cancel PO</Button>
                )}
              </>
            )}
          </div>
        </div>
      }
    >
      {!po ? (
        <p className="py-10 text-center text-[14px] text-ink-500">Loading…</p>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-[13px] text-ink-500">
            <span>PO Date: {po.po_date}</span>
            {po.expected_delivery_date && <span>Expected: {po.expected_delivery_date}</span>}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px] text-left text-[13px]">
              <thead>
                <tr className="border-b border-ink-200/70 text-[11.5px] font-semibold uppercase tracking-[0.08em] text-ink-400">
                  <th className="py-2 pr-3">Medicine</th><th className="py-2 pr-3">Ordered</th><th className="py-2 pr-3">Received</th><th className="py-2 pr-3">Remaining</th><th className="py-2 pr-3">Rate</th>
                  {receiving && <><th className="py-2 pr-3">Receive Qty</th><th className="py-2 pr-3">Batch</th><th className="py-2 pr-3">Expiry</th><th className="py-2 pr-3">Selling ₹</th></>}
                </tr>
              </thead>
              <tbody>
                {po.items.map((item) => {
                  const remaining = item.ordered_quantity - item.received_quantity;
                  const rl = receiveLines[item.id] ?? { quantity: 0, batch_number: '', expiry_date: '', selling_price_paise: 0 };
                  return (
                    <tr key={item.id} className="border-b border-ink-100 last:border-0">
                      <td className="py-2.5 pr-3 font-medium text-ink-900">{medicineNameById[item.medicine_id] ?? 'Medicine'}</td>
                      <td className="tnum py-2.5 pr-3">{item.ordered_quantity}</td>
                      <td className="tnum py-2.5 pr-3">{item.received_quantity}</td>
                      <td className="tnum py-2.5 pr-3 text-ink-500">{remaining}</td>
                      <td className="tnum py-2.5 pr-3">₹{(item.purchase_rate_paise / 100).toFixed(2)}</td>
                      {receiving && (
                        <>
                          <td className="py-2 pr-3">{remaining > 0 && <Input type="number" min={0} max={remaining} className="w-20" value={rl.quantity ? String(rl.quantity) : ''} onChange={(e) => setReceiveLines((p) => ({ ...p, [item.id]: { ...rl, quantity: Math.min(Number(e.target.value) || 0, remaining) } }))} />}</td>
                          <td className="py-2 pr-3">{remaining > 0 && <Input className="w-24" value={rl.batch_number} onChange={(e) => setReceiveLines((p) => ({ ...p, [item.id]: { ...rl, batch_number: e.target.value } }))} />}</td>
                          <td className="py-2 pr-3">{remaining > 0 && <Input type="date" className="w-36" value={rl.expiry_date} onChange={(e) => setReceiveLines((p) => ({ ...p, [item.id]: { ...rl, expiry_date: e.target.value } }))} />}</td>
                          <td className="py-2 pr-3">{remaining > 0 && <Input type="number" className="w-20" value={rl.selling_price_paise ? String(rl.selling_price_paise / 100) : ''} onChange={(e) => setReceiveLines((p) => ({ ...p, [item.id]: { ...rl, selling_price_paise: Math.round(Number(e.target.value) * 100) || 0 } }))} />}</td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Modal>
  );
}
