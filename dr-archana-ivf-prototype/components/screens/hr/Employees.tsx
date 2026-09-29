'use client';

import React, { useMemo, useState } from 'react';
import { Card, Button, Badge, Input, Select, Modal } from '@/components/ui/primitives';
import { Plus, Search, User } from 'lucide-react';
import {
  useEmployees, useCreateEmployee, useUpdateEmployee, useSetEmployeeActive,
  useAttendanceRecords, usePayrollList, type EmployeeOut,
} from '@/lib/api/hr';
import { useApp } from '@/lib/store';

const DEPARTMENTS = [
  'Front Desk', 'Doctors', 'Nursing', 'Prescription', 'Pharmacy', 'Laboratory',
  'Administration', 'HR', 'Accounts', 'Reproductive Medicine', 'Embryology Laboratory',
  'Patient Services', 'Operations & Finance', 'Inventory', 'Other',
];

function EmployeeFormModal({ open, onClose, employee }: { open: boolean; onClose: () => void; employee: EmployeeOut | null }) {
  const { toast } = useApp();
  const create = useCreateEmployee();
  const update = useUpdateEmployee();
  const [form, setForm] = useState(() => ({
    full_name: employee?.full_name ?? '',
    department: employee?.department ?? DEPARTMENTS[0],
    designation: employee?.designation ?? '',
    phone: employee?.phone ?? '',
    email: employee?.email ?? '',
    joined_date: employee?.joined_date ?? new Date().toISOString().slice(0, 10),
    monthly_salary_rupees: employee?.monthly_salary_rupees?.toString() ?? '',
    working_hours_per_day: employee?.working_hours_per_day?.toString() ?? '8',
    biometric_id: employee?.biometric_id ?? '',
  }));
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    if (!form.full_name.trim() || !form.designation.trim()) { setError('Name and designation are required.'); return; }
    const payload = {
      full_name: form.full_name.trim(),
      department: form.department,
      designation: form.designation.trim(),
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      joined_date: form.joined_date,
      monthly_salary_rupees: form.monthly_salary_rupees ? Number(form.monthly_salary_rupees) : null,
      working_hours_per_day: Number(form.working_hours_per_day) || 8,
      biometric_id: form.biometric_id.trim() || null,
    };
    const onSuccess = () => { toast({ title: employee ? 'Employee updated' : 'Employee added', tone: 'success' }); onClose(); };
    const onError = (e: any) => setError(e?.message ?? 'Something went wrong.');
    if (employee) update.mutate({ id: employee.id, data: payload }, { onSuccess, onError });
    else create.mutate(payload, { onSuccess, onError });
  };

  return (
    <Modal open={open} onClose={onClose} title={employee ? 'Edit Employee' : 'Add Employee'} width="max-w-2xl"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button variant="primary" loading={create.isPending || update.isPending} onClick={submit}>Save</Button></>}
    >
      <div className="grid grid-cols-2 gap-4">
        <Input label="Full name*" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <Input label="Designation*" value={form.designation} onChange={(e) => setForm({ ...form, designation: e.target.value })} />
        <Select label="Department" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>
          {DEPARTMENTS.map((d) => <option key={d} value={d}>{d}</option>)}
        </Select>
        <Input label="Joining date" type="date" value={form.joined_date} onChange={(e) => setForm({ ...form, joined_date: e.target.value })} />
        <Input label="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        <Input label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Input label="Monthly salary (₹)" type="number" value={form.monthly_salary_rupees} onChange={(e) => setForm({ ...form, monthly_salary_rupees: e.target.value })} />
        <Input label="Working hours/day" type="number" value={form.working_hours_per_day} onChange={(e) => setForm({ ...form, working_hours_per_day: e.target.value })} />
        <Input label="Biometric ID" hint="The ID printed on the biometric device export for this employee." value={form.biometric_id} onChange={(e) => setForm({ ...form, biometric_id: e.target.value })} />
      </div>
      {error && <p className="mt-3 text-[13px] text-rose-600">{error}</p>}
    </Modal>
  );
}

