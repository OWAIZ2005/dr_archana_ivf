'use client';

import React, { useState } from 'react';
import { Card, Input, Select } from '@/components/ui/primitives';
import { formatINR } from '@/lib/utils';
import {
  useBillMarginReport, useCollectionReport, useCollectionSummary, useCustomerSalesReport, useDoctorSalesReport,
  useIndentReportData, usePurchaseBookReport, usePurchaseOrderReport, usePurchaseReturnReport, useStockTransactionReport,
  useTopSellingReport, useVendorReport,
} from '@/lib/api/pharmacy';
import { BarChart3 } from 'lucide-react';

type Category = 'collection' | 'gst' | 'indents' | 'vendors' | 'stock' | 'sales' | 'purchases' | 'customers';

const CATEGORIES: { id: Category; label: string }[] = [
  { id: 'collection', label: 'Collection' }, { id: 'sales', label: 'Sales' }, { id: 'purchases', label: 'Purchases' },
  { id: 'vendors', label: 'Vendors' }, { id: 'stock', label: 'Stock' }, { id: 'indents', label: 'Indents' }, { id: 'customers', label: 'Customers' },
];

function Table({ columns, rows, formatters }: { columns: { key: string; label: string; money?: boolean }[]; rows: Record<string, any>[]; formatters?: Record<string, (v: any) => string> }) {
  if (rows.length === 0) return <p className="py-8 text-center text-[13.5px] text-ink-500">No data for this report yet.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-[13px]">
        <thead>
          <tr className="border-b border-ink-200/70 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-400">
            {columns.map((c) => <th key={c.key} className="py-2 pr-3">{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-ink-100 last:border-0">
              {columns.map((c) => {
                const raw = row[c.key];
                const value = formatters?.[c.key] ? formatters[c.key](raw) : c.money ? formatINR(Math.round((raw ?? 0) / 100)) : String(raw ?? '—');
                return <td key={c.key} className="tnum py-2 pr-3 text-ink-700">{value}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DateFilters({ from, to, onFrom, onTo }: { from: string; to: string; onFrom: (v: string) => void; onTo: (v: string) => void }) {
  return (
    <div className="mb-3 flex flex-wrap items-end gap-3">
      <Input label="From" type="date" value={from} onChange={(e) => onFrom(e.target.value)} />
      <Input label="To" type="date" value={to} onChange={(e) => onTo(e.target.value)} />
    </div>
  );
}

export function ReportsTab() {
  const [category, setCategory] = useState<Category>('collection');
  const [report, setReport] = useState('collection-summary');
  const today = new Date().toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const [from, setFrom] = useState(monthAgo);
  const [to, setTo] = useState(today);

  const REPORTS_BY_CATEGORY: Record<Category, { id: string; label: string }[]> = {
    collection: [{ id: 'collection-summary', label: 'Collection Summary' }, { id: 'collection-list', label: 'Pharmacy Collection' }],
    gst: [],
    sales: [{ id: 'top-selling', label: 'Top Selling Medicines' }, { id: 'doctor-sales', label: 'Doctor Wise Sales' }, { id: 'bill-margin', label: 'Bill Wise Margin' }],
    purchases: [{ id: 'purchase-book', label: 'Purchase Book' }, { id: 'purchase-orders', label: 'Purchase Order List' }, { id: 'purchase-returns', label: 'Purchase Return Medicine' }],
    vendors: [{ id: 'vendor-report', label: 'Vendor Report' }],
    stock: [{ id: 'stock-transactions', label: 'Medicine Transaction Report' }],
    indents: [{ id: 'indent-report', label: 'Indent Report' }],
    customers: [{ id: 'customer-sales', label: 'Customer Wise Sales' }],
  };

  const changeCategory = (c: Category) => { setCategory(c); setReport(REPORTS_BY_CATEGORY[c][0]?.id ?? ''); };

  return (
    <div className="animate-fade-up space-y-4 p-5">
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map((c) => (
          <button
            key={c.id} onClick={() => changeCategory(c.id)}
            className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors ${category === c.id ? 'bg-brand-600 text-white' : 'bg-ink-100 text-ink-600 hover:bg-ink-200'}`}
          >
            {c.label}
          </button>
        ))}
      </div>

      {category === 'gst' ? (
        <Card className="p-6 text-center text-[13.5px] text-ink-500">GST Files Report is exposed at <code>GET /pharmacy/reports/gst</code> (purchase + sale tax lines) — not yet wired to a dedicated view in this tab.</Card>
      ) : (
        <div className="w-64">
          <Select label="Report" value={report} onChange={(e) => setReport(e.target.value)}>
            {REPORTS_BY_CATEGORY[category].map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
          </Select>
        </div>
      )}

      <Card className="p-4">
        <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink-700"><BarChart3 className="h-4 w-4 text-brand-600" /> {REPORTS_BY_CATEGORY[category]?.find((r) => r.id === report)?.label}</div>

        {report === 'collection-summary' && <CollectionSummaryReport from={from} to={to} setFrom={setFrom} setTo={setTo} />}
        {report === 'collection-list' && <CollectionListReport from={from} to={to} setFrom={setFrom} setTo={setTo} />}
        {report === 'top-selling' && <TopSellingReport from={from} to={to} setFrom={setFrom} setTo={setTo} />}
        {report === 'doctor-sales' && <DoctorSalesReport from={from} to={to} setFrom={setFrom} setTo={setTo} />}
        {report === 'bill-margin' && <BillMarginReport from={from} to={to} setFrom={setFrom} setTo={setTo} />}
        {report === 'purchase-book' && <PurchaseBookReport from={from} to={to} setFrom={setFrom} setTo={setTo} />}
        {report === 'purchase-orders' && <PurchaseOrderReport />}
        {report === 'purchase-returns' && <PurchaseReturnReport />}
        {report === 'vendor-report' && <VendorReport />}
        {report === 'stock-transactions' && <StockTransactionReport />}
        {report === 'indent-report' && <IndentReport />}
        {report === 'customer-sales' && <CustomerSalesReport />}
      </Card>
    </div>
  );
}

function CollectionSummaryReport({ from, to, setFrom, setTo }: { from: string; to: string; setFrom: (v: string) => void; setTo: (v: string) => void }) {
  const { data } = useCollectionSummary({ from_date: from, to_date: to });
  return (
    <div>
      <DateFilters from={from} to={to} onFrom={setFrom} onTo={setTo} />
      {data && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ['Gross', data.gross_paise], ['Discounts', data.discount_paise], ['Net Collection', data.net_paise], ['Bills', data.bill_count * 100],
            ['Cash', data.cash_paise], ['Card', data.card_paise], ['Cheque', data.cheque_paise], ['Online', data.online_paise],
          ].map(([label, paise]) => (
            <div key={label as string} className="rounded-xl border border-ink-100 p-3">
              <p className="text-[11px] uppercase tracking-wide text-ink-400">{label}</p>
              <p className="tnum text-[16px] font-semibold text-ink-900">{label === 'Bills' ? data.bill_count : formatINR(Math.round((paise as number) / 100))}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CollectionListReport({ from, to, setFrom, setTo }: { from: string; to: string; setFrom: (v: string) => void; setTo: (v: string) => void }) {
  const { data } = useCollectionReport({ from_date: from, to_date: to });
  return (
    <div>
      <DateFilters from={from} to={to} onFrom={setFrom} onTo={setTo} />
      <Table columns={[{ key: 'bill_number', label: 'Bill No.' }, { key: 'patient_name', label: 'Patient' }, { key: 'amount_paise', label: 'Amount', money: true }, { key: 'payment_method', label: 'Payment' }, { key: 'collected_by', label: 'Collected By' }]} rows={data ?? []} />
    </div>
  );
}

function TopSellingReport({ from, to, setFrom, setTo }: { from: string; to: string; setFrom: (v: string) => void; setTo: (v: string) => void }) {
  const { data } = useTopSellingReport({ from_date: from, to_date: to });
  return (
    <div>
      <DateFilters from={from} to={to} onFrom={setFrom} onTo={setTo} />
      <Table columns={[{ key: 'medicine_name', label: 'Medicine' }, { key: 'quantity_sold', label: 'Qty Sold' }, { key: 'revenue_paise', label: 'Revenue', money: true }]} rows={data ?? []} />
    </div>
  );
}

function DoctorSalesReport({ from, to, setFrom, setTo }: { from: string; to: string; setFrom: (v: string) => void; setTo: (v: string) => void }) {
  const { data } = useDoctorSalesReport({ from_date: from, to_date: to });
  return (
    <div>
      <DateFilters from={from} to={to} onFrom={setFrom} onTo={setTo} />
      <Table columns={[{ key: 'doctor_name', label: 'Doctor' }, { key: 'bill_count', label: 'Bills' }, { key: 'total_paise', label: 'Total', money: true }]} rows={data ?? []} />
    </div>
  );
}

function BillMarginReport({ from, to, setFrom, setTo }: { from: string; to: string; setFrom: (v: string) => void; setTo: (v: string) => void }) {
  const { data } = useBillMarginReport({ from_date: from, to_date: to });
  return (
    <div>
      <DateFilters from={from} to={to} onFrom={setFrom} onTo={setTo} />
      <Table columns={[{ key: 'bill_number', label: 'Bill No.' }, { key: 'selling_value_paise', label: 'Selling Value', money: true }, { key: 'purchase_cost_paise', label: 'Purchase Cost', money: true }, { key: 'margin_paise', label: 'Margin', money: true }]} rows={data ?? []} />
    </div>
  );
}

function PurchaseBookReport({ from, to, setFrom, setTo }: { from: string; to: string; setFrom: (v: string) => void; setTo: (v: string) => void }) {
  const { data } = usePurchaseBookReport({ from_date: from, to_date: to });
  return (
    <div>
      <DateFilters from={from} to={to} onFrom={setFrom} onTo={setTo} />
      <Table columns={[{ key: 'invoice_number', label: 'Invoice' }, { key: 'vendor_name', label: 'Vendor' }, { key: 'purchase_date', label: 'Date' }, { key: 'medicine_name', label: 'Medicine' }, { key: 'quantity', label: 'Qty' }, { key: 'tax_paise', label: 'Tax', money: true }, { key: 'total_paise', label: 'Total', money: true }]} rows={data ?? []} />
    </div>
  );
}

function PurchaseOrderReport() {
  const { data } = usePurchaseOrderReport();
  return <Table columns={[{ key: 'po_number', label: 'PO' }, { key: 'vendor_name', label: 'Vendor' }, { key: 'po_date', label: 'Date' }, { key: 'ordered', label: 'Ordered' }, { key: 'received', label: 'Received' }, { key: 'remaining', label: 'Remaining' }, { key: 'status', label: 'Status' }]} rows={data ?? []} />;
}

function PurchaseReturnReport() {
  const { data } = usePurchaseReturnReport();
  return <Table columns={[{ key: 'return_number', label: 'Return' }, { key: 'vendor_name', label: 'Vendor' }, { key: 'medicine_name', label: 'Medicine' }, { key: 'batch_number', label: 'Batch' }, { key: 'quantity', label: 'Qty' }, { key: 'return_date', label: 'Date' }, { key: 'reason', label: 'Reason' }]} rows={data ?? []} />;
}

function VendorReport() {
  const { data } = useVendorReport();
  return <Table columns={[{ key: 'vendor_name', label: 'Vendor' }, { key: 'gst_number', label: 'GST' }, { key: 'purchase_count', label: 'Purchases' }, { key: 'purchase_value_paise', label: 'Value', money: true }]} rows={data ?? []} />;
}

function StockTransactionReport() {
  const { data } = useStockTransactionReport();
  return <Table columns={[{ key: 'occurred_at', label: 'Date' }, { key: 'medicine_name', label: 'Medicine' }, { key: 'batch_number', label: 'Batch' }, { key: 'transaction_type', label: 'Type' }, { key: 'quantity_delta', label: 'Qty Δ' }, { key: 'reference_type', label: 'Reference' }, { key: 'user_name', label: 'User' }]} rows={data ?? []} />;
}

function IndentReport() {
  const { data } = useIndentReportData();
  return <Table columns={[{ key: 'indent_number', label: 'Indent' }, { key: 'department', label: 'Department' }, { key: 'medicine_name', label: 'Medicine' }, { key: 'requested_quantity', label: 'Req' }, { key: 'delivered_quantity', label: 'Del' }, { key: 'returned_quantity', label: 'Ret' }, { key: 'remaining_quantity', label: 'Rem' }, { key: 'status', label: 'Status' }]} rows={data ?? []} />;
}

function CustomerSalesReport() {
  const { data } = useCustomerSalesReport();
  return <Table columns={[{ key: 'patient_name', label: 'Patient' }, { key: 'bill_count', label: 'Bills' }, { key: 'total_sales_paise', label: 'Total Sales', money: true }, { key: 'discount_paise', label: 'Discounts', money: true }]} rows={data ?? []} />;
}
