'use client';

import React, { useState } from 'react';
import { Card, Button, Badge, Select, Modal, InfoNote } from '@/components/ui/primitives';
import { Calculator, Download, AlertTriangle } from 'lucide-react';
import {
  useEmployees, usePayrollList, useCalculatePayroll, useApprovePayroll, useMarkPayrollPaid,
  useHrSettings, downloadHrReport, type PayrollOut, type PayrollStatus,
} from '@/lib/api/hr';
import { useApp } from '@/lib/store';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

const STATUS_TONE: Record<PayrollStatus, 'active' | 'scheduled' | 'pending' | 'neutral'> = {
  paid: 'active',
  approved: 'scheduled',
  calculated: 'pending',
  draft: 'neutral',
};

function CalculateModal({ onClose }: { onClose: () => void }) {
  const { toast } = useApp();
  const { data: employees } = useEmployees({ employment_status: 'active' });
  const calc = useCalculatePayroll();
  const now = new Date();
  const [employeeId, setEmployeeId] = useState('');
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());

  const submit = () => {
    if (!employeeId) return;
    calc.mutate({ employee_id: employeeId, month, year }, {
      onSuccess: () => { toast({ title: 'Payroll calculated', tone: 'success' }); onClose(); },
      onError: (e: any) => toast({ title: 'Could not calculate payroll', body: e?.message, tone: 'error' }),
    });
  };

  return (
    <Modal open onClose={onClose} title="Calculate Payroll" footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button variant="primary" loading={calc.isPending} onClick={submit}>Calculate</Button></>}>
      <div className="space-y-4">
        <Select label="Employee" value={employeeId} onChange={(e) => setEmployeeId(e.target.value)}>
          <option value="">Select an employee…</option>
          {(employees ?? []).map((e) => <option key={e.id} value={e.id}>{e.full_name} — {e.department}</option>)}
        </Select>
        <div className="grid grid-cols-2 gap-3">
          <Select label="Month" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </Select>
          <Select label="Year" value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {[year - 1, year, year + 1].map((y) => <option key={y} value={y}>{y}</option>)}
          </Select>
        </div>
      </div>
    </Modal>
  );
}

