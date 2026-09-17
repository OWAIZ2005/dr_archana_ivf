'use client';

import React, { useMemo, useRef, useState } from 'react';
import { useApp } from '@/lib/store';
import { PHARMACY_ITEMS, PHARMACY_SALES, PHARMACY_METRICS } from '@/lib/data';
import { cn, formatINR } from '@/lib/utils';
import { Badge, Button, Card, CardHeader, Field, InfoNote, Input, Modal, ProgressBar, SectionTitle, Select, Switch, Tabs } from '@/components/ui/primitives';
import { useCountUp } from '@/lib/hooks';
import { ApiError } from '@/lib/api/client';
import {
  useAdjustStock,
  useCorrectBatchExpiry,
  useCreateIndent,
  useCreateMedicine,
  useCreateMedicineAttribute,
  useCreatePurchase,
  useCreateSaleReturn,
  useDeliverIndent,
  useDispenseSale,
  useIndent,
  useIndentAvailableStock,
  useIndents,
  useMedicine,
  useMedicineAttributes,
  useMedicines,
  usePharmacyPurchases,
  usePharmacySales,
  usePharmacyStock,
  useReceivePurchase,
  useReturnIndent,
  useUpdateMedicine,
  type IndentOut,
  type IndentStatus,
  type MedicineDetailOut,
  type MedicineOut,
  type MedicineUpdate,
  type PaymentMethod,
  type PurchaseLineCreate,
  type SaleOut,
} from '@/lib/api/pharmacy';
import { useCreateVendor, useUpdateVendor, useVendors, type VendorOut } from '@/lib/api/purchasing';
import { usePatients } from '@/lib/api/patients';
import { useDoctors } from '@/lib/api/users';
import { useCreatePurchaseReturn, usePurchaseReturns, useReturnableLines } from '@/lib/api/pharmacy';
import { TemplatesTab } from '@/components/screens/pharmacy/Templates';
import { PurchaseOrdersTab } from '@/components/screens/pharmacy/PurchaseOrders';
import { ReportsTab } from '@/components/screens/pharmacy/Reports';
import { SettingsTab } from '@/components/screens/pharmacy/Settings';
import {
  AlertTriangle,
  Banknote,
  Boxes,
  CalendarX2,
  ClipboardList,
  CreditCard,
  FileText,
  IndianRupee,
  LayoutDashboard,
  Package,
  Pencil,
  Pill,
  Plus,
  Receipt,
  RotateCcw,
  Search,
  Smartphone,
  Trash2,
  Truck,
} from 'lucide-react';

function Metric({ label, value, icon: Icon, tone, currency }: { label: string; value: number; icon: any; tone: string; currency?: boolean }) {
  const v = useCountUp(value, 1000);
  return (
    <Card className="p-4">
      <div className={cn('flex h-9 w-9 items-center justify-center rounded-xl ring-1 ring-inset', tone)}>
        <Icon className="h-[18px] w-[18px]" />
      </div>
      <p className="tnum tracking-display mt-3 text-[22px] font-semibold leading-none text-ink-900">
        {currency ? formatINR(Math.round(v), true) : Math.round(v)}
      </p>
      <p className="mt-1.5 text-[13px] font-medium text-ink-600">{label}</p>
    </Card>
  );
}

const STOCK_STATUS_LABEL: Record<string, string> = {
  in_stock: 'In Stock', low_stock: 'Low Stock', out_of_stock: 'Out of Stock',
  expiring_soon: 'Expiring Soon', expired: 'Expired',
};
const STOCK_STATUS_TONE: Record<string, 'completed' | 'attention' | 'critical' | 'neutral'> = {
  in_stock: 'completed', low_stock: 'attention', out_of_stock: 'critical', expiring_soon: 'attention', expired: 'critical',
};

