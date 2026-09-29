'use client';

import React, { useRef, useState } from 'react';
import { Card, CardHeader, Button, Badge, Input, Select, InfoNote, Tabs, Modal } from '@/components/ui/primitives';
import { UploadCloud, AlertTriangle, FileSpreadsheet, CalendarCheck, Lock, Unlock } from 'lucide-react';
import {
  useAttendanceRecords, useAttendanceIssues, useResolveAttendanceRecord,
  useUploadAttendanceImport, useAttendanceImportRows, useConfirmAttendanceImport,
  useEmployees, useMonthlyAttendance, usePeriodSummary, useFinalizePeriod, useReopenPeriod,
  type AttendanceStatus, type MonthlyAttendanceRowOut,
} from '@/lib/api/hr';
import { useApp } from '@/lib/store';

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function UploadPanel() {
  const { toast } = useApp();
  const fileRef = useRef<HTMLInputElement>(null);
  const upload = useUploadAttendanceImport();
  const confirm = useConfirmAttendanceImport();
  const [importId, setImportId] = useState<string | null>(null);
  const rows = useAttendanceImportRows(importId);
  const imp = upload.data && upload.data.id === importId ? upload.data : null;

  const pick = () => fileRef.current?.click();
  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    upload.mutate(file, {
      onSuccess: (result) => setImportId(result.id),
      onError: (err: any) => toast({ title: 'Upload failed', body: err?.message, tone: 'error' }),
    });
    e.target.value = '';
  };

  const doConfirm = () => {
    if (!importId) return;
    confirm.mutate(importId, {
      onSuccess: () => { toast({ title: 'Attendance imported', tone: 'success' }); setImportId(null); },
      onError: (err: any) => toast({ title: 'Import failed', body: err?.message, tone: 'error' }),
    });
  };

  return (
    <Card className="p-5">
      <CardHeader icon={<UploadCloud className="h-4 w-4" />} title="Upload Attendance" subtitle="Upload the biometric device's exported .xlsx file." />
      <div className="px-1 pb-1">
        {!imp ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-ink-200 py-10 text-center">
            <FileSpreadsheet className="h-8 w-8 text-ink-300" />
            <p className="text-[13.5px] text-ink-500">Select the biometric attendance Excel file (.xlsx)</p>
            <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden" onChange={onFile} />
            <Button variant="primary" icon={<UploadCloud className="h-4 w-4" />} loading={upload.isPending} onClick={pick}>
              Select Excel File
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <InfoNote tone={imp.unknown_count > 0 ? 'amber' : 'brand'} icon={<AlertTriangle className="h-4 w-4" />}>
              Attendance Preview — <strong>{imp.records_found}</strong> records found, <strong>{imp.matched_count}</strong> matched,{' '}
              <strong>{imp.unknown_count}</strong> unknown IDs, <strong>{imp.duplicate_count}</strong> duplicates
              {imp.error_count > 0 && <> , <strong>{imp.error_count}</strong> errors</>}.
            </InfoNote>

            <div className="max-h-64 overflow-y-auto rounded-lg ring-1 ring-ink-200/70">
              <table className="w-full text-[12.5px]">
                <thead className="sticky top-0 bg-ink-50 text-left text-[11.5px] font-semibold uppercase tracking-wide text-ink-500">
                  <tr>
                    <th className="px-3 py-2">Biometric ID</th>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Entry</th>
                    <th className="px-3 py-2">Exit</th>
                    <th className="px-3 py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(rows.data ?? []).map((r) => (
                    <tr key={r.id} className="border-t border-ink-100">
                      <td className="px-3 py-1.5">{r.biometric_id}</td>
                      <td className="px-3 py-1.5">{r.attendance_date ?? '—'}</td>
                      <td className="px-3 py-1.5">{r.entry_time ? new Date(r.entry_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—'}</td>
                      <td className="px-3 py-1.5">{r.exit_time ? new Date(r.exit_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—'}</td>
                      <td className="px-3 py-1.5">
                        {r.is_unknown && <Badge size="sm" tone="critical">Unknown ID</Badge>}
                        {!r.is_unknown && r.is_duplicate && <Badge size="sm" tone="attention">Duplicate</Badge>}
                        {!r.is_unknown && !r.is_duplicate && !r.error && <Badge size="sm" tone="active">Matched</Badge>}
                        {r.error && <Badge size="sm" tone="critical">{r.error}</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setImportId(null)}>Cancel</Button>
              <Button variant="primary" loading={confirm.isPending} onClick={doConfirm}>Confirm Import</Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function IssuesPanel() {
  const { data: issues } = useAttendanceIssues();
  const resolve = useResolveAttendanceRecord();
  const { data: employees } = useEmployees();
  const nameOf = (id: string) => employees?.find((e) => e.id === id)?.full_name ?? id;

  if (!issues?.length) return null;
  return (
    <Card className="border-amber-200 bg-amber-50/50 p-4">
      <p className="mb-2 flex items-center gap-2 text-[13.5px] font-semibold text-amber-800">
        <AlertTriangle className="h-4 w-4" /> Attendance Issues ({issues.length})
      </p>
      <div className="space-y-2">
        {issues.map((i) => (
          <div key={i.id} className="flex items-center justify-between rounded-lg bg-white px-3 py-2 ring-1 ring-ink-200/70">
            <p className="text-[13px] text-ink-800">
              <strong>{nameOf(i.employee_id)}</strong> — {i.attendance_date} — {i.missing_exit ? 'Missing Exit Scan' : 'Missing Entry Scan'}
              {i.entry_time && <span className="text-ink-500"> (Entry {new Date(i.entry_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })})</span>}
            </p>
            <Button size="sm" variant="secondary" loading={resolve.isPending} onClick={() => resolve.mutate(i.id)}>Mark Reviewed</Button>
          </div>
        ))}
      </div>
    </Card>
  );
}

function RecordsTable() {
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [status, setStatus] = useState<'' | AttendanceStatus>('');
  const { data: employees } = useEmployees();
  const { data, isLoading } = useAttendanceRecords({ from_date: fromDate || undefined, to_date: toDate || undefined, status: (status || undefined) as any });
  const nameOf = (id: string) => employees?.find((e) => e.id === id)?.full_name ?? id;
  const deptOf = (id: string) => employees?.find((e) => e.id === id)?.department ?? '—';

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4">
        <Input type="date" label="From" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="max-w-[160px]" />
        <Input type="date" label="To" value={toDate} onChange={(e) => setToDate(e.target.value)} className="max-w-[160px]" />
        <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value as any)} className="max-w-[160px]">
          <option value="">All</option>
          <option value="present">Present</option>
          <option value="half_day">Half Day</option>
          <option value="absent">Absent</option>
        </Select>
      </div>
      <table className="w-full text-[13.5px]">
        <thead className="bg-ink-50 text-left text-[12px] font-semibold uppercase tracking-wide text-ink-500">
          <tr>
            <th className="px-4 py-2.5">Employee</th>
            <th className="px-4 py-2.5">Department</th>
            <th className="px-4 py-2.5">Date</th>
            <th className="px-4 py-2.5">Entry</th>
            <th className="px-4 py-2.5">Exit</th>
            <th className="px-4 py-2.5">Working Hours</th>
            <th className="px-4 py-2.5">Status</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && <tr><td colSpan={7} className="px-4 py-6 text-center text-ink-400">Loading…</td></tr>}
          {!isLoading && !data?.length && <tr><td colSpan={7} className="px-4 py-6 text-center text-ink-400">No attendance records for this filter.</td></tr>}
          {(data ?? []).map((r) => (
            <tr key={r.id} className="border-t border-ink-100">
              <td className="px-4 py-2 font-medium text-ink-900">{nameOf(r.employee_id)}</td>
              <td className="px-4 py-2 text-ink-600">{deptOf(r.employee_id)}</td>
              <td className="px-4 py-2 text-ink-600">{r.attendance_date}</td>
              <td className="px-4 py-2 text-ink-600">{r.entry_time ? new Date(r.entry_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—'}</td>
              <td className="px-4 py-2 text-ink-600">{r.exit_time ? new Date(r.exit_time).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—'}</td>
              <td className="px-4 py-2 tnum text-ink-600">{r.working_minutes ? `${Math.floor(r.working_minutes / 60)}h ${r.working_minutes % 60}m` : '—'}</td>
              <td className="px-4 py-2">
                <Badge size="sm" tone={r.status === 'present' ? 'active' : r.status === 'half_day' ? 'attention' : 'critical'}>{r.status.replace('_', ' ')}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function DayDetailModal({ row, month, year, onClose }: { row: MonthlyAttendanceRowOut; month: number; year: number; onClose: () => void }) {
  const daysInMonth = new Date(year, month, 0).getDate();
  const labelFor = (code: string | null) => (code === 'P' ? 'Present' : code === 'HD' ? 'Half Day' : code === 'A' ? 'Absent' : code === '?' ? 'Unprocessed' : 'Off / N/A');
  const toneFor = (code: string | null) =>
    code === 'P' ? 'active' : code === 'HD' ? 'attention' : code === 'A' ? 'critical' : code === '?' ? 'pending' : 'neutral';
  return (
    <Modal open onClose={onClose} title={row.full_name} subtitle={`${row.department} — ${MONTH_NAMES[month - 1]} ${year} daily attendance`} width="max-w-2xl">
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
        {Array.from({ length: daysInMonth }, (_, i) => i + 1).map((day) => {
          const code = row.days[day] ?? null;
          return (
            <div key={day} className="rounded-lg border border-ink-200/70 p-2 text-center">
              <p className="text-[11px] font-medium text-ink-400">{day}</p>
              <Badge size="sm" tone={toneFor(code) as any} dot={false} className="mt-1 justify-center">{code ?? '—'}</Badge>
              <p className="mt-1 text-[10.5px] text-ink-400">{labelFor(code)}</p>
            </div>
          );
        })}
      </div>
    </Modal>
  );
}

function FinalizeSection({ month, year }: { month: number; year: number }) {
  const { toast, permissions } = useApp();
  const { data: summary, isLoading } = usePeriodSummary(year, month);
  const finalize = useFinalizePeriod();
  const reopen = useReopenPeriod();
  const [overrideMode, setOverrideMode] = useState(false);
  const [reason, setReason] = useState('');
  const [blockedMessage, setBlockedMessage] = useState<string | null>(null);

  const canFinalize = permissions.includes('hr.attendance_finalize');

  if (isLoading || !summary) {
    return <Card className="p-4 text-[13px] text-ink-400">Loading attendance period…</Card>;
  }

  const isFinalized = summary.period.status === 'finalized';

  const doFinalize = (override: boolean) => {
    setBlockedMessage(null);
    finalize.mutate(
      { year, month, override, reason: override ? reason : undefined },
      {
        onSuccess: () => {
          toast({ title: 'Attendance period finalized', tone: 'success' });
          setOverrideMode(false);
          setReason('');
        },
        onError: (err: any) => {
          if (err?.errorCode === 'attendance_incomplete') {
            setOverrideMode(true);
          } else {
            setBlockedMessage(err?.message ?? 'Could not finalize the attendance period.');
          }
        },
      }
    );
  };

  return (
    <Card className={isFinalized ? 'border-emerald-200 bg-emerald-50/40 p-4' : 'border-amber-200 bg-amber-50/40 p-4'}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {isFinalized ? <Lock className="h-4 w-4 text-emerald-700" /> : <CalendarCheck className="h-4 w-4 text-amber-700" />}
          <div>
            <p className="text-[13.5px] font-semibold text-ink-900">
              {isFinalized ? `Attendance Period: FINALIZED` : 'Attendance period in progress'}
            </p>
            <p className="text-[12.5px] text-ink-500">
              {summary.processed_days} of {summary.working_days} working day(s) processed
              {summary.unprocessed_days > 0 && ` — ${summary.unprocessed_days} unprocessed`}
              {isFinalized && summary.period.override_used && ' — finalized with override'}
            </p>
          </div>
        </div>
        {canFinalize && (
          isFinalized ? (
            <Button variant="secondary" size="sm" icon={<Unlock className="h-4 w-4" />} loading={reopen.isPending}
              onClick={() => reopen.mutate({ year, month }, { onSuccess: () => toast({ title: 'Attendance period reopened', tone: 'success' }) })}>
              Reopen Period
            </Button>
          ) : (
            <Button variant="primary" size="sm" loading={finalize.isPending} onClick={() => doFinalize(false)}>
              Finalize Attendance
            </Button>
          )
        )}
      </div>

      {blockedMessage && (
        <div className="mt-3">
          <InfoNote tone="amber" icon={<AlertTriangle className="h-4 w-4" />}>
            {blockedMessage}
          </InfoNote>
        </div>
      )}

      {!isFinalized && overrideMode && canFinalize && (
        <div className="mt-3 space-y-2 rounded-lg bg-white p-3 ring-1 ring-amber-200">
          <p className="text-[13px] text-amber-800">
            {summary.unprocessed_days} working day(s) are unprocessed. Finalizing anyway requires a reason and will be recorded on the audit log.
          </p>
          <Input label="Override reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Two employees on unrecorded field duty" />
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="secondary" onClick={() => { setOverrideMode(false); setReason(''); }}>Cancel</Button>
            <Button size="sm" variant="primary" loading={finalize.isPending} disabled={!reason.trim()} onClick={() => doFinalize(true)}>
              Finalize With Override
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

function MonthlyAttendancePanel() {
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());
  const { data, isLoading } = useMonthlyAttendance({ month, year });
  const [selected, setSelected] = useState<MonthlyAttendanceRowOut | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <Select value={month} onChange={(e) => setMonth(Number(e.target.value))} className="max-w-[180px]">
          {MONTH_NAMES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
        </Select>
        <Select value={year} onChange={(e) => setYear(Number(e.target.value))} className="max-w-[120px]">
          {[year - 1, year, year + 1].map((y) => <option key={y} value={y}>{y}</option>)}
        </Select>
      </div>

      <FinalizeSection month={month} year={year} />

      <Card className="overflow-hidden">
        <table className="w-full text-[13.5px]">
          <thead className="bg-ink-50 text-left text-[12px] font-semibold uppercase tracking-wide text-ink-500">
            <tr>
              <th className="px-4 py-2.5">Employee</th>
              <th className="px-4 py-2.5">Present</th>
              <th className="px-4 py-2.5">Half Day</th>
              <th className="px-4 py-2.5">Absent</th>
              <th className="px-4 py-2.5">Unprocessed</th>
              <th className="px-4 py-2.5">Attendance %</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} className="px-4 py-6 text-center text-ink-400">Loading…</td></tr>}
            {!isLoading && !data?.length && <tr><td colSpan={6} className="px-4 py-6 text-center text-ink-400">No active employees found.</td></tr>}
            {(data ?? []).map((row) => (
              <tr key={row.employee_id} className="cursor-pointer border-t border-ink-100 hover:bg-ink-50/60" onClick={() => setSelected(row)}>
                <td className="px-4 py-2 font-medium text-ink-900">{row.full_name}</td>
                <td className="px-4 py-2 tnum text-ink-600">{row.present_days}</td>
                <td className="px-4 py-2 tnum text-ink-600">{row.half_days}</td>
                <td className="px-4 py-2 tnum text-ink-600">{row.absent_days}</td>
                <td className="px-4 py-2 tnum">
                  {row.unprocessed_days > 0 ? <Badge size="sm" tone="pending">{row.unprocessed_days}</Badge> : <span className="text-ink-400">0</span>}
                </td>
                <td className="px-4 py-2 tnum text-ink-600">{row.attendance_percent}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {selected && <DayDetailModal row={selected} month={month} year={year} onClose={() => setSelected(null)} />}
    </div>
  );
}

export function HrAttendance() {
  const [tab, setTab] = useState('records');
  return (
    <div className="space-y-4">
      <div>
        <h1 className="tracking-display text-[20px] font-semibold text-ink-900">Biometric Attendance</h1>
        <p className="mt-1 text-[13px] text-ink-500">Import attendance from the biometric device and review the daily record.</p>
      </div>
      <Tabs
        tabs={[
          { id: 'records', label: 'Attendance Records' },
          { id: 'monthly', label: 'Monthly Attendance' },
          { id: 'upload', label: 'Upload Attendance' },
        ]}
        active={tab}
        onChange={setTab}
      />
      {tab === 'records' && (
        <div className="space-y-4">
          <IssuesPanel />
          <RecordsTable />
        </div>
      )}
      {tab === 'monthly' && <MonthlyAttendancePanel />}
      {tab === 'upload' && <UploadPanel />}
    </div>
  );
}