function EmployeeDetailModal({ employee, onClose }: { employee: EmployeeOut; onClose: () => void }) {
  const attendance = useAttendanceRecords({ employee_id: employee.id });
  const payroll = usePayrollList({ employee_id: employee.id });
  const setActive = useSetEmployeeActive();

  return (
    <Modal open onClose={onClose} title={employee.full_name} subtitle={`${employee.designation} · ${employee.department}`} width="max-w-3xl">
      <div className="grid grid-cols-2 gap-3 rounded-xl bg-ink-50 p-4 text-[13px]">
        <div><span className="text-ink-500">Phone</span><p className="font-medium text-ink-900">{employee.phone || '—'}</p></div>
        <div><span className="text-ink-500">Email</span><p className="font-medium text-ink-900">{employee.email || '—'}</p></div>
        <div><span className="text-ink-500">Joined</span><p className="font-medium text-ink-900">{employee.joined_date}</p></div>
        <div><span className="text-ink-500">Biometric ID</span><p className="font-medium text-ink-900">{employee.biometric_id || 'Not enrolled'}</p></div>
        <div><span className="text-ink-500">Monthly Salary</span><p className="font-medium text-ink-900">{employee.monthly_salary_rupees ? `₹${employee.monthly_salary_rupees.toLocaleString('en-IN')}` : '—'}</p></div>
        <div><span className="text-ink-500">Status</span><Badge tone={employee.employment_status === 'active' ? 'active' : 'neutral'}>{employee.employment_status}</Badge></div>
      </div>

      <p className="mb-2 mt-5 text-[13px] font-semibold text-ink-800">Recent Attendance</p>
      <div className="max-h-40 overflow-y-auto rounded-lg ring-1 ring-ink-200/70">
        <table className="w-full text-[12.5px]">
          <tbody>
            {(attendance.data ?? []).slice(0, 10).map((r) => (
              <tr key={r.id} className="border-b border-ink-100 last:border-0">
                <td className="px-3 py-1.5">{r.attendance_date}</td>
                <td className="px-3 py-1.5">{r.working_minutes ? `${Math.floor(r.working_minutes / 60)}h ${r.working_minutes % 60}m` : '—'}</td>
                <td className="px-3 py-1.5"><Badge size="sm" tone={r.status === 'present' ? 'active' : r.status === 'half_day' ? 'attention' : 'critical'}>{r.status.replace('_', ' ')}</Badge></td>
              </tr>
            ))}
            {!attendance.data?.length && <tr><td className="px-3 py-3 text-ink-400">No attendance recorded yet.</td></tr>}
          </tbody>
        </table>
      </div>

      <p className="mb-2 mt-5 text-[13px] font-semibold text-ink-800">Salary History</p>
      <div className="max-h-40 overflow-y-auto rounded-lg ring-1 ring-ink-200/70">
        <table className="w-full text-[12.5px]">
          <tbody>
            {(payroll.data ?? []).map((p) => (
              <tr key={p.id} className="border-b border-ink-100 last:border-0">
                <td className="px-3 py-1.5">{p.month}/{p.year}</td>
                <td className="px-3 py-1.5 tnum">₹{p.net_salary_rupees.toLocaleString('en-IN')}</td>
                <td className="px-3 py-1.5"><Badge size="sm" tone={p.status === 'paid' ? 'active' : 'pending'}>{p.status}</Badge></td>
              </tr>
            ))}
            {!payroll.data?.length && <tr><td className="px-3 py-3 text-ink-400">No payroll calculated yet.</td></tr>}
          </tbody>
        </table>
      </div>

      <div className="mt-5 flex justify-end">
        <Button
          variant={employee.employment_status === 'active' ? 'danger' : 'primary'}
          onClick={() => setActive.mutate({ id: employee.id, active: employee.employment_status !== 'active' })}
          loading={setActive.isPending}
        >
          {employee.employment_status === 'active' ? 'Deactivate Employee' : 'Activate Employee'}
        </Button>
      </div>
    </Modal>
  );
}

export function HrEmployees() {
  const [q, setQ] = useState('');
  const [department, setDepartment] = useState('');
  const [status, setStatus] = useState<'' | 'active' | 'inactive'>('');
  const { data, isLoading } = useEmployees({ q: q || undefined, department: department || undefined, employment_status: (status || undefined) as any });
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<EmployeeOut | null>(null);
  const [detail, setDetail] = useState<EmployeeOut | null>(null);

  const departments = useMemo(() => Array.from(new Set((data ?? []).map((e) => e.department))).sort(), [data]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="tracking-display text-[20px] font-semibold text-ink-900">Employee Management</h1>
          <p className="mt-1 text-[13px] text-ink-500">{data?.length ?? 0} employees</p>
        </div>
        <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => { setEditing(null); setFormOpen(true); }}>Add Employee</Button>
      </div>

      <div className="flex flex-wrap gap-3">
        <Input icon={<Search className="h-4 w-4" />} placeholder="Search employees…" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" />
        <Select value={department} onChange={(e) => setDepartment(e.target.value)} className="max-w-[200px]">
          <option value="">All departments</option>
          {departments.map((d) => <option key={d} value={d}>{d}</option>)}
        </Select>
        <Select value={status} onChange={(e) => setStatus(e.target.value as any)} className="max-w-[160px]">
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </Select>
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-[13.5px]">
          <thead className="bg-ink-50 text-left text-[12px] font-semibold uppercase tracking-wide text-ink-500">
            <tr>
              <th className="px-4 py-2.5">Employee</th>
              <th className="px-4 py-2.5">Department</th>
              <th className="px-4 py-2.5">Designation</th>
              <th className="px-4 py-2.5">Biometric ID</th>
              <th className="px-4 py-2.5">Salary</th>
              <th className="px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} className="px-4 py-6 text-center text-ink-400">Loading…</td></tr>}
            {!isLoading && !data?.length && <tr><td colSpan={7} className="px-4 py-6 text-center text-ink-400">No employees found.</td></tr>}
            {(data ?? []).map((e) => (
              <tr key={e.id} className="border-t border-ink-100 hover:bg-ink-50/60">
                <td className="flex items-center gap-2 px-4 py-2.5 font-medium text-ink-900">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink-100 text-[11px] font-semibold text-ink-600"><User className="h-3.5 w-3.5" /></span>
                  {e.full_name}
                </td>
                <td className="px-4 py-2.5 text-ink-600">{e.department}</td>
                <td className="px-4 py-2.5 text-ink-600">{e.designation}</td>
                <td className="px-4 py-2.5 text-ink-600">{e.biometric_id || '—'}</td>
                <td className="px-4 py-2.5 tnum text-ink-600">{e.monthly_salary_rupees ? `₹${e.monthly_salary_rupees.toLocaleString('en-IN')}` : '—'}</td>
                <td className="px-4 py-2.5"><Badge size="sm" tone={e.employment_status === 'active' ? 'active' : 'neutral'}>{e.employment_status}</Badge></td>
                <td className="px-4 py-2.5 text-right">
                  <Button size="sm" variant="ghost" onClick={() => setDetail(e)}>View</Button>
                  <Button size="sm" variant="ghost" onClick={() => { setEditing(e); setFormOpen(true); }}>Edit</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {formOpen && <EmployeeFormModal open={formOpen} onClose={() => setFormOpen(false)} employee={editing} />}
      {detail && <EmployeeDetailModal employee={detail} onClose={() => setDetail(null)} />}
    </div>
  );
}
