'use client';

import React from 'react';
import { Card, CardHeader, Badge, Skeleton } from '@/components/ui/primitives';
import { DonutChart } from '@/components/ui/charts';
import { useHrDashboard, useHrAlerts, useResolveHrAlert } from '@/lib/api/hr';
import { Users, Fingerprint, Wallet, Activity, AlertTriangle, X } from 'lucide-react';

function StatCard({ label, value, hint, tone }: { label: string; value: React.ReactNode; hint?: string; tone?: 'default' | 'critical' | 'warning' }) {
  return (
    <Card className="p-4">
      <p className="text-[12.5px] font-medium text-ink-500">{label}</p>
      <p
        className={
          'tnum mt-1.5 text-[24px] font-semibold tracking-[-0.02em] ' +
          (tone === 'critical' ? 'text-rose-600' : tone === 'warning' ? 'text-amber-600' : 'text-ink-900')
        }
      >
        {value}
      </p>
      {hint && <p className="mt-1 text-[12px] text-ink-400">{hint}</p>}
    </Card>
  );
}

export function HrDashboardHome({ onNavigate }: { onNavigate: (v: any) => void }) {
  const { data, isLoading } = useHrDashboard();
  const { data: alerts } = useHrAlerts();
  const resolveAlert = useResolveHrAlert();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="tracking-display text-[22px] font-semibold text-ink-900">HR & Operations Overview</h1>
        <p className="mt-1 text-[13.5px] text-ink-500">Employees, attendance, payroll, and live patient-flow status.</p>
      </div>

      {!!alerts?.length && (
        <Card className="border-amber-200 bg-amber-50/60 p-4">
          <div className="mb-2 flex items-center gap-2 text-[13.5px] font-semibold text-amber-800">
            <AlertTriangle className="h-4 w-4" /> Operational Alerts ({alerts.length})
          </div>
          <div className="space-y-2">
            {alerts.slice(0, 5).map((a) => (
              <div key={a.key} className="flex items-start justify-between gap-3 rounded-lg bg-white px-3 py-2 ring-1 ring-ink-200/70">
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-ink-900">
                    {a.severity === 'critical' ? '🔴' : '⚠️'} {a.title}
                  </p>
                  <p className="mt-0.5 text-[12.5px] text-ink-600">{a.body}</p>
                </div>
                <button
                  onClick={() => resolveAlert.mutate(a.key)}
                  className="shrink-0 rounded-md p-1 text-ink-400 hover:bg-ink-100 hover:text-ink-700"
                  title="Dismiss"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {isLoading || !data ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}
        </div>
      ) : (
        <>
          <section>
            <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wide text-ink-500">
              <Users className="h-3.5 w-3.5" /> Employees
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
              <StatCard label="Total Employees" value={data.employees.total_employees} />
              <StatCard label="Present Today" value={data.employees.present_today} />
              <StatCard label="Half Day Today" value={data.employees.half_day_today} tone={data.employees.half_day_today > 0 ? 'warning' : 'default'} />
              <StatCard label="Absent Today" value={data.employees.absent_today} tone={data.employees.absent_today > 0 ? 'critical' : 'default'} />
              <StatCard label="Late Arrivals" value={data.employees.late_arrivals} tone={data.employees.late_arrivals > 0 ? 'warning' : 'default'} />
              <StatCard label="Currently Inside" value={data.employees.currently_inside} />
            </div>
          </section>

          <section>
            <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wide text-ink-500">
              <Fingerprint className="h-3.5 w-3.5" /> Attendance
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Card className="p-4">
                <p className="text-[12.5px] font-medium text-ink-500">Today's Attendance</p>
                <div className="mt-3">
                  <DonutChart
                    size={140}
                    centerLabel="Present"
                    centerValue={`${data.attendance.attendance_percent}%`}
                    data={[
                      { label: 'Present', value: data.employees.present_today, color: '#059669' },
                      { label: 'Half Day', value: data.employees.half_day_today, color: '#d97706' },
                      { label: 'Absent', value: data.employees.absent_today || 0.001, color: '#e11d48' },
                    ]}
                  />
                </div>
              </Card>
              <StatCard label="Average Working Hours" value={`${data.attendance.avg_working_hours}h`} />
              <StatCard label="Total Overtime Hours (today)" value={`${data.attendance.total_overtime_hours}h`} />
            </div>
          </section>

          <section>
            <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wide text-ink-500">
              <Wallet className="h-3.5 w-3.5" /> Payroll — this month
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatCard label="Calculated" value={data.payroll.current_month_calculated} />
              <StatCard label="Pending Approval" value={data.payroll.pending_approval} tone={data.payroll.pending_approval > 0 ? 'warning' : 'default'} />
              <StatCard label="Total Salary" value={`₹${data.payroll.total_salary_this_month_rupees.toLocaleString('en-IN')}`} />
              <StatCard label="With Deductions" value={data.payroll.employees_with_deductions} />
            </div>
          </section>

          <section>
            <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold uppercase tracking-wide text-ink-500">
              <Activity className="h-3.5 w-3.5" /> Patient Operations
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
              <StatCard label="Patients In Process" value={data.patient_ops.patients_in_process} />
              <StatCard label="Avg. Waiting Time" value={`${data.patient_ops.avg_waiting_time_minutes}m`} />
              <StatCard label="Avg. Consultation Time" value={`${data.patient_ops.avg_consultation_time_minutes}m`} />
              <StatCard label="Avg. Pharmacy Time" value={`${data.patient_ops.avg_pharmacy_time_minutes}m`} />
              <StatCard label="Active Delays" value={data.patient_ops.active_delays} tone={data.patient_ops.active_delays > 0 ? 'warning' : 'default'} />
              <StatCard
                label="Critical Delays"
                value={data.patient_ops.critical_delays}
                tone={data.patient_ops.critical_delays > 0 ? 'critical' : 'default'}
              />
            </div>
            {data.patient_ops.active_delays > 0 && (
              <button onClick={() => onNavigate('delays')} className="mt-3 text-[13px] font-medium text-brand-700 hover:underline">
                View delayed patients →
              </button>
            )}
          </section>
        </>
      )}
    </div>
  );
}
