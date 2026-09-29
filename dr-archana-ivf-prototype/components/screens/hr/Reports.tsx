'use client';

import React, { useState } from 'react';
import { Card, CardHeader, Button, Input, Select } from '@/components/ui/primitives';
import { Download, FileText, Wallet, AlertTriangle } from 'lucide-react';
import { downloadHrReport, useEmployees, type AttendanceStatus } from '@/lib/api/hr';

function ReportCard({
  icon, title, description, onExport,
}: { icon: React.ReactNode; title: string; description: string; onExport: () => void }) {
  return (
    <Card className="p-5">
      <CardHeader icon={icon} title={title} subtitle={description} />
      <div className="px-1">
        <Button variant="primary" icon={<Download className="h-4 w-4" />} onClick={onExport}>Export CSV</Button>
      </div>
    </Card>
  );
}

export function HrReports() {
  const { data: employees } = useEmployees();
  const departments = Array.from(new Set((employees ?? []).map((e) => e.department))).sort();

  const [attFrom, setAttFrom] = useState('');
  const [attTo, setAttTo] = useState('');
  const [attDept, setAttDept] = useState('');
  const [attStatus, setAttStatus] = useState<'' | AttendanceStatus>('');

  const [payMonth, setPayMonth] = useState('');
  const [payYear, setPayYear] = useState('');
  const [payDept, setPayDept] = useState('');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="tracking-display text-[20px] font-semibold text-ink-900">Reports</h1>
        <p className="mt-1 text-[13px] text-ink-500">Export attendance, payroll, and delay data as CSV — filters apply to each export.</p>
      </div>

      <Card className="p-5">
        <CardHeader icon={<FileText className="h-4 w-4" />} title="Attendance Report" subtitle="Filter by date range, department, and status" />
        <div className="flex flex-wrap items-end gap-3 px-1">
          <Input type="date" label="From" value={attFrom} onChange={(e) => setAttFrom(e.target.value)} className="max-w-[160px]" />
          <Input type="date" label="To" value={attTo} onChange={(e) => setAttTo(e.target.value)} className="max-w-[160px]" />
          <Select label="Department" value={attDept} onChange={(e) => setAttDept(e.target.value)} className="max-w-[180px]">
            <option value="">All</option>
            {departments.map((d) => <option key={d} value={d}>{d}</option>)}
          </Select>
          <Select label="Status" value={attStatus} onChange={(e) => setAttStatus(e.target.value as any)} className="max-w-[160px]">
            <option value="">All</option>
            <option value="present">Present</option>
            <option value="half_day">Half Day</option>
            <option value="absent">Absent</option>
          </Select>
          <Button
            variant="primary" icon={<Download className="h-4 w-4" />}
            onClick={() => {
              const qs = new URLSearchParams();
              if (attFrom) qs.set('from_date', attFrom);
              if (attTo) qs.set('to_date', attTo);
              if (attDept) qs.set('department', attDept);
              if (attStatus) qs.set('status', attStatus);
              downloadHrReport(`/hr/reports/attendance.csv?${qs}`, 'attendance_report.csv');
            }}
          >
            Export
          </Button>
        </div>
      </Card>

      <Card className="p-5">
        <CardHeader icon={<Wallet className="h-4 w-4" />} title="Payroll Report" subtitle="Filter by month, year, and department" />
        <div className="flex flex-wrap items-end gap-3 px-1">
          <Input type="number" label="Month" placeholder="e.g. 9" value={payMonth} onChange={(e) => setPayMonth(e.target.value)} className="max-w-[120px]" />
          <Input type="number" label="Year" placeholder="e.g. 2026" value={payYear} onChange={(e) => setPayYear(e.target.value)} className="max-w-[120px]" />
          <Select label="Department" value={payDept} onChange={(e) => setPayDept(e.target.value)} className="max-w-[180px]">
            <option value="">All</option>
            {departments.map((d) => <option key={d} value={d}>{d}</option>)}
          </Select>
          <Button
            variant="primary" icon={<Download className="h-4 w-4" />}
            onClick={() => {
              const qs = new URLSearchParams();
              if (payMonth) qs.set('month', payMonth);
              if (payYear) qs.set('year', payYear);
              if (payDept) qs.set('department', payDept);
              downloadHrReport(`/hr/reports/payroll.csv?${qs}`, 'payroll_report.csv');
            }}
          >
            Export
          </Button>
        </div>
      </Card>

      <ReportCard
        icon={<AlertTriangle className="h-4 w-4" />}
        title="Delay Report"
        description="Currently delayed/critical patients — stage, expected vs actual time, and recorded reason."
        onExport={() => downloadHrReport('/hr/reports/delays.csv', 'delay_report.csv')}
      />
    </div>
  );
}