function BreakdownModal({ payroll, employeeName, onClose }: { payroll: PayrollOut; employeeName: string; onClose: () => void }) {
  const approve = useApprovePayroll();
  const markPaid = useMarkPayrollPaid();
  const { data: settings } = useHrSettings();
  const { toast } = useApp();

  const perDay = Number(payroll.per_day_rupees);
  const halfFraction = settings ? Number(settings.half_day_pay_fraction) : 0.5;
  const absentFraction = settings ? Number(settings.absent_day_pay_fraction) : 0;
  const presentAmount = payroll.present_days * perDay;
  const halfDayAmount = payroll.half_days * perDay * halfFraction;
  const absentAmount = payroll.absent_days * perDay * absentFraction;

  return (
    <Modal open onClose={onClose} title={`${employeeName} — ${MONTHS[payroll.month - 1]} ${payroll.year}`} subtitle="Salary breakdown">
      {payroll.status === 'draft' && (
        <InfoNote tone="amber" icon={<AlertTriangle className="h-4 w-4" />}>
          Attendance period is not finalized. Payroll is currently <strong>DRAFT</strong> and cannot be approved until the month's
          attendance is finalized on the Monthly Attendance tab.
        </InfoNote>
      )}
      <div className="mt-3 space-y-1 rounded-xl bg-ink-50 p-4 text-[13.5px]">
        <div className="flex justify-between py-1"><span className="text-ink-500">Monthly Salary</span><span className="tnum font-medium">₹{payroll.base_salary_rupees.toLocaleString('en-IN')}</span></div>
        <div className="flex justify-between py-1"><span className="text-ink-500">Working Days</span><span className="tnum">{payroll.working_days}</span></div>
        <div className="flex justify-between py-1"><span className="text-ink-500">Daily Salary</span><span className="tnum">₹{perDay.toFixed(2)}</span></div>
        <div className="my-2 border-t border-ink-200" />
        <div className="flex justify-between py-1"><span className="text-ink-500">Present ({payroll.present_days} × ₹{perDay.toFixed(2)})</span><span className="tnum">₹{presentAmount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span></div>
        <div className="flex justify-between py-1"><span className="text-ink-500">Half Day ({payroll.half_days} × ₹{perDay.toFixed(2)} × {halfFraction})</span><span className="tnum">₹{halfDayAmount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span></div>
        <div className="flex justify-between py-1"><span className="text-ink-500">Absent ({payroll.absent_days} × ₹{perDay.toFixed(2)} × {absentFraction})</span><span className="tnum">₹{absentAmount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span></div>
        <div className="flex justify-between py-1"><span className="text-ink-500">Payable Days</span><span className="tnum">{payroll.payable_days}</span></div>
        <div className="my-2 border-t border-ink-200" />
        <div className="flex justify-between py-1 text-rose-600"><span>Attendance Deduction</span><span className="tnum font-medium">− ₹{payroll.deduction_rupees.toLocaleString('en-IN')}</span></div>
        <div className="flex justify-between py-1 text-emerald-700"><span>Overtime ({payroll.overtime_hours}h)</span><span className="tnum font-medium">+ ₹{payroll.overtime_amount_rupees.toLocaleString('en-IN')}</span></div>
        <div className="my-2 border-t border-ink-200" />
        <div className="flex justify-between py-1 text-[16px] font-semibold text-ink-900"><span>Net Salary</span><span className="tnum">₹{payroll.net_salary_rupees.toLocaleString('en-IN')}</span></div>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Badge tone={STATUS_TONE[payroll.status]}>{payroll.status}</Badge>
        <div className="flex gap-2">
          {payroll.status === 'calculated' && (
            <Button
              variant="primary" size="sm" loading={approve.isPending}
              onClick={() => approve.mutate(payroll.id, {
                onSuccess: () => { toast({ title: 'Payroll approved', tone: 'success' }); onClose(); },
                onError: (e: any) => toast({ title: 'Could not approve payroll', body: e?.message, tone: 'error' }),
              })}
            >
              Approve
            </Button>
          )}
          {payroll.status === 'approved' && (
            <Button
              variant="dark" size="sm" loading={markPaid.isPending}
              onClick={() => markPaid.mutate(payroll.id, {
                onSuccess: () => { toast({ title: 'Marked as paid', tone: 'success' }); onClose(); },
                onError: (e: any) => toast({ title: 'Could not mark payroll as paid', body: e?.message, tone: 'error' }),
              })}
            >
              Mark as Paid
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}

export function HrPayroll() {
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const { data: employees } = useEmployees();
  const { data, isLoading } = usePayrollList({ month, year });
  const [calcOpen, setCalcOpen] = useState(false);
  const [selected, setSelected] = useState<PayrollOut | null>(null);
  const nameOf = (id: string) => employees?.find((e) => e.id === id)?.full_name ?? id;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="tracking-display text-[20px] font-semibold text-ink-900">Salary / Payroll Management</h1>
          <p className="mt-1 text-[13px] text-ink-500">Calculated from attendance — nothing is ever auto-marked as paid.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" icon={<Download className="h-4 w-4" />} onClick={() => downloadHrReport(`/hr/reports/payroll.csv?month=${month}&year=${year}`, `payroll_${month}_${year}.csv`)}>Export</Button>
          <Button variant="primary" icon={<Calculator className="h-4 w-4" />} onClick={() => setCalcOpen(true)}>Calculate Payroll</Button>
        </div>
      </div>

      <div className="flex gap-3">
        <Select value={month} onChange={(e) => setMonth(Number(e.target.value))} className="max-w-[160px]">
          {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
        </Select>
        <Select value={year} onChange={(e) => setYear(Number(e.target.value))} className="max-w-[120px]">
          {[year - 1, year, year + 1].map((y) => <option key={y} value={y}>{y}</option>)}
        </Select>
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-[13.5px]">
          <thead className="bg-ink-50 text-left text-[12px] font-semibold uppercase tracking-wide text-ink-500">
            <tr>
              <th className="px-4 py-2.5">Employee</th>
              <th className="px-4 py-2.5">Base</th>
              <th className="px-4 py-2.5">Present</th>
              <th className="px-4 py-2.5">Half Day</th>
              <th className="px-4 py-2.5">Absent</th>
              <th className="px-4 py-2.5">Deduction</th>
              <th className="px-4 py-2.5">Overtime</th>
              <th className="px-4 py-2.5">Net Salary</th>
              <th className="px-4 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={9} className="px-4 py-6 text-center text-ink-400">Loading…</td></tr>}
            {!isLoading && !data?.length && <tr><td colSpan={9} className="px-4 py-6 text-center text-ink-400">No payroll calculated for this month yet.</td></tr>}
            {(data ?? []).map((p) => (
              <tr key={p.id} className="cursor-pointer border-t border-ink-100 hover:bg-ink-50/60" onClick={() => setSelected(p)}>
                <td className="px-4 py-2 font-medium text-ink-900">{nameOf(p.employee_id)}</td>
                <td className="px-4 py-2 tnum text-ink-600">₹{p.base_salary_rupees.toLocaleString('en-IN')}</td>
                <td className="px-4 py-2 tnum text-ink-600">{p.present_days}</td>
                <td className="px-4 py-2 tnum text-ink-600">{p.half_days}</td>
                <td className="px-4 py-2 tnum text-ink-600">{p.absent_days}</td>
                <td className="px-4 py-2 tnum text-rose-600">₹{p.deduction_rupees.toLocaleString('en-IN')}</td>
                <td className="px-4 py-2 tnum text-emerald-700">₹{p.overtime_amount_rupees.toLocaleString('en-IN')}</td>
                <td className="px-4 py-2 tnum font-semibold text-ink-900">₹{p.net_salary_rupees.toLocaleString('en-IN')}</td>
                <td className="px-4 py-2"><Badge size="sm" tone={STATUS_TONE[p.status]}>{p.status}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {calcOpen && <CalculateModal onClose={() => setCalcOpen(false)} />}
      {selected && <BreakdownModal payroll={selected} employeeName={nameOf(selected.employee_id)} onClose={() => setSelected(null)} />}
    </div>
  );
}