export function Pharmacy() {
  const { toast, can } = useApp();
  const [tab, setTab] = useState('dashboard');
  const [q, setQ] = useState('');
  const [addMedicineOpen, setAddMedicineOpen] = useState(false);
  const [addVendorOpen, setAddVendorOpen] = useState(false);
  const [addPurchaseOpen, setAddPurchaseOpen] = useState(false);
  const [newBillOpen, setNewBillOpen] = useState(false);
  const [adjustBatchId, setAdjustBatchId] = useState<string | null>(null);
  const [detailMedicineId, setDetailMedicineId] = useState<string | null>(null);
  const [detailVendorId, setDetailVendorId] = useState<string | null>(null);
  const [addIndentOpen, setAddIndentOpen] = useState(false);
  const [detailIndentId, setDetailIndentId] = useState<string | null>(null);

  const medicinesQuery = useMedicines();
  const salesQuery = usePharmacySales();
  const patientsQuery = usePatients();
  const doctorsQuery = useDoctors();
  const stockQuery = usePharmacyStock();
  const vendorsQuery = useVendors();
  const purchasesQuery = usePharmacyPurchases();
  const canManage = can('pharmacy.manage');
  const canPurchase = can('pharmacy.purchase');
  const canAdjust = can('pharmacy.adjust');
  const canDispense = can('pharmacy.dispense');
  const canIndentRequest = can('pharmacy.indent_request');
  const canIndentDeliver = can('pharmacy.indent_deliver');
  const canPurchaseReturn = can('pharmacy.purchase_return');
  const canPOCreate = can('pharmacy.po_create');
  const canPOApprove = can('pharmacy.po_approve');
  const canSettingsManage = can('pharmacy.settings_manage');
  const hasRealMedicines = (medicinesQuery.data ?? []).length > 0;
  const indentsQuery = useIndents();

  const medicineNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const m of medicinesQuery.data ?? []) map[m.id] = m.brand_name ?? m.generic_name;
    return map;
  }, [medicinesQuery.data]);

  const patientNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of patientsQuery.data ?? []) map[p.id] = p.full_name;
    return map;
  }, [patientsQuery.data]);

  const patientUhidById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of patientsQuery.data ?? []) map[p.id] = p.uhid;
    return map;
  }, [patientsQuery.data]);

  const doctorNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const d of doctorsQuery.data ?? []) map[d.id] = d.full_name;
    return map;
  }, [doctorsQuery.data]);

  const vendorNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const v of vendorsQuery.data ?? []) map[v.id] = v.name;
    return map;
  }, [vendorsQuery.data]);

  const realMedicines = useMemo(
    () =>
      (medicinesQuery.data ?? []).map((m) => ({
        id: m.id, name: m.brand_name ?? m.generic_name, category: m.category ?? 'Uncategorised',
        stock: m.total_available, reorderLevel: m.reorder_level, unit: m.unit,
        batch: null as string | null, expiry: null as string | null, mrp: null as number | null, gst: null as number | null,
      })),
    [medicinesQuery.data]
  );

  const realSales = useMemo(
    () =>
      (salesQuery.data ?? []).map((s) => ({
        id: s.bill_number, patient: patientNameById[s.patient_id] ?? 'Unknown patient', date: '',
        items: s.lines.map((l) => `${medicineNameById[l.medicine_id] ?? 'Medicine'} × ${l.quantity}`).join(', '),
        amount: Math.round(s.total_amount_paise / 100), status: s.status, tone: 'completed' as const,
      })),
    [salesQuery.data, patientNameById, medicineNameById]
  );

  const items = useMemo(() => {
    const base = hasRealMedicines ? realMedicines : PHARMACY_ITEMS;
    if (!q.trim()) return base;
    const t = q.toLowerCase();
    return base.filter((i) => i.name.toLowerCase().includes(t) || i.category.toLowerCase().includes(t));
  }, [q, hasRealMedicines, realMedicines]);

  const sales = hasRealMedicines && salesQuery.data ? realSales : PHARMACY_SALES;
  const stockRows = stockQuery.data ?? [];
  const purchases = purchasesQuery.data ?? [];
  const vendors = vendorsQuery.data ?? [];
  const adjustBatch = stockRows.find((r) => r.batch_id === adjustBatchId) ?? null;

  return (
    <div className="screen-enter mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6 lg:p-8">
      <AddMedicineModal open={addMedicineOpen} onClose={() => setAddMedicineOpen(false)} />
      <AddVendorModal open={addVendorOpen} onClose={() => setAddVendorOpen(false)} />
      <AddPurchaseModal open={addPurchaseOpen} onClose={() => setAddPurchaseOpen(false)} vendors={vendors} medicines={medicinesQuery.data ?? []} />
      {adjustBatch && <StockAdjustModal row={adjustBatch} onClose={() => setAdjustBatchId(null)} />}
      {detailMedicineId && (
        <MedicineDetailModal medicineId={detailMedicineId} canManage={canManage} onClose={() => setDetailMedicineId(null)} />
      )}
      {detailVendorId && (
        <VendorDetailModal vendorId={detailVendorId} canManage={canPurchase} onClose={() => setDetailVendorId(null)} />
      )}
      <NewIndentModal open={addIndentOpen} onClose={() => setAddIndentOpen(false)} medicines={medicinesQuery.data ?? []} />
      {detailIndentId && (
        <IndentDetailModal indentId={detailIndentId} medicineNameById={medicineNameById} canDeliver={canIndentDeliver} onClose={() => setDetailIndentId(null)} />
      )}
      <NewBillModal
        open={newBillOpen}
        onClose={() => setNewBillOpen(false)}
        medicines={medicinesQuery.data ?? []}
        patients={patientsQuery.data ?? []}
        doctors={doctorsQuery.data ?? []}
      />

      <SectionTitle
        eyebrow="Operations"
        title="Pharmacy Management"
        description="Medicine catalogue, vendors, purchases, stock and GST-ready sales"
        action={
          <div className="flex gap-2">
            {canManage && (
              <Button variant="secondary" icon={<Plus className="h-4 w-4" />} onClick={() => setAddMedicineOpen(true)}>
                Add Medicine
              </Button>
            )}
            {canDispense && (
              <Button variant="primary" icon={<Receipt className="h-4 w-4" />} onClick={() => setNewBillOpen(true)}>
                New Bill
              </Button>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-4">
        {hasRealMedicines ? (
          <>
            <Metric label="Today's Sales" value={Math.round((salesQuery.data ?? []).reduce((s, sale) => s + sale.total_amount_paise, 0) / 100)} icon={IndianRupee} tone="bg-emerald-50 text-emerald-700 ring-emerald-600/12" currency />
            <Metric label="Below Reorder Level" value={realMedicines.filter((m) => m.stock < m.reorderLevel).length} icon={AlertTriangle} tone="bg-amber-50 text-amber-700 ring-amber-600/12" />
            <Metric label="Total Sales" value={(salesQuery.data ?? []).length} icon={CalendarX2} tone="bg-rose-50 text-rose-700 ring-rose-600/12" />
            <Metric label="Total SKUs" value={realMedicines.length} icon={Package} tone="bg-sky-50 text-sky-700 ring-sky-600/12" />
          </>
        ) : (
          <>
            <Metric label="Today's Sales" value={PHARMACY_METRICS.todaySales} icon={IndianRupee} tone="bg-emerald-50 text-emerald-700 ring-emerald-600/12" currency />
            <Metric label="Below Reorder Level" value={PHARMACY_METRICS.itemsBelowReorder} icon={AlertTriangle} tone="bg-amber-50 text-amber-700 ring-amber-600/12" />
            <Metric label="Expiring in 90 Days" value={PHARMACY_METRICS.expiringWithin90Days} icon={CalendarX2} tone="bg-rose-50 text-rose-700 ring-rose-600/12" />
            <Metric label="Total SKUs" value={PHARMACY_METRICS.totalSKUs} icon={Package} tone="bg-sky-50 text-sky-700 ring-sky-600/12" />
          </>
        )}
      </div>

      <Card className="overflow-hidden">
        <div className="px-4 pt-2">
          <Tabs
            tabs={[
              { id: 'dashboard', label: 'Sales Dashboard', count: (salesQuery.data ?? []).length },
              { id: 'stock', label: 'Medicine Stock', count: items.length },
              { id: 'inventory', label: 'Current Stock', count: stockRows.length },
              { id: 'vendors', label: 'Vendors', count: vendors.length },
              { id: 'purchases', label: 'Purchases & GRN', count: purchases.length },
              { id: 'sales', label: 'Recent Dispensing', count: sales.length },
              { id: 'returns', label: 'Sales Returns', count: 0 },
              { id: 'indents', label: 'Indents', count: (indentsQuery.data ?? []).length },
              { id: 'templates', label: 'Templates' },
              { id: 'purchase-orders', label: 'Purchase Orders' },
              { id: 'purchase-returns', label: 'Purchase Returns' },
              { id: 'reports', label: 'Reports' },
              { id: 'settings', label: 'Settings' },
            ]}
            active={tab}
            onChange={setTab}
          />
        </div>

        {tab === 'dashboard' && (
          <SalesDashboardTab
            sales={salesQuery.data ?? []}
            isLoading={salesQuery.isLoading}
            patientNameById={patientNameById}
            patientUhidById={patientUhidById}
            doctorNameById={doctorNameById}
            doctors={doctorsQuery.data ?? []}
          />
        )}

        {tab === 'stock' && (
          <div className="animate-fade-up p-5">
            <div className="mb-4">
              <Input placeholder="Search medicine or category…" icon={<Search className="h-3.5 w-3.5" />} value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <div className="stagger grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {items.map((m, i) => {
                const pct = Math.min((m.stock / (m.reorderLevel * 2 || 1)) * 100, 100);
                const low = m.stock < m.reorderLevel;
                return (
                  <Card
                    key={m.id}
                    style={{ ['--i' as string]: i }}
                    className="p-4"
                    interactive={hasRealMedicines}
                    onClick={hasRealMedicines ? () => setDetailMedicineId(m.id) : undefined}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                        <Pill className="h-4 w-4" />
                      </div>
                      {low && <Badge tone="attention" size="sm">Reorder</Badge>}
                    </div>
                    <p className="mt-2.5 text-[14px] font-semibold leading-snug text-ink-900">{m.name}</p>
                    <p className="text-[12px] text-ink-500">{m.category}</p>
                    <div className="mt-3">
                      <div className="mb-1 flex justify-between text-[12px]">
                        <span className="text-ink-500">Stock: <span className="tnum font-semibold text-ink-800">{m.stock}</span> {m.unit}</span>
                        <span className="tnum text-ink-400">Min {m.reorderLevel}</span>
                      </div>
                      <ProgressBar value={pct} tone={low ? 'amber' : 'brand'} height={5} />
                    </div>
                    {m.mrp !== null ? (
                      <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-ink-100 pt-2.5 text-[12px]">
                        <span className="text-ink-400">Batch</span><span className="tnum text-right text-ink-700">{m.batch}</span>
                        <span className="text-ink-400">Expiry</span><span className="tnum text-right text-ink-700">{m.expiry}</span>
                        <span className="text-ink-400">MRP</span><span className="tnum text-right font-semibold text-ink-900">₹{m.mrp.toLocaleString('en-IN')}</span>
                        <span className="text-ink-400">GST</span><span className="tnum text-right text-ink-700">{m.gst}%</span>
                      </div>
                    ) : (
                      <p className="mt-3 border-t border-ink-100 pt-2.5 text-[12px] text-ink-400">See "Current Stock" for batch-level detail.</p>
                    )}
                  </Card>
                );
              })}
            </div>
          </div>
        )}

        {tab === 'inventory' && (
          <div className="animate-fade-up p-5">
            {stockQuery.isLoading ? (
              <p className="py-10 text-center text-[14px] text-ink-500">Loading stock…</p>
            ) : stockRows.length === 0 ? (
              <InfoNote>No batches recorded yet. Receive a purchase to bring in stock.</InfoNote>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-left text-[13px]">
                  <thead>
                    <tr className="border-b border-ink-200/70 text-[11.5px] font-semibold uppercase tracking-[0.08em] text-ink-400">
                      <th className="py-2 pr-3">Medicine</th><th className="py-2 pr-3">Batch</th><th className="py-2 pr-3">Expiry</th>
                      <th className="py-2 pr-3">Available</th><th className="py-2 pr-3">Min / Max</th><th className="py-2 pr-3">Status</th>
                      {canAdjust && <th className="py-2 pr-3">Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {stockRows.map((r) => (
                      <tr key={r.batch_id} className="border-b border-ink-100 last:border-0">
                        <td className="py-2.5 pr-3 font-medium text-ink-900">{r.medicine_name}</td>
                        <td className="tnum py-2.5 pr-3 text-ink-600">{r.batch_number}</td>
                        <td className="tnum py-2.5 pr-3 text-ink-600">{r.expiry_date}</td>
                        <td className="tnum py-2.5 pr-3 text-ink-800">{r.quantity_available} {r.unit}</td>
                        <td className="tnum py-2.5 pr-3 text-ink-500">{r.minimum_stock} / {r.maximum_stock ?? '—'}</td>
                        <td className="py-2.5 pr-3"><Badge tone={STOCK_STATUS_TONE[r.status]} size="sm">{STOCK_STATUS_LABEL[r.status]}</Badge></td>
                        {canAdjust && (
                          <td className="py-2.5 pr-3">
                            <Button size="sm" variant="ghost" onClick={() => setAdjustBatchId(r.batch_id)}>Adjust</Button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {tab === 'vendors' && (
          <div className="animate-fade-up p-5">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-[13px] text-ink-500">Suppliers medicines are purchased from.</p>
              {canPurchase && (
                <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setAddVendorOpen(true)}>
                  Add Vendor
                </Button>
              )}
            </div>
            {vendorsQuery.isLoading ? (
              <p className="py-10 text-center text-[14px] text-ink-500">Loading vendors…</p>
            ) : vendors.length === 0 ? (
              <InfoNote>No vendors yet. Add one before recording a purchase.</InfoNote>
            ) : (
              <div className="stagger grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {vendors.map((v) => (
                  <Card key={v.id} className="p-4" interactive onClick={() => setDetailVendorId(v.id)}>
                    <div className="flex items-center justify-between">
                      <p className="text-[14px] font-semibold text-ink-900">{v.name}</p>
                      <Badge tone={v.is_active ? 'completed' : 'neutral'} size="sm">{v.is_active ? 'Active' : 'Inactive'}</Badge>
                    </div>
                    <p className="tnum text-[12px] text-ink-500">{v.account_code}{v.city ? ` · ${v.city}` : ''}</p>
                    <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 border-t border-ink-100 pt-2.5 text-[12px]">
                      <span className="text-ink-400">Payment</span><span className="text-right capitalize text-ink-700">{v.payment_type}</span>
                      <span className="text-ink-400">Credit period</span><span className="tnum text-right text-ink-700">{v.credit_period_days} days</span>
                      <span className="text-ink-400">GST</span><span className="tnum text-right text-ink-700">{v.gst_number ?? '—'}</span>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'purchases' && (
          <div className="animate-fade-up p-5">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-[13px] text-ink-500">Purchase Entry → GRN. Receiving a purchase creates/updates the medicine's batch stock.</p>
              {canPurchase && (
                <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setAddPurchaseOpen(true)}>
                  New Purchase
                </Button>
              )}
            </div>
            {purchasesQuery.isLoading ? (
              <p className="py-10 text-center text-[14px] text-ink-500">Loading purchases…</p>
            ) : purchases.length === 0 ? (
              <InfoNote>No purchases recorded yet.</InfoNote>
            ) : (
              <div className="stagger space-y-2.5">
                {purchases.map((p) => (
                  <PurchaseRow key={p.id} purchase={p} vendorName={vendorNameById[p.vendor_id] ?? 'Vendor'} canReceive={canPurchase} />
                ))}
              </div>
            )}
          </div>
        )}

        {tab === 'sales' && (
          <div className="animate-fade-up stagger p-5">
            {sales.map((s, i) => (
              <div key={s.id} style={{ ['--i' as string]: i }} className="flex flex-wrap items-center gap-4 border-b border-ink-100 py-3.5 last:border-0">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-ink-100 text-ink-600">
                  <Receipt className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold text-ink-900">{s.patient} <span className="tnum font-normal text-ink-400">· {s.id}</span></p>
                  <p className="text-[13px] text-ink-500">{s.items}</p>
                  <p className="tnum text-[12px] text-ink-400">{s.date}</p>
                </div>
                <span className="tnum text-[14px] font-semibold text-ink-900">{formatINR(s.amount)}</span>
                <Badge tone={s.tone} size="sm">{s.status}</Badge>
              </div>
            ))}
          </div>
        )}

        {tab === 'returns' && (
          <SalesReturnTab sales={salesQuery.data ?? []} medicineNameById={medicineNameById} patientNameById={patientNameById} />
        )}

        {tab === 'indents' && (
          <IndentsTab
            indents={indentsQuery.data ?? []}
            isLoading={indentsQuery.isLoading}
            medicineNameById={medicineNameById}
            canRequest={canIndentRequest}
            canDeliver={canIndentDeliver}
            onAddIndent={() => setAddIndentOpen(true)}
            onOpenIndent={(id) => setDetailIndentId(id)}
          />
        )}

        {tab === 'templates' && (
          <TemplatesTab medicines={medicinesQuery.data ?? []} medicineNameById={medicineNameById} canManage={canManage} />
        )}

        {tab === 'purchase-orders' && (
          <PurchaseOrdersTab
            vendors={vendors} medicines={medicinesQuery.data ?? []} medicineNameById={medicineNameById}
            canCreate={canPOCreate} canApprove={canPOApprove} canReceive={canPurchase}
          />
        )}

        {tab === 'purchase-returns' && (
          <PurchaseReturnsTab purchases={purchases} vendorNameById={vendorNameById} medicineNameById={medicineNameById} canReturn={canPurchaseReturn} />
        )}

        {tab === 'reports' && <ReportsTab />}

        {tab === 'settings' && (
          <SettingsTab medicines={medicinesQuery.data ?? []} medicineNameById={medicineNameById} canManage={canSettingsManage} />
        )}
      </Card>
    </div>
  );
}

// =========================================================================
// Purchase row (with Receive/GRN action)
// =========================================================================

function PurchaseRow({ purchase, vendorName, canReceive }: { purchase: ReturnType<typeof usePharmacyPurchases>['data'] extends (infer T)[] | undefined ? T : never; vendorName: string; canReceive: boolean }) {
  const { toast } = useApp();
  const receive = useReceivePurchase();
  const STATUS_TONE: Record<string, 'completed' | 'attention' | 'critical' | 'neutral'> = {
    pending: 'attention', partially_received: 'attention', completed: 'completed', cancelled: 'neutral',
  };
  return (
    <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-ink-100 text-ink-600"><Truck className="h-4 w-4" /></div>
        <div>
          <p className="text-[14px] font-semibold text-ink-900">{purchase.purchase_number} <span className="tnum font-normal text-ink-400">· {vendorName}</span></p>
          <p className="tnum text-[12px] text-ink-500">{purchase.entry_date} · {purchase.lines.length} line{purchase.lines.length === 1 ? '' : 's'} · Net {formatINR(Math.round(purchase.total_value_paise / 100))}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Badge tone={STATUS_TONE[purchase.status]} size="sm">{purchase.status.replace('_', ' ')}</Badge>
        {canReceive && purchase.status === 'pending' && (
          <Button
            size="sm" variant="primary" loading={receive.isPending}
            onClick={() =>
              receive.mutate(purchase.id, {
                onSuccess: () => toast({ title: 'Stock received', body: `${purchase.purchase_number} marked completed.`, tone: 'success' }),
                onError: (e) => toast({ title: e instanceof ApiError ? e.message : 'Could not receive this purchase.', tone: 'error' }),
              })
            }
          >
            Receive (GRN)
          </Button>
        )}
      </div>
    </Card>
  );
}

// =========================================================================
// Add Medicine
// =========================================================================

function AddMedicineModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { toast } = useApp();
  const createMedicine = useCreateMedicine();
  const typesQuery = useMedicineAttributes('medicine_type');
  const createAttribute = useCreateMedicineAttribute();
  const [f, setF] = useState({ generic_name: '', brand_name: '', manufacturer: '', unit: '', category: '', hsn_code: '', gst_percent: '12', reorder_level: '0', medicine_type_id: '', new_type: '' });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f, v: string) => setF((s) => ({ ...s, [k]: v }));
  const reset = () => { setF({ generic_name: '', brand_name: '', manufacturer: '', unit: '', category: '', hsn_code: '', gst_percent: '12', reorder_level: '0', medicine_type_id: '', new_type: '' }); setError(null); createMedicine.reset(); };
  const close = () => { reset(); onClose(); };

  return (
    <Modal
      open={open} onClose={close} title="Add Medicine" subtitle="Basic catalogue entry — full details can be edited later."
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button
              variant="primary" disabled={!f.generic_name.trim() || !f.unit.trim() || createMedicine.isPending} loading={createMedicine.isPending}
              onClick={async () => {
                setError(null);
                let medicineTypeId = f.medicine_type_id || undefined;
                try {
                  if (!medicineTypeId && f.new_type.trim()) {
                    const attr = await createAttribute.mutateAsync({ attribute_type: 'medicine_type', name: f.new_type.trim() });
                    medicineTypeId = attr.id;
                  }
                  createMedicine.mutate(
                    {
                      generic_name: f.generic_name.trim(), brand_name: f.brand_name.trim() || null,
                      manufacturer: f.manufacturer.trim() || null, unit: f.unit.trim(),
                      category: f.category.trim() || null, hsn_code: f.hsn_code.trim() || null,
                      gst_percent: Number(f.gst_percent) || 0, reorder_level: Number(f.reorder_level) || 0,
                      medicine_type_id: medicineTypeId ?? null,
                    },
                    {
                      onSuccess: () => { close(); toast({ title: 'Medicine added', tone: 'success' }); },
                      onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not add the medicine.'),
                    }
                  );
                } catch (e) {
                  setError(e instanceof ApiError ? e.message : 'Could not add the medicine type.');
                }
              }}
            >
              Add Medicine
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Generic name" placeholder="Paracetamol" value={f.generic_name} onChange={(e) => set('generic_name', e.target.value)} />
          <Input label="Brand name" placeholder="Crocin" value={f.brand_name} onChange={(e) => set('brand_name', e.target.value)} />
          <Select label="Medicine type" value={f.medicine_type_id} onChange={(e) => set('medicine_type_id', e.target.value)}>
            <option value="">{f.new_type ? 'Use new type below' : 'Select a type…'}</option>
            {(typesQuery.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </Select>
          <Input label="Or add new type" placeholder="e.g. Suppository" value={f.new_type} onChange={(e) => set('new_type', e.target.value)} />
          <Input label="Manufacturer" value={f.manufacturer} onChange={(e) => set('manufacturer', e.target.value)} />
          <Input label="Category" placeholder="Antibiotic" value={f.category} onChange={(e) => set('category', e.target.value)} />
          <Input label="Unit" placeholder="Strip / Vial / Box" value={f.unit} onChange={(e) => set('unit', e.target.value)} />
          <Input label="HSN code" value={f.hsn_code} onChange={(e) => set('hsn_code', e.target.value)} />
          <Input label="Sales tax %" type="number" value={f.gst_percent} onChange={(e) => set('gst_percent', e.target.value)} />
          <Input label="Minimum stock" type="number" value={f.reorder_level} onChange={(e) => set('reorder_level', e.target.value)} />
        </div>
      </div>
    </Modal>
  );
}

// =========================================================================
// Add Vendor
// =========================================================================

function AddVendorModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { toast } = useApp();
  const createVendor = useCreateVendor();
  const [f, setF] = useState({ name: '', account_code: '', city: '', gst_number: '', payment_type: 'credit', credit_period_days: '0' });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f, v: string) => setF((s) => ({ ...s, [k]: v }));
  const reset = () => { setF({ name: '', account_code: '', city: '', gst_number: '', payment_type: 'credit', credit_period_days: '0' }); setError(null); createVendor.reset(); };
  const close = () => { reset(); onClose(); };

  return (
    <Modal
      open={open} onClose={close} title="Add Vendor"
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button
              variant="primary" disabled={!f.name.trim() || !f.account_code.trim() || createVendor.isPending} loading={createVendor.isPending}
              onClick={() => {
                setError(null);
                createVendor.mutate(
                  { name: f.name.trim(), account_code: f.account_code.trim(), city: f.city.trim() || null, gst_number: f.gst_number.trim() || null, payment_type: f.payment_type as any, credit_period_days: Number(f.credit_period_days) || 0 },
                  { onSuccess: () => { close(); toast({ title: 'Vendor added', tone: 'success' }); }, onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not add the vendor.') }
                );
              }}
            >
              Add Vendor
            </Button>
          </div>
        </div>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Vendor name" value={f.name} onChange={(e) => set('name', e.target.value)} />
        <Input label="Account code" placeholder="Unique code" value={f.account_code} onChange={(e) => set('account_code', e.target.value)} />
        <Input label="City" value={f.city} onChange={(e) => set('city', e.target.value)} />
        <Input label="GST number" value={f.gst_number} onChange={(e) => set('gst_number', e.target.value)} />
        <Select label="Payment type" value={f.payment_type} onChange={(e) => set('payment_type', e.target.value)}>
          {['credit', 'cash', 'card', 'cheque', 'rtgs', 'transaction'].map((p) => <option key={p} value={p}>{p}</option>)}
        </Select>
        <Input label="Credit period (days)" type="number" value={f.credit_period_days} onChange={(e) => set('credit_period_days', e.target.value)} />
      </div>
    </Modal>
  );
}

// =========================================================================
// New Purchase (multi-line entry)
// =========================================================================

function AddPurchaseModal({ open, onClose, vendors, medicines }: { open: boolean; onClose: () => void; vendors: { id: string; name: string }[]; medicines: { id: string; generic_name: string; brand_name: string | null }[] }) {
  const { toast } = useApp();
  const createPurchase = useCreatePurchase();
  const [vendorId, setVendorId] = useState('');
  const [entryDate, setEntryDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [lines, setLines] = useState<PurchaseLineCreate[]>([]);
  const [error, setError] = useState<string | null>(null);

  const addLine = () => setLines((l) => [...l, { medicine_id: '', batch_number: '', quantity: 1, free_quantity: 0, purchase_rate_paise: 0, selling_price_paise: 0, discount_percent: 0, expiry_date: '', hsn_code: '', tax_percent: 12 }]);
  const updateLine = (i: number, patch: Partial<PurchaseLineCreate>) => setLines((l) => l.map((row, idx) => (idx === i ? { ...row, ...patch } : row)));
  const removeLine = (i: number) => setLines((l) => l.filter((_, idx) => idx !== i));

  const reset = () => { setVendorId(''); setEntryDate(new Date().toISOString().slice(0, 10)); setInvoiceNumber(''); setLines([]); setError(null); createPurchase.reset(); };
  const close = () => { reset(); onClose(); };

  const netTotal = lines.reduce((sum, l) => {
    const gross = (l.quantity || 0) * (l.purchase_rate_paise || 0);
    const disc = Math.round((gross * (l.discount_percent || 0)) / 100);
    const taxable = gross - disc;
    const tax = Math.round((taxable * (l.tax_percent || 0)) / 100);
    return sum + taxable + tax;
  }, 0);

  return (
    <Modal
      open={open} onClose={close} title="New Purchase Entry" subtitle="Add every medicine on the vendor's invoice, then submit. Receive (GRN) later brings it into stock."
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex items-center gap-3">
            <p className="tnum text-[13px] text-ink-600">Net total: <span className="font-semibold text-ink-900">{formatINR(Math.round(netTotal / 100))}</span></p>
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button
              variant="primary" disabled={!vendorId || lines.length === 0 || createPurchase.isPending} loading={createPurchase.isPending}
              onClick={() => {
                setError(null);
                if (lines.some((l) => !l.medicine_id || !l.batch_number.trim() || !l.expiry_date)) {
                  setError('Every line needs a medicine, batch number and expiry date.');
                  return;
                }
                createPurchase.mutate(
                  { vendor_id: vendorId, entry_date: entryDate, invoice_number: invoiceNumber.trim() || null, lines },
                  { onSuccess: () => { close(); toast({ title: 'Purchase recorded', body: 'Use Receive (GRN) to bring it into stock.', tone: 'success' }); }, onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not save the purchase.') }
                );
              }}
            >
              Save Purchase
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
          <Input label="Invoice number" value={invoiceNumber} onChange={(e) => setInvoiceNumber(e.target.value)} />
          <Input label="Entry date" type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} />
        </div>

        <div className="space-y-3">
          {lines.map((line, i) => (
            <Card key={i} className="p-3">
              <div className="grid gap-2.5 sm:grid-cols-4">
                <Select label="Medicine" value={line.medicine_id} onChange={(e) => updateLine(i, { medicine_id: e.target.value })}>
                  <option value="">Select…</option>
                  {medicines.map((m) => <option key={m.id} value={m.id}>{m.brand_name ?? m.generic_name}</option>)}
                </Select>
                <Input label="Batch no." value={line.batch_number} onChange={(e) => updateLine(i, { batch_number: e.target.value })} />
                <Input label="Expiry" type="date" value={line.expiry_date} onChange={(e) => updateLine(i, { expiry_date: e.target.value })} />
                <Input label="Qty" type="number" value={String(line.quantity)} onChange={(e) => updateLine(i, { quantity: Number(e.target.value) || 0 })} />
                <Input label="Free qty" type="number" value={String(line.free_quantity)} onChange={(e) => updateLine(i, { free_quantity: Number(e.target.value) || 0 })} />
                <Input label="Purchase rate (₹)" type="number" value={String((line.purchase_rate_paise || 0) / 100)} onChange={(e) => updateLine(i, { purchase_rate_paise: Math.round(Number(e.target.value) * 100) || 0 })} />
                <Input label="Selling price (₹)" type="number" value={String((line.selling_price_paise || 0) / 100)} onChange={(e) => updateLine(i, { selling_price_paise: Math.round(Number(e.target.value) * 100) || 0 })} />
                <Input label="Discount %" type="number" value={String(line.discount_percent)} onChange={(e) => updateLine(i, { discount_percent: Number(e.target.value) || 0 })} />
                <Input label="Tax %" type="number" value={String(line.tax_percent)} onChange={(e) => updateLine(i, { tax_percent: Number(e.target.value) || 0 })} />
                <Input label="HSN" value={line.hsn_code ?? ''} onChange={(e) => updateLine(i, { hsn_code: e.target.value })} />
              </div>
              <button onClick={() => removeLine(i)} className="mt-2 text-[12px] font-medium text-rose-600 hover:text-rose-700">Remove line</button>
            </Card>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={addLine}>Add medicine line</Button>
        </div>
      </div>
    </Modal>
  );
}

// =========================================================================
// Manual Stock Adjustment
// =========================================================================

function StockAdjustModal({ row, onClose }: { row: { batch_id: string; medicine_name: string; batch_number: string; quantity_available: number }; onClose: () => void }) {
  const { toast } = useApp();
  const adjust = useAdjustStock();
  const [physical, setPhysical] = useState(String(row.quantity_available));
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const difference = (Number(physical) || 0) - row.quantity_available;

  return (
    <Modal
      open onClose={onClose} title="Stock Adjustment" subtitle={`${row.medicine_name} · Batch ${row.batch_number}`}
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button
              variant="primary" loading={adjust.isPending}
              onClick={() => {
                setError(null);
                adjust.mutate(
                  { batch_id: row.batch_id, physical_stock: Number(physical) || 0, reason: reason.trim() || null },
                  { onSuccess: () => { onClose(); toast({ title: 'Stock adjusted', tone: 'success' }); }, onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not save the adjustment.') }
                );
              }}
            >
              Save Adjustment
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Field label="System stock" value={String(row.quantity_available)} />
        <Input label="Physical (counted) stock" type="number" value={physical} onChange={(e) => setPhysical(e.target.value)} />
        <p className={cn('text-[13px] font-medium', difference === 0 ? 'text-ink-500' : difference > 0 ? 'text-emerald-600' : 'text-rose-600')}>
          Difference: {difference > 0 ? '+' : ''}{difference}
        </p>
        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Reason</span>
          <textarea className="min-h-[70px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900" placeholder="Physical count / damage / expiry write-off…" value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
      </div>
    </Modal>
  );
}

// =========================================================================
// Sales Dashboard
// =========================================================================

const PAYMENT_LABEL: Record<PaymentMethod, string> = { cash: 'Cash', card: 'Card', cheque: 'Cheque', online: 'Online' };
const SALE_STATUS_TONE: Record<string, 'completed' | 'attention' | 'critical' | 'neutral'> = {
  dispensed: 'completed', partially_returned: 'attention', returned: 'neutral',
};

function SalesDashboardTab({
  sales, isLoading, patientNameById, patientUhidById, doctorNameById, doctors,
}: {
  sales: SaleOut[];
  isLoading: boolean;
  patientNameById: Record<string, string>;
  patientUhidById: Record<string, string>;
  doctorNameById: Record<string, string>;
  doctors: { id: string; full_name: string }[];
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [fromDate, setFromDate] = useState(today);
  const [toDate, setToDate] = useState(today);
  const [search, setSearch] = useState('');
  const [doctorId, setDoctorId] = useState('');
  const [paymentFilter, setPaymentFilter] = useState<'' | PaymentMethod>('');

  const filtered = useMemo(() => {
    const from = new Date(fromDate + 'T00:00:00');
    const to = new Date(toDate + 'T23:59:59');
    const term = search.trim().toLowerCase();
    return sales.filter((s) => {
      const billDate = new Date(s.created_at);
      if (billDate < from || billDate > to) return false;
      if (doctorId && s.prescribed_by_id !== doctorId) return false;
      if (paymentFilter && s.payment_method !== paymentFilter) return false;
      if (term) {
        const patient = (patientNameById[s.patient_id] ?? '').toLowerCase();
        if (!patient.includes(term) && !s.bill_number.toLowerCase().includes(term)) return false;
      }
      return true;
    });
  }, [sales, fromDate, toDate, search, doctorId, paymentFilter, patientNameById]);

  const totals = useMemo(() => {
    const byMethod: Record<PaymentMethod, number> = { cash: 0, card: 0, cheque: 0, online: 0 };
    let gross = 0;
    let discount = 0;
    let returnedBills = 0;
    for (const s of filtered) {
      byMethod[s.payment_method] += s.total_amount_paise;
      gross += s.total_amount_paise;
      discount += s.discount_paise;
      if (s.status !== 'dispensed') returnedBills += 1;
    }
    return { byMethod, gross, discount, returnedBills };
  }, [filtered]);

  return (
    <div className="animate-fade-up space-y-5 p-5">
      <div className="flex flex-wrap items-end gap-3">
        <Input label="From" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        <Input label="To" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        <div className="min-w-[200px] flex-1">
          <Input label="Search" icon={<Search className="h-3.5 w-3.5" />} placeholder="Patient or bill number…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="w-48">
          <Select label="Doctor" value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
            <option value="">All doctors</option>
            {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
          </Select>
        </div>
        <div className="w-36">
          <Select label="Payment" value={paymentFilter} onChange={(e) => setPaymentFilter(e.target.value as '' | PaymentMethod)}>
            <option value="">All methods</option>
            {(Object.keys(PAYMENT_LABEL) as PaymentMethod[]).map((p) => <option key={p} value={p}>{PAYMENT_LABEL[p]}</option>)}
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Metric label="Total Sales" value={Math.round(totals.gross / 100)} icon={IndianRupee} tone="bg-emerald-50 text-emerald-700 ring-emerald-600/12" currency />
        <Metric label="Cash" value={Math.round(totals.byMethod.cash / 100)} icon={Banknote} tone="bg-sky-50 text-sky-700 ring-sky-600/12" currency />
        <Metric label="Card" value={Math.round(totals.byMethod.card / 100)} icon={CreditCard} tone="bg-violet-50 text-violet-700 ring-violet-600/12" currency />
        <Metric label="Cheque" value={Math.round(totals.byMethod.cheque / 100)} icon={FileText} tone="bg-amber-50 text-amber-700 ring-amber-600/12" currency />
        <Metric label="Online" value={Math.round(totals.byMethod.online / 100)} icon={Smartphone} tone="bg-rose-50 text-rose-700 ring-rose-600/12" currency />
        <Metric label="Discounts Given" value={Math.round(totals.discount / 100)} icon={RotateCcw} tone="bg-ink-100 text-ink-600 ring-ink-300/40" currency />
      </div>

      {isLoading ? (
        <p className="py-10 text-center text-[14px] text-ink-500">Loading sales…</p>
      ) : filtered.length === 0 ? (
        <InfoNote>No bills in this range. Use "New Bill" to record one.</InfoNote>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-ink-200/70 text-[11.5px] font-semibold uppercase tracking-[0.08em] text-ink-400">
                <th className="py-2 pr-3">UHID</th><th className="py-2 pr-3">Patient</th><th className="py-2 pr-3">Doctor</th>
                <th className="py-2 pr-3">Bill Date</th><th className="py-2 pr-3">Bill No.</th><th className="py-2 pr-3">Amount</th>
                <th className="py-2 pr-3">Payment</th><th className="py-2 pr-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id} className="border-b border-ink-100 last:border-0">
                  <td className="tnum py-2.5 pr-3 text-ink-500">{patientUhidById[s.patient_id] ?? '—'}</td>
                  <td className="py-2.5 pr-3 font-medium text-ink-900">{patientNameById[s.patient_id] ?? 'Unknown'}</td>
                  <td className="py-2.5 pr-3 text-ink-600">{s.prescribed_by_id ? (doctorNameById[s.prescribed_by_id] ?? '—') : '—'}</td>
                  <td className="tnum py-2.5 pr-3 text-ink-500">{new Date(s.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</td>
                  <td className="tnum py-2.5 pr-3 text-ink-600">{s.bill_number}</td>
                  <td className="tnum py-2.5 pr-3 font-semibold text-ink-900">{formatINR(Math.round(s.total_amount_paise / 100))}</td>
                  <td className="py-2.5 pr-3 text-ink-600">{PAYMENT_LABEL[s.payment_method]}</td>
                  <td className="py-2.5 pr-3"><Badge tone={SALE_STATUS_TONE[s.status] ?? 'neutral'} size="sm">{s.status.replace('_', ' ')}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// =========================================================================
// New Bill (billing)
// =========================================================================

interface BillLine {
  key: number;
  medicine_id: string;
  quantity: number;
}

function NewBillModal({
  open, onClose, medicines, patients, doctors,
}: {
  open: boolean;
  onClose: () => void;
  medicines: MedicineOut[];
  patients: { id: string; full_name: string; uhid: string }[];
  doctors: { id: string; full_name: string }[];
}) {
  const { toast } = useApp();
  const dispense = useDispenseSale();
  const [patientId, setPatientId] = useState('');
  const [doctorId, setDoctorId] = useState('');
  const [lines, setLines] = useState<BillLine[]>([{ key: 0, medicine_id: '', quantity: 1 }]);
  const nextKey = useRef(1);
  const [discountRupees, setDiscountRupees] = useState('0');
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('cash');
  const [error, setError] = useState<string | null>(null);
  const [savedBill, setSavedBill] = useState<{ bill_number: string; amount: number; method: PaymentMethod } | null>(null);


  const reset = () => {
    setPatientId(''); setDoctorId(''); setLines([{ key: 0, medicine_id: '', quantity: 1 }]);
    setDiscountRupees('0'); setPaymentMethod('cash'); setError(null); setSavedBill(null); dispense.reset();
  };
  const close = () => { reset(); onClose(); };

  const addLine = () => { setLines((l) => [...l, { key: nextKey.current++, medicine_id: '', quantity: 1 }]); };
  const updateLine = (key: number, patch: Partial<BillLine>) =>
    setLines((l) => l.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  const removeLine = (key: number) => setLines((l) => (l.length > 1 ? l.filter((row) => row.key !== key) : l));

  const medicineById = useMemo(() => {
    const map: Record<string, MedicineOut> = {};
    for (const m of medicines) map[m.id] = m;
    return map;
  }, [medicines]);

  // Net amount is computed by NewBillLineTotals below (a sibling helper
  // that subscribes to the same per-line medicine queries React Query
  // already caches, so this doesn't duplicate any fetch).
  const [lineTotals, setLineTotals] = useState<Record<number, number>>({});
  const reportLineTotal = (key: number, total: number) =>
    setLineTotals((prev) => (prev[key] === total ? prev : { ...prev, [key]: total }));

  const grossPaise = lines.reduce((sum, l) => sum + (lineTotals[l.key] ?? 0), 0);
  const discountPaise = Math.min(Math.round((Number(discountRupees) || 0) * 100), grossPaise);
  const balancePaise = Math.max(grossPaise - discountPaise, 0);

  const PAYMENT_OPTIONS: { id: PaymentMethod; label: string; icon: any }[] = [
    { id: 'cash', label: 'Cash', icon: Banknote },
    { id: 'card', label: 'Card', icon: CreditCard },
    { id: 'cheque', label: 'Cheque', icon: FileText },
    { id: 'online', label: 'Online', icon: Smartphone },
  ];

  return (
    <Modal
      open={open} onClose={close} title="New Bill" subtitle="Batch is auto-selected (FEFO) — same rule as every other dispense."
      footer={
        savedBill ? (
          <div className="flex items-center justify-between gap-3">
            <p className="text-[13px] font-medium text-emerald-700">
              ✅ Bill {savedBill.bill_number} saved — {formatINR(Math.round(savedBill.amount / 100))} via {PAYMENT_LABEL[savedBill.method]}
            </p>
            <Button variant="primary" onClick={close}>Done</Button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3">
            {error && <p className="text-[13px] text-rose-600">{error}</p>}
            <div className="ml-auto flex items-center gap-3">
              <p className="tnum text-[13px] text-ink-600">Balance: <span className="font-semibold text-ink-900">{formatINR(Math.round(balancePaise / 100))}</span></p>
              <Button variant="ghost" onClick={close}>Cancel</Button>
              <Button
                variant="primary" disabled={!patientId || lines.every((l) => !l.medicine_id) || dispense.isPending} loading={dispense.isPending}
                onClick={() => {
                  setError(null);
                  const validLines = lines.filter((l) => l.medicine_id && l.quantity > 0);
                  if (validLines.length === 0) { setError('Add at least one medicine.'); return; }
                  dispense.mutate(
                    {
                      patient_id: patientId, prescribed_by_id: doctorId || null,
                      lines: validLines.map((l) => ({ medicine_id: l.medicine_id, quantity: l.quantity })),
                      discount_paise: discountPaise, payment_method: paymentMethod,
                    },
                    {
                      onSuccess: (sale) => {
                        setSavedBill({ bill_number: sale.bill_number, amount: sale.total_amount_paise, method: sale.payment_method });
                        toast({ title: `Bill ${sale.bill_number} saved`, tone: 'success' });
                      },
                      onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not save this bill.'),
                    }
                  );
                }}
              >
                Save Bill
              </Button>
            </div>
          </div>
        )
      }
    >
      {savedBill ? (
        <InfoNote tone="brand">Stock has been deducted and the sale recorded. Refresh Current Stock / Sales Dashboard to see it reflected.</InfoNote>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Patient" value={patientId} onChange={(e) => setPatientId(e.target.value)}>
              <option value="">Select a patient…</option>
              {patients.map((p) => <option key={p.id} value={p.id}>{p.full_name} ({p.uhid})</option>)}
            </Select>
            <Select label="Doctor (optional)" value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
              <option value="">None</option>
              {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
            </Select>
          </div>

          <div className="space-y-3">
            {lines.map((line) => (
              <BillLineRowWithTotal
                key={line.key}
                line={line}
                medicines={medicines}
                onChange={(patch) => updateLine(line.key, patch)}
                onRemove={() => removeLine(line.key)}
                onTotal={(total) => reportLineTotal(line.key, total)}
              />
            ))}
            <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={addLine}>Add medicine</Button>
          </div>

          <Card className="space-y-3 p-4">
            <div className="flex items-center justify-between text-[14px]"><span className="text-ink-500">Net Amount</span><span className="tnum font-semibold text-ink-900">{formatINR(Math.round(grossPaise / 100))}</span></div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-[14px] text-ink-500">Discount (₹)</span>
              <input
                type="number" min={0} value={discountRupees} onChange={(e) => setDiscountRupees(e.target.value)}
                className="h-9 w-28 rounded-lg border border-ink-200 px-2 text-right text-[14px] text-ink-900"
              />
            </div>
            <div className="flex items-center justify-between border-t border-ink-100 pt-3 text-[15px] font-semibold">
              <span className="text-ink-700">Balance</span><span className="tnum text-ink-900">{formatINR(Math.round(balancePaise / 100))}</span>
            </div>
          </Card>

          <div>
            <p className="mb-1.5 text-[13.5px] font-medium text-ink-700">Payment method</p>
            <div className="grid grid-cols-4 gap-2">
              {PAYMENT_OPTIONS.map((opt) => {
                const Icon = opt.icon;
                const active = paymentMethod === opt.id;
                return (
                  <button
                    key={opt.id}
                    onClick={() => setPaymentMethod(opt.id)}
                    className={cn(
                      'flex flex-col items-center gap-1 rounded-xl border p-3 text-[12.5px] font-medium transition-colors',
                      active ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-ink-200 text-ink-600 hover:bg-ink-50'
                    )}
                  >
                    <Icon className="h-4 w-4" /> {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}

/** Wraps BillLineRow to also report its computed line total upward, so the
 * parent's Net Amount/Balance stay accurate without re-fetching anything. */
function BillLineRowWithTotal({
  line, medicines, onChange, onRemove, onTotal,
}: {
  line: BillLine;
  medicines: MedicineOut[];
  onChange: (patch: Partial<BillLine>) => void;
  onRemove: () => void;
  onTotal: (total: number) => void;
}) {
  const medicineDetail = useMedicine(line.medicine_id || null);
  const fefoBatch = useMemo(() => {
    const batches = (medicineDetail.data?.batches ?? []).filter((b) => b.quantity_available > 0);
    return [...batches].sort((a, b) => a.expiry_date.localeCompare(b.expiry_date))[0] ?? null;
  }, [medicineDetail.data]);
  const rate = fefoBatch?.selling_rate_paise ?? 0;
  const total = rate * (line.quantity || 0);

  React.useEffect(() => {
    onTotal(total);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [total]);

  return (
    <Card className="p-3">
      <div className="grid gap-2.5 sm:grid-cols-5">
        <div className="sm:col-span-2">
          <Select label="Medicine" value={line.medicine_id} onChange={(e) => onChange({ medicine_id: e.target.value })}>
            <option value="">Select…</option>
            {medicines.map((m) => <option key={m.id} value={m.id}>{m.brand_name ?? m.generic_name}</option>)}
          </Select>
        </div>
        <Input label="Qty" type="number" min={1} value={String(line.quantity)} onChange={(e) => onChange({ quantity: Number(e.target.value) || 0 })} />
        <Field label="Rate (FEFO batch)" value={rate ? `₹${(rate / 100).toFixed(2)}` : '—'} />
        <Field label="Line total" value={formatINR(Math.round(total / 100))} />
      </div>
      {line.medicine_id && !medicineDetail.isLoading && !fefoBatch && (
        <p className="mt-2 text-[12px] text-rose-600">No stock available for this medicine.</p>
      )}
      <button onClick={onRemove} className="mt-2 flex items-center gap-1 text-[12px] font-medium text-rose-600 hover:text-rose-700">
        <Trash2 className="h-3 w-3" /> Remove
      </button>
    </Card>
  );
}

// =========================================================================
// Medicine Detail / Edit — the module's "editing is a core requirement":
// every field below is corrigible after creation and persists to the
// backend (PATCH /pharmacy/medicines/{id}); batch expiry is corrected
// separately via PATCH /pharmacy/batches/{id}/expiry, never by touching
// quantity/rate history.
// =========================================================================

function MedicineDetailModal({ medicineId, canManage, onClose }: { medicineId: string; canManage: boolean; onClose: () => void }) {
  const { toast } = useApp();
  const medicineQuery = useMedicine(medicineId);
  const updateMedicine = useUpdateMedicine();
  const correctExpiry = useCorrectBatchExpiry();
  const [medTab, setMedTab] = useState('overview');
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<MedicineUpdate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expiryEdits, setExpiryEdits] = useState<Record<string, string>>({});

  const medicine = medicineQuery.data;

  const startEdit = (m: MedicineDetailOut) => {
    setForm({
      generic_name: m.generic_name, brand_name: m.brand_name, manufacturer: m.manufacturer,
      category: m.category, unit: m.unit, hsn_code: m.hsn_code, barcode: m.barcode,
      item_code: m.item_code, rack_number: m.rack_number,
      mrp_paise: m.mrp_paise, gst_percent: m.gst_percent, purchase_tax_percent: m.purchase_tax_percent,
      reorder_level: m.reorder_level, minimum_stock: m.minimum_stock, maximum_stock: m.maximum_stock,
      scheduled_drug: m.scheduled_drug, is_active: m.is_active,
    });
    setEditing(true);
    setError(null);
  };

  const set = (patch: Partial<MedicineUpdate>) => setForm((f) => (f ? { ...f, ...patch } : f));

  const save = () => {
    if (!form) return;
    setError(null);
    updateMedicine.mutate(
      { medicineId, ...form },
      {
        onSuccess: () => { setEditing(false); toast({ title: 'Medicine updated', tone: 'success' }); },
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not save changes.'),
      }
    );
  };

  const saveExpiry = (batchId: string) => {
    const value = expiryEdits[batchId];
    if (!value) return;
    correctExpiry.mutate(
      { batchId, expiryDate: value, medicineId },
      {
        onSuccess: () => { toast({ title: 'Expiry corrected', tone: 'success' }); setExpiryEdits((e) => { const n = { ...e }; delete n[batchId]; return n; }); },
        onError: (e) => toast({ title: e instanceof ApiError ? e.message : 'Could not correct the expiry.', tone: 'error' }),
      }
    );
  };

  return (
    <Modal
      open onClose={onClose} title={medicine ? (medicine.brand_name ?? medicine.generic_name) : 'Medicine'}
      subtitle={medicine ? `${medicine.generic_name}${medicine.manufacturer ? ` · ${medicine.manufacturer}` : ''}` : undefined}
      footer={
        editing ? (
          <div className="flex items-center justify-between gap-3">
            {error && <p className="text-[13px] text-rose-600">{error}</p>}
            <div className="ml-auto flex gap-2">
              <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
              <Button variant="primary" loading={updateMedicine.isPending} onClick={save}>Save Changes</Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3">
            <Badge tone={medicine?.is_active ? 'completed' : 'neutral'} size="sm">{medicine?.is_active ? 'Active' : 'Inactive'}</Badge>
            <div className="ml-auto flex gap-2">
              <Button variant="ghost" onClick={onClose}>Close</Button>
              {canManage && medicine && (
                <Button variant="primary" icon={<Pencil className="h-3.5 w-3.5" />} onClick={() => startEdit(medicine)}>Edit</Button>
              )}
            </div>
          </div>
        )
      }
    >
      {!medicine ? (
        <p className="py-10 text-center text-[14px] text-ink-500">Loading…</p>
      ) : editing && form ? (
        <div className="space-y-4">
          <p className="text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-400">Basic information</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Medicine name" value={form.generic_name ?? ''} onChange={(e) => set({ generic_name: e.target.value })} />
            <Input label="Brand name" value={form.brand_name ?? ''} onChange={(e) => set({ brand_name: e.target.value })} />
            <Input label="Manufacturer" value={form.manufacturer ?? ''} onChange={(e) => set({ manufacturer: e.target.value })} />
            <Input label="Category" value={form.category ?? ''} onChange={(e) => set({ category: e.target.value })} />
            <Input label="Unit" value={form.unit ?? ''} onChange={(e) => set({ unit: e.target.value })} />
            <Input label="Barcode" value={form.barcode ?? ''} onChange={(e) => set({ barcode: e.target.value })} />
            <Input label="Item code" value={form.item_code ?? ''} onChange={(e) => set({ item_code: e.target.value })} />
            <Input label="Rack number" value={form.rack_number ?? ''} onChange={(e) => set({ rack_number: e.target.value })} />
            <Input label="HSN code" value={form.hsn_code ?? ''} onChange={(e) => set({ hsn_code: e.target.value })} />
          </div>

          <p className="pt-2 text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-400">Pricing & tax</p>
          <div className="grid gap-3 sm:grid-cols-3">
            <Input label="MRP (₹)" type="number" value={form.mrp_paise != null ? String(form.mrp_paise / 100) : ''} onChange={(e) => set({ mrp_paise: e.target.value ? Math.round(Number(e.target.value) * 100) : null })} />
            <Input label="Sales tax %" type="number" value={String(form.gst_percent ?? 0)} onChange={(e) => set({ gst_percent: Number(e.target.value) || 0 })} />
            <Input label="Purchase tax %" type="number" value={String(form.purchase_tax_percent ?? 0)} onChange={(e) => set({ purchase_tax_percent: Number(e.target.value) || 0 })} />
          </div>

          <p className="pt-2 text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-400">Stock configuration</p>
          <div className="grid gap-3 sm:grid-cols-3">
            <Input label="Minimum stock" type="number" value={String(form.minimum_stock ?? 0)} onChange={(e) => set({ minimum_stock: Number(e.target.value) || 0 })} />
            <Input label="Maximum stock" type="number" value={form.maximum_stock != null ? String(form.maximum_stock) : ''} onChange={(e) => set({ maximum_stock: e.target.value ? Number(e.target.value) : null })} />
            <Input label="Reorder level" type="number" value={String(form.reorder_level ?? 0)} onChange={(e) => set({ reorder_level: Number(e.target.value) || 0 })} />
          </div>

          <p className="pt-2 text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-400">Configuration</p>
          <div className="flex flex-wrap gap-6">
            <Switch label="Scheduled drug" checked={!!form.scheduled_drug} onChange={(v) => set({ scheduled_drug: v })} />
            <Switch label="Active" checked={form.is_active !== false} onChange={(v) => set({ is_active: v })} />
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <Tabs
            tabs={[
              { id: 'overview', label: 'Overview' },
              { id: 'pricing', label: 'Pricing' },
              { id: 'batches', label: `Batches (${medicine.batches.length})` },
              { id: 'config', label: 'Configuration' },
            ]}
            active={medTab}
            onChange={setMedTab}
          />

          {medTab === 'overview' && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Generic name" value={medicine.generic_name} />
              <Field label="Category" value={medicine.category ?? '—'} />
              <Field label="Manufacturer" value={medicine.manufacturer ?? '—'} />
              <Field label="Unit" value={medicine.unit} />
              <Field label="Barcode" value={medicine.barcode ?? '—'} />
              <Field label="Item code" value={medicine.item_code ?? '—'} />
              <Field label="Rack number" value={medicine.rack_number ?? '—'} />
              <Field label="HSN code" value={medicine.hsn_code ?? '—'} />
              <Field label="Total available" value={`${medicine.total_available} ${medicine.unit}`} />
            </div>
          )}

          {medTab === 'pricing' && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="MRP" value={medicine.mrp_paise != null ? `₹${(medicine.mrp_paise / 100).toFixed(2)}` : '—'} />
              <Field label="Sales tax" value={`${medicine.gst_percent}%`} />
              <Field label="Purchase tax" value={`${medicine.purchase_tax_percent}%`} />
            </div>
          )}

          {medTab === 'batches' && (
            <div className="space-y-2.5">
              {medicine.batches.length === 0 ? (
                <InfoNote>No batches yet — received via Purchases &amp; GRN.</InfoNote>
              ) : (
                medicine.batches.map((b) => (
                  <div key={b.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-ink-100 p-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-[13.5px] font-semibold text-ink-900">{b.batch_number}</p>
                      <p className="tnum text-[12px] text-ink-500">{b.quantity_available} {medicine.unit} available · ₹{(b.selling_rate_paise / 100).toFixed(2)}</p>
                    </div>
                    {canManage ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="date" defaultValue={b.expiry_date}
                          onChange={(e) => setExpiryEdits((prev) => ({ ...prev, [b.id]: e.target.value }))}
                          className="h-9 rounded-lg border border-ink-200 px-2 text-[13px] text-ink-900"
                        />
                        <Button size="sm" variant="secondary" disabled={!expiryEdits[b.id]} loading={correctExpiry.isPending} onClick={() => saveExpiry(b.id)}>
                          Correct
                        </Button>
                      </div>
                    ) : (
                      <span className="tnum text-[13px] text-ink-600">{b.expiry_date}</span>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {medTab === 'config' && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Minimum stock" value={String(medicine.minimum_stock)} />
              <Field label="Maximum stock" value={medicine.maximum_stock != null ? String(medicine.maximum_stock) : '—'} />
              <Field label="Reorder level" value={String(medicine.reorder_level)} />
              <Field label="Scheduled drug" value={medicine.scheduled_drug ? 'Yes' : 'No'} />
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

// =========================================================================
// Vendor Detail / Edit
// =========================================================================

function VendorDetailModal({ vendorId, canManage, onClose }: { vendorId: string; canManage: boolean; onClose: () => void }) {
  const { toast } = useApp();
  const vendorsQuery = useVendors(true);
  const updateVendor = useUpdateVendor();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<VendorOut> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const vendor = (vendorsQuery.data ?? []).find((v) => v.id === vendorId) ?? null;

  const startEdit = (v: VendorOut) => {
    setForm({ ...v });
    setEditing(true);
    setError(null);
  };
  const set = (patch: Partial<VendorOut>) => setForm((f) => (f ? { ...f, ...patch } : f));

  const save = () => {
    if (!form) return;
    setError(null);
    updateVendor.mutate(
      {
        vendorId, name: form.name, city: form.city, gst_number: form.gst_number,
        payment_type: form.payment_type, credit_period_days: form.credit_period_days,
        bank_account_number: form.bank_account_number, bank_name: form.bank_name, ifsc_code: form.ifsc_code,
        contact_phone: form.contact_phone, contact_email: form.contact_email, address: form.address,
        is_active: form.is_active,
      },
      {
        onSuccess: () => { setEditing(false); toast({ title: 'Vendor updated', tone: 'success' }); },
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not save changes.'),
      }
    );
  };

  return (
    <Modal
      open onClose={onClose} title={vendor?.name ?? 'Vendor'} subtitle={vendor?.account_code}
      footer={
        editing ? (
          <div className="flex items-center justify-between gap-3">
            {error && <p className="text-[13px] text-rose-600">{error}</p>}
            <div className="ml-auto flex gap-2">
              <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
              <Button variant="primary" loading={updateVendor.isPending} onClick={save}>Save Changes</Button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3">
            <Badge tone={vendor?.is_active ? 'completed' : 'neutral'} size="sm">{vendor?.is_active ? 'Active' : 'Inactive'}</Badge>
            <div className="ml-auto flex gap-2">
              <Button variant="ghost" onClick={onClose}>Close</Button>
              {canManage && vendor && (
                <Button variant="primary" icon={<Pencil className="h-3.5 w-3.5" />} onClick={() => startEdit(vendor)}>Edit</Button>
              )}
            </div>
          </div>
        )
      }
    >
      {!vendor ? (
        <p className="py-10 text-center text-[14px] text-ink-500">Loading…</p>
      ) : editing && form ? (
        <div className="space-y-4">
          <p className="text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-400">Basic</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Vendor name" value={form.name ?? ''} onChange={(e) => set({ name: e.target.value })} />
            <Input label="City" value={form.city ?? ''} onChange={(e) => set({ city: e.target.value })} />
            <Select label="Payment type" value={form.payment_type} onChange={(e) => set({ payment_type: e.target.value as VendorOut['payment_type'] })}>
              {['credit', 'cash', 'card', 'cheque', 'rtgs', 'transaction'].map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
            <Input label="Credit period (days)" type="number" value={String(form.credit_period_days ?? 0)} onChange={(e) => set({ credit_period_days: Number(e.target.value) || 0 })} />
            <Input label="GST number" value={form.gst_number ?? ''} onChange={(e) => set({ gst_number: e.target.value })} />
            <Input label="Contact phone" value={form.contact_phone ?? ''} onChange={(e) => set({ contact_phone: e.target.value })} />
          </div>

          <p className="pt-2 text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-400">Bank</p>
          <div className="grid gap-3 sm:grid-cols-3">
            <Input label="Account number" value={form.bank_account_number ?? ''} onChange={(e) => set({ bank_account_number: e.target.value })} />
            <Input label="Bank name" value={form.bank_name ?? ''} onChange={(e) => set({ bank_name: e.target.value })} />
            <Input label="IFSC" value={form.ifsc_code ?? ''} onChange={(e) => set({ ifsc_code: e.target.value })} />
          </div>

          <Switch label="Active" checked={form.is_active !== false} onChange={(v) => set({ is_active: v })} />
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="City" value={vendor.city ?? '—'} />
          <Field label="GST number" value={vendor.gst_number ?? '—'} />
          <Field label="Payment type" value={vendor.payment_type} />
          <Field label="Credit period" value={`${vendor.credit_period_days} days`} />
          <Field label="Bank" value={vendor.bank_name ?? '—'} />
          <Field label="Account number" value={vendor.bank_account_number ?? '—'} />
          <Field label="IFSC" value={vendor.ifsc_code ?? '—'} />
          <Field label="Contact phone" value={vendor.contact_phone ?? '—'} />
        </div>
      )}
    </Modal>
  );
}

// =========================================================================
// Purchase Returns — return received stock back to a vendor. Only
// completed (received) purchases are returnable; reuses the existing
// PharmacyPurchaseLine/MedicineBatch data, no parallel purchase system.
// =========================================================================

function PurchaseReturnsTab({
  purchases, vendorNameById, medicineNameById, canReturn,
}: {
  purchases: { id: string; purchase_number: string; vendor_id: string; status: string }[];
  vendorNameById: Record<string, string>;
  medicineNameById: Record<string, string>;
  canReturn: boolean;
}) {
  const [selectedPurchaseId, setSelectedPurchaseId] = useState<string | null>(null);
  const returnsQuery = usePurchaseReturns();
  const completedPurchases = purchases.filter((p) => p.status === 'completed');

  return (
    <div className="animate-fade-up space-y-5 p-5">
      {selectedPurchaseId && (
        <PurchaseReturnModal
          purchaseId={selectedPurchaseId} purchaseNumber={completedPurchases.find((p) => p.id === selectedPurchaseId)?.purchase_number ?? ''}
          medicineNameById={medicineNameById} onClose={() => setSelectedPurchaseId(null)}
        />
      )}

      <div>
        <p className="mb-2 text-[13px] font-semibold text-ink-700">Received purchases eligible for return</p>
        {completedPurchases.length === 0 ? (
          <InfoNote>No completed purchases yet — a purchase becomes returnable once it has been received (GRN).</InfoNote>
        ) : (
          <div className="stagger space-y-2">
            {completedPurchases.map((p) => (
              <Card key={p.id} className="flex items-center justify-between p-3.5" interactive onClick={canReturn ? () => setSelectedPurchaseId(p.id) : undefined}>
                <p className="text-[13.5px] font-medium text-ink-900">{p.purchase_number} <span className="tnum font-normal text-ink-400">· {vendorNameById[p.vendor_id] ?? 'Vendor'}</span></p>
                {canReturn && <Button size="sm" variant="secondary">Return</Button>}
              </Card>
            ))}
          </div>
        )}
      </div>

      <div>
        <p className="mb-2 text-[13px] font-semibold text-ink-700">Return history</p>
        {(returnsQuery.data ?? []).length === 0 ? (
          <InfoNote>No purchase returns recorded yet.</InfoNote>
        ) : (
          <div className="space-y-2">
            {(returnsQuery.data ?? []).map((r) => (
              <Card key={r.id} className="p-3.5">
                <p className="text-[13.5px] font-medium text-ink-900">{r.return_number} <span className="tnum font-normal text-ink-400">· {vendorNameById[r.vendor_id] ?? 'Vendor'} · {r.return_date}</span></p>
                <p className="text-[12px] text-ink-500">
                  {r.items.map((i) => `${medicineNameById[i.medicine_id] ?? 'Medicine'} × ${i.quantity}`).join(', ')}
                  {r.reason ? ` — ${r.reason}` : ''}
                </p>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PurchaseReturnModal({
  purchaseId, purchaseNumber, medicineNameById, onClose,
}: { purchaseId: string; purchaseNumber: string; medicineNameById: Record<string, string>; onClose: () => void }) {
  const { toast } = useApp();
  const returnableQuery = useReturnableLines(purchaseId);
  const createReturn = useCreatePurchaseReturn();
  const [qty, setQty] = useState<Record<string, number>>({});
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const lines = returnableQuery.data ?? [];

  return (
    <Modal
      open onClose={onClose} title={`Return — ${purchaseNumber}`}
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button
              variant="primary" loading={createReturn.isPending}
              disabled={Object.values(qty).every((q) => !q)}
              onClick={() => {
                setError(null);
                const reqLines = Object.entries(qty).filter(([, q]) => q > 0).map(([purchase_line_id, quantity]) => ({ purchase_line_id, quantity }));
                if (reqLines.length === 0) { setError('Enter a return quantity for at least one line.'); return; }
                createReturn.mutate(
                  { purchaseId, reason: reason.trim() || null, lines: reqLines },
                  { onSuccess: () => { onClose(); toast({ title: 'Purchase return recorded', tone: 'success' }); }, onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not process the return.') }
                );
              }}
            >
              Confirm Return
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        {returnableQuery.isLoading ? (
          <p className="py-8 text-center text-[14px] text-ink-500">Loading…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-[13px]">
              <thead>
                <tr className="border-b border-ink-200/70 text-[11.5px] font-semibold uppercase tracking-[0.08em] text-ink-400">
                  <th className="py-2 pr-3">Medicine</th><th className="py-2 pr-3">Purchased</th><th className="py-2 pr-3">Returned</th><th className="py-2 pr-3">Returnable</th><th className="py-2 pr-3">Return Qty</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((l) => (
                  <tr key={l.purchase_line_id} className="border-b border-ink-100 last:border-0">
                    <td className="py-2.5 pr-3 font-medium text-ink-900">{medicineNameById[l.medicine_id] ?? 'Medicine'} <span className="tnum text-ink-400">({l.batch_number})</span></td>
                    <td className="tnum py-2.5 pr-3">{l.purchased_quantity}</td>
                    <td className="tnum py-2.5 pr-3">{l.already_returned}</td>
                    <td className="tnum py-2.5 pr-3 text-ink-500">{l.returnable}</td>
                    <td className="py-2 pr-3">
                      {l.returnable > 0 ? (
                        <Input type="number" min={0} max={l.returnable} className="w-20" value={qty[l.purchase_line_id] ? String(qty[l.purchase_line_id]) : ''}
                          onChange={(e) => setQty((prev) => ({ ...prev, [l.purchase_line_id]: Math.min(Number(e.target.value) || 0, l.returnable) }))} />
                      ) : <span className="text-[12px] text-ink-400">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Reason (optional)</span>
          <textarea className="min-h-[60px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900" value={reason} onChange={(e) => setReason(e.target.value)} />
        </label>
      </div>
    </Modal>
  );
}

// =========================================================================
// Sales Returns — search a bill, pick lines, process the return.
// Reuses POST /pharmacy/sales/{id}/return; never a second stock path.
// =========================================================================

function SalesReturnTab({
  sales, medicineNameById, patientNameById,
}: {
  sales: SaleOut[];
  medicineNameById: Record<string, string>;
  patientNameById: Record<string, string>;
}) {
  const { toast } = useApp();
  const createReturn = useCreateSaleReturn();
  const [search, setSearch] = useState('');
  const [selectedSaleId, setSelectedSaleId] = useState<string | null>(null);
  const [returnQty, setReturnQty] = useState<Record<string, number>>({});
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const results = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return [];
    return sales.filter(
      (s) => s.bill_number.toLowerCase().includes(term) || (patientNameById[s.patient_id] ?? '').toLowerCase().includes(term)
    );
  }, [sales, search, patientNameById]);

  const selectedSale = sales.find((s) => s.id === selectedSaleId) ?? null;

  const openSale = (id: string) => { setSelectedSaleId(id); setReturnQty({}); setReason(''); setError(null); createReturn.reset(); };

  return (
    <div className="animate-fade-up space-y-4 p-5">
      <Input placeholder="Search by bill number or patient name…" icon={<Search className="h-3.5 w-3.5" />} value={search} onChange={(e) => { setSearch(e.target.value); setSelectedSaleId(null); }} />

      {!selectedSale ? (
        search.trim() === '' ? (
          <InfoNote>Search for a bill to process a return.</InfoNote>
        ) : results.length === 0 ? (
          <InfoNote>No matching bills.</InfoNote>
        ) : (
          <div className="stagger space-y-2">
            {results.map((s) => (
              <Card key={s.id} className="cursor-pointer p-3.5 hover:border-brand-300/70" interactive onClick={() => openSale(s.id)}>
                <div className="flex items-center justify-between">
                  <p className="text-[14px] font-semibold text-ink-900">{s.bill_number} <span className="tnum font-normal text-ink-400">· {patientNameById[s.patient_id] ?? 'Unknown'}</span></p>
                  <span className="tnum text-[13px] font-semibold text-ink-900">{formatINR(Math.round(s.total_amount_paise / 100))}</span>
                </div>
                <p className="text-[12px] text-ink-500">{s.lines.length} line{s.lines.length === 1 ? '' : 's'} · <Badge tone={s.status === 'dispensed' ? 'completed' : 'attention'} size="sm">{s.status.replace('_', ' ')}</Badge></p>
              </Card>
            ))}
          </div>
        )
      ) : (
        <Card className="space-y-4 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[14px] font-semibold text-ink-900">{selectedSale.bill_number}</p>
              <p className="text-[12px] text-ink-500">{patientNameById[selectedSale.patient_id] ?? 'Unknown patient'}</p>
            </div>
            <Button size="sm" variant="ghost" onClick={() => setSelectedSaleId(null)}>Back to search</Button>
          </div>

          <div className="space-y-2">
            {selectedSale.lines.map((line) => (
              <div key={line.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-ink-100 p-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-medium text-ink-900">{medicineNameById[line.medicine_id] ?? 'Medicine'}</p>
                  <p className="tnum text-[12px] text-ink-500">Sold: {line.quantity} · ₹{(line.unit_price_paise / 100).toFixed(2)} each</p>
                </div>
                <Input
                  type="number" min={0} max={line.quantity} placeholder="Qty"
                  value={returnQty[line.id] ? String(returnQty[line.id]) : ''}
                  onChange={(e) => setReturnQty((prev) => ({ ...prev, [line.id]: Math.min(Number(e.target.value) || 0, line.quantity) }))}
                  className="w-24"
                />
              </div>
            ))}
          </div>

          <label className="block">
            <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Reason (optional)</span>
            <textarea className="min-h-[60px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900" value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>

          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="flex justify-end">
            <Button
              variant="primary"
              disabled={Object.values(returnQty).every((q) => !q) || createReturn.isPending}
              loading={createReturn.isPending}
              onClick={() => {
                setError(null);
                const lines = Object.entries(returnQty).filter(([, q]) => q > 0).map(([sale_line_id, quantity]) => ({ sale_line_id, quantity }));
                if (lines.length === 0) { setError('Enter a return quantity for at least one line.'); return; }
                createReturn.mutate(
                  { saleId: selectedSale.id, reason: reason.trim() || null, lines },
                  {
                    onSuccess: (r) => {
                      toast({ title: 'Return processed', body: `Refunded ${formatINR(Math.round(r.total_refund_paise / 100))}`, tone: 'success' });
                      setSelectedSaleId(null);
                    },
                    onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not process the return.'),
                  }
                );
              }}
            >
              Process Return
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

// =========================================================================
// Indents — department/room request -> pharmacist delivery -> optional
// return. Reuses POST /pharmacy/indents/{id}/deliver|/return; delivery is
// FEFO-allocated server-side, same as dispensing — no second stock engine.
// =========================================================================

const INDENT_STATUS_LABEL: Record<IndentStatus, string> = {
  PENDING: 'Pending', PARTIALLY_DELIVERED: 'Partially Delivered', DELIVERED: 'Delivered',
  CANCELLED: 'Cancelled', RETURNED: 'Returned',
};
const INDENT_STATUS_TONE: Record<IndentStatus, 'completed' | 'attention' | 'critical' | 'neutral'> = {
  PENDING: 'attention', PARTIALLY_DELIVERED: 'attention', DELIVERED: 'completed', CANCELLED: 'neutral', RETURNED: 'neutral',
};

function IndentsTab({
  indents, isLoading, medicineNameById, canRequest, canDeliver, onAddIndent, onOpenIndent,
}: {
  indents: IndentOut[];
  isLoading: boolean;
  medicineNameById: Record<string, string>;
  canRequest: boolean;
  canDeliver: boolean;
  onAddIndent: () => void;
  onOpenIndent: (id: string) => void;
}) {
  const [statusFilter, setStatusFilter] = useState<'' | IndentStatus>('');
  const [departmentFilter, setDepartmentFilter] = useState('');

  const filtered = useMemo(() => {
    return indents.filter((i) => {
      if (statusFilter && i.status !== statusFilter) return false;
      if (departmentFilter.trim() && !i.department.toLowerCase().includes(departmentFilter.trim().toLowerCase())) return false;
      return true;
    });
  }, [indents, statusFilter, departmentFilter]);

  return (
    <div className="animate-fade-up space-y-4 p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-56">
            <Input label="Department" placeholder="OT, Ward 2…" value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)} />
          </div>
          <div className="w-48">
            <Select label="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as '' | IndentStatus)}>
              <option value="">All statuses</option>
              {(Object.keys(INDENT_STATUS_LABEL) as IndentStatus[]).map((s) => <option key={s} value={s}>{INDENT_STATUS_LABEL[s]}</option>)}
            </Select>
          </div>
        </div>
        {canRequest && (
          <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={onAddIndent}>
            New Indent
          </Button>
        )}
      </div>

      {isLoading ? (
        <p className="py-10 text-center text-[14px] text-ink-500">Loading indents…</p>
      ) : filtered.length === 0 ? (
        <InfoNote>No indents match. {canRequest && 'Use "New Indent" to raise a department request.'}</InfoNote>
      ) : (
        <div className="stagger space-y-2.5">
          {filtered.map((indent) => {
            const totalRequested = indent.items.reduce((s, i) => s + i.requested_quantity, 0);
            const totalDelivered = indent.items.reduce((s, i) => s + i.delivered_quantity, 0);
            return (
              <Card key={indent.id} className="p-4" interactive onClick={() => onOpenIndent(indent.id)}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-[14px] font-semibold text-ink-900">{indent.indent_number} <span className="tnum font-normal text-ink-400">· {indent.department}{indent.room ? ` / ${indent.room}` : ''}</span></p>
                    <p className="text-[12px] text-ink-500">{indent.items.length} medicine{indent.items.length === 1 ? '' : 's'} · {totalDelivered}/{totalRequested} delivered</p>
                  </div>
                  <Badge tone={INDENT_STATUS_TONE[indent.status]} size="sm">{INDENT_STATUS_LABEL[indent.status]}</Badge>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function NewIndentModal({ open, onClose, medicines }: { open: boolean; onClose: () => void; medicines: MedicineOut[] }) {
  const { toast } = useApp();
  const createIndent = useCreateIndent();
  const [department, setDepartment] = useState('');
  const [room, setRoom] = useState('');
  const [notes, setNotes] = useState('');
  const [lines, setLines] = useState<{ key: number; medicine_id: string; requested_quantity: number }[]>([{ key: 0, medicine_id: '', requested_quantity: 1 }]);
  const nextKey = useRef(1);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setDepartment(''); setRoom(''); setNotes(''); setLines([{ key: 0, medicine_id: '', requested_quantity: 1 }]); setError(null); createIndent.reset();
  };
  const close = () => { reset(); onClose(); };
  const addLine = () => setLines((l) => [...l, { key: nextKey.current++, medicine_id: '', requested_quantity: 1 }]);
  const updateLine = (key: number, patch: Partial<{ medicine_id: string; requested_quantity: number }>) =>
    setLines((l) => l.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  const removeLine = (key: number) => setLines((l) => (l.length > 1 ? l.filter((row) => row.key !== key) : l));

  return (
    <Modal
      open={open} onClose={close} title="New Indent" subtitle="Raise a department/room request to the pharmacy."
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button
              variant="primary" disabled={!department.trim() || createIndent.isPending} loading={createIndent.isPending}
              onClick={() => {
                setError(null);
                const validLines = lines.filter((l) => l.medicine_id && l.requested_quantity > 0);
                if (validLines.length === 0) { setError('Add at least one medicine.'); return; }
                createIndent.mutate(
                  {
                    department: department.trim(), room: room.trim() || null, request_date: new Date().toISOString().slice(0, 10),
                    notes: notes.trim() || null,
                    items: validLines.map((l) => ({ medicine_id: l.medicine_id, requested_quantity: l.requested_quantity })),
                  },
                  {
                    onSuccess: (indent) => { close(); toast({ title: `Indent ${indent.indent_number} raised`, tone: 'success' }); },
                    onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not raise the indent.'),
                  }
                );
              }}
            >
              Raise Indent
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Department" placeholder="OT, Ward 2, ICU…" value={department} onChange={(e) => setDepartment(e.target.value)} />
          <Input label="Room (optional)" value={room} onChange={(e) => setRoom(e.target.value)} />
        </div>
        <div className="space-y-2.5">
          {lines.map((line) => (
            <Card key={line.key} className="p-3">
              <div className="grid gap-2.5 sm:grid-cols-[2fr_1fr]">
                <Select label="Medicine" value={line.medicine_id} onChange={(e) => updateLine(line.key, { medicine_id: e.target.value })}>
                  <option value="">Select…</option>
                  {medicines.map((m) => <option key={m.id} value={m.id}>{m.brand_name ?? m.generic_name}</option>)}
                </Select>
                <Input label="Requested qty" type="number" min={1} value={String(line.requested_quantity)} onChange={(e) => updateLine(line.key, { requested_quantity: Number(e.target.value) || 0 })} />
              </div>
              <button onClick={() => removeLine(line.key)} className="mt-2 text-[12px] font-medium text-rose-600 hover:text-rose-700">Remove line</button>
            </Card>
          ))}
          <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={addLine}>Add medicine</Button>
        </div>
        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Notes (optional)</span>
          <textarea className="min-h-[60px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
      </div>
    </Modal>
  );
}

function IndentDetailModal({
  indentId, medicineNameById, canDeliver, onClose,
}: {
  indentId: string;
  medicineNameById: Record<string, string>;
  canDeliver: boolean;
  onClose: () => void;
}) {
  const { toast } = useApp();
  const indentQuery = useIndent(indentId);
  const indent = indentQuery.data;
  const medicineIds = useMemo(() => (indent?.items ?? []).map((i) => i.medicine_id), [indent]);
  const stockQuery = useIndentAvailableStock(medicineIds);
  const deliver = useDeliverIndent();
  const doReturn = useReturnIndent();
  const [mode, setMode] = useState<'deliver' | 'return' | null>(null);
  const [qty, setQty] = useState<Record<string, number>>({});
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const availableByMedicine = useMemo(() => {
    const map: Record<string, number> = {};
    for (const row of stockQuery.data ?? []) map[row.medicine_id] = row.available;
    return map;
  }, [stockQuery.data]);

  const openMode = (m: 'deliver' | 'return') => { setMode(m); setQty({}); setReason(''); setError(null); deliver.reset(); doReturn.reset(); };

  return (
    <Modal
      open onClose={onClose} title={indent?.indent_number ?? 'Indent'} subtitle={indent ? `${indent.department}${indent.room ? ` / ${indent.room}` : ''}` : undefined}
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            {mode ? (
              <>
                <Button variant="ghost" onClick={() => setMode(null)}>Cancel</Button>
                <Button
                  variant="primary" loading={mode === 'deliver' ? deliver.isPending : doReturn.isPending}
                  disabled={Object.values(qty).every((q) => !q)}
                  onClick={() => {
                    setError(null);
                    const lines = Object.entries(qty).filter(([, q]) => q > 0).map(([indent_item_id, quantity]) => ({ indent_item_id, quantity }));
                    if (lines.length === 0) { setError('Enter a quantity for at least one line.'); return; }
                    if (mode === 'deliver') {
                      deliver.mutate(
                        { indentId, lines },
                        { onSuccess: () => { setMode(null); toast({ title: 'Delivery confirmed', tone: 'success' }); }, onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not confirm delivery.') }
                      );
                    } else {
                      doReturn.mutate(
                        { indentId, reason: reason.trim() || null, lines },
                        { onSuccess: () => { setMode(null); toast({ title: 'Return processed', tone: 'success' }); }, onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not process the return.') }
                      );
                    }
                  }}
                >
                  {mode === 'deliver' ? 'Confirm Delivery' : 'Process Return'}
                </Button>
              </>
            ) : (
              <>
                <Button variant="ghost" onClick={onClose}>Close</Button>
                {canDeliver && indent && indent.status !== 'CANCELLED' && indent.status !== 'DELIVERED' && indent.status !== 'RETURNED' && (
                  <Button variant="primary" icon={<Truck className="h-3.5 w-3.5" />} onClick={() => openMode('deliver')}>Deliver</Button>
                )}
                {canDeliver && indent && indent.items.some((i) => i.delivered_quantity > i.returned_quantity) && (
                  <Button variant="secondary" icon={<RotateCcw className="h-3.5 w-3.5" />} onClick={() => openMode('return')}>Return</Button>
                )}
              </>
            )}
          </div>
        </div>
      }
    >
      {!indent ? (
        <p className="py-10 text-center text-[14px] text-ink-500">Loading…</p>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Badge tone={INDENT_STATUS_TONE[indent.status]} size="sm">{INDENT_STATUS_LABEL[indent.status]}</Badge>
            <p className="tnum text-[12px] text-ink-500">Requested {indent.request_date}</p>
          </div>
          {indent.notes && <p className="text-[13px] text-ink-600">{indent.notes}</p>}

          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[13px]">
              <thead>
                <tr className="border-b border-ink-200/70 text-[11.5px] font-semibold uppercase tracking-[0.08em] text-ink-400">
                  <th className="py-2 pr-3">Medicine</th>
                  <th className="py-2 pr-3">Requested</th>
                  <th className="py-2 pr-3">Available</th>
                  <th className="py-2 pr-3">Delivered</th>
                  <th className="py-2 pr-3">Remaining</th>
                  {mode && <th className="py-2 pr-3">{mode === 'deliver' ? 'Deliver Qty' : 'Return Qty'}</th>}
                </tr>
              </thead>
              <tbody>
                {indent.items.map((item) => {
                  const remaining = item.requested_quantity - item.delivered_quantity;
                  const returnable = item.delivered_quantity - item.returned_quantity;
                  const max = mode === 'deliver' ? Math.min(remaining, availableByMedicine[item.medicine_id] ?? 0) : returnable;
                  return (
                    <tr key={item.id} className="border-b border-ink-100 last:border-0">
                      <td className="py-2.5 pr-3 font-medium text-ink-900">{medicineNameById[item.medicine_id] ?? 'Medicine'}</td>
                      <td className="tnum py-2.5 pr-3 text-ink-700">{item.requested_quantity}</td>
                      <td className="tnum py-2.5 pr-3 text-ink-600">{availableByMedicine[item.medicine_id] ?? '—'}</td>
                      <td className="tnum py-2.5 pr-3 text-ink-700">{item.delivered_quantity}</td>
                      <td className="tnum py-2.5 pr-3 text-ink-500">{remaining}</td>
                      {mode && (
                        <td className="py-2.5 pr-3">
                          {max > 0 ? (
                            <Input
                              type="number" min={0} max={max} className="w-20" value={qty[item.id] ? String(qty[item.id]) : ''}
                              onChange={(e) => setQty((prev) => ({ ...prev, [item.id]: Math.min(Number(e.target.value) || 0, max) }))}
                            />
                          ) : (
                            <span className="text-[12px] text-ink-400">—</span>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {mode === 'deliver' && indent.items.some((i) => (availableByMedicine[i.medicine_id] ?? 0) < (i.requested_quantity - i.delivered_quantity)) && (
            <InfoNote tone="amber">Some lines have less stock available than requested — deliver what's available now; the remainder stays open for a later delivery.</InfoNote>
          )}
          {mode === 'return' && (
            <label className="block">
              <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Reason (optional)</span>
              <textarea className="min-h-[60px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900" value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
          )}
        </div>
      )}
    </Modal>
  );
}
