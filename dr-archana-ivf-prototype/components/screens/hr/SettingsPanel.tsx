'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardHeader, Button, Input } from '@/components/ui/primitives';
import { SlidersHorizontal, Clock, Wallet } from 'lucide-react';
import { useHrSettings, useUpdateHrSettings, useProcessThresholds, useUpdateProcessThresholds } from '@/lib/api/hr';
import { useApp } from '@/lib/store';

const STAGE_LABELS: Record<string, string> = {
  arrived: 'Front Desk (Arrival)', waiting: 'Waiting Room', consultation: 'Consultation',
  investigation: 'Investigation', billing: 'Billing', pharmacy: 'Pharmacy', follow_up: 'Follow-up',
};

export function HrSettingsPanel() {
  const { toast } = useApp();
  const { data: settings } = useHrSettings();
  const updateSettings = useUpdateHrSettings();
  const { data: thresholdsData } = useProcessThresholds();
  const updateThresholds = useUpdateProcessThresholds();

  const [form, setForm] = useState<Record<string, string>>({});
  const [thresholds, setThresholds] = useState<Record<string, string>>({});

  useEffect(() => {
    if (settings) {
      setForm({
        full_day_hours: String(settings.full_day_hours),
        half_day_min_hours: String(settings.half_day_min_hours),
        late_arrival_grace_minutes: String(settings.late_arrival_grace_minutes),
        early_departure_grace_minutes: String(settings.early_departure_grace_minutes),
        standard_start_time: settings.standard_start_time,
        standard_end_time: settings.standard_end_time,
        working_days_per_month: String(settings.working_days_per_month),
        half_day_pay_fraction: String(settings.half_day_pay_fraction),
        absent_day_pay_fraction: String(settings.absent_day_pay_fraction),
        overtime_rate_per_hour_rupees: String(settings.overtime_rate_per_hour_rupees),
      });
    }
  }, [settings]);

  useEffect(() => {
    if (thresholdsData) {
      const t: Record<string, string> = {};
      Object.entries(thresholdsData.thresholds).forEach(([k, v]) => { t[k] = String(v); });
      setThresholds(t);
    }
  }, [thresholdsData]);

  const saveSettings = () => {
    updateSettings.mutate(
      {
        full_day_hours: Number(form.full_day_hours), half_day_min_hours: Number(form.half_day_min_hours),
        late_arrival_grace_minutes: Number(form.late_arrival_grace_minutes), early_departure_grace_minutes: Number(form.early_departure_grace_minutes),
        standard_start_time: form.standard_start_time, standard_end_time: form.standard_end_time,
        working_days_per_month: Number(form.working_days_per_month), half_day_pay_fraction: Number(form.half_day_pay_fraction),
        absent_day_pay_fraction: Number(form.absent_day_pay_fraction),
        overtime_rate_per_hour_rupees: Number(form.overtime_rate_per_hour_rupees),
      },
      { onSuccess: () => toast({ title: 'HR settings saved', tone: 'success' }) }
    );
  };

  const saveThresholds = () => {
    const payload: Record<string, number> = {};
    Object.entries(thresholds).forEach(([k, v]) => { payload[k] = Number(v); });
    updateThresholds.mutate(payload, { onSuccess: () => toast({ title: 'Process thresholds saved', tone: 'success' }) });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="tracking-display text-[20px] font-semibold text-ink-900">HR Settings</h1>
        <p className="mt-1 text-[13px] text-ink-500">Attendance thresholds, payroll rules, and patient-process delay thresholds.</p>
      </div>

      <Card className="p-5">
        <CardHeader icon={<Clock className="h-4 w-4" />} title="Attendance Thresholds" subtitle="Determine Present / Half Day / Absent from working hours" />
        <div className="grid grid-cols-2 gap-4 px-1">
          <Input label="Required Full Day Hours" type="number" step="0.5" value={form.full_day_hours ?? ''} onChange={(e) => setForm({ ...form, full_day_hours: e.target.value })} />
          <Input label="Minimum Half Day Hours" type="number" step="0.5" value={form.half_day_min_hours ?? ''} onChange={(e) => setForm({ ...form, half_day_min_hours: e.target.value })} />
          <Input label="Standard Start Time" type="time" value={form.standard_start_time ?? ''} onChange={(e) => setForm({ ...form, standard_start_time: e.target.value })} />
          <Input label="Standard End Time" type="time" value={form.standard_end_time ?? ''} onChange={(e) => setForm({ ...form, standard_end_time: e.target.value })} />
          <Input label="Late Arrival Grace (minutes)" type="number" value={form.late_arrival_grace_minutes ?? ''} onChange={(e) => setForm({ ...form, late_arrival_grace_minutes: e.target.value })} />
          <Input label="Early Departure Grace (minutes)" type="number" value={form.early_departure_grace_minutes ?? ''} onChange={(e) => setForm({ ...form, early_departure_grace_minutes: e.target.value })} />
        </div>
      </Card>

      <Card className="p-5">
        <CardHeader icon={<Wallet className="h-4 w-4" />} title="Payroll Rules" subtitle="How attendance translates into payable salary" />
        <div className="grid grid-cols-2 gap-4 px-1">
          <Input label="Working Days / Month" type="number" value={form.working_days_per_month ?? ''} onChange={(e) => setForm({ ...form, working_days_per_month: e.target.value })} />
          <Input label="Half-Day Pay Fraction" type="number" step="0.05" hint="0.5 = a half day earns half a day's pay" value={form.half_day_pay_fraction ?? ''} onChange={(e) => setForm({ ...form, half_day_pay_fraction: e.target.value })} />
          <Input label="Absent-Day Pay Fraction" type="number" step="0.05" min="0" max="1" hint="0 = an absent day receives no pay" value={form.absent_day_pay_fraction ?? ''} onChange={(e) => setForm({ ...form, absent_day_pay_fraction: e.target.value })} />
          <Input label="Overtime Rate (₹/hour)" type="number" hint="0 = overtime hours are shown but not paid" value={form.overtime_rate_per_hour_rupees ?? ''} onChange={(e) => setForm({ ...form, overtime_rate_per_hour_rupees: e.target.value })} />
        </div>
        <div className="mt-5 rounded-xl bg-ink-50 px-4 py-3.5 text-[13px] leading-relaxed text-ink-600">
          <p className="mb-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-ink-500">How Salary Is Calculated</p>
          <p className="tnum">Daily Salary = Monthly Salary ÷ Working Days</p>
          <ul className="mt-1.5 space-y-0.5">
            <li>Present → 100% of daily salary</li>
            <li>Half Day → Half-Day Pay Fraction × daily salary</li>
            <li>Absent → Absent-Day Pay Fraction × daily salary</li>
            <li>Overtime → Overtime Hours × Overtime Rate</li>
          </ul>
        </div>
        <div className="mt-4 px-1">
          <Button variant="primary" loading={updateSettings.isPending} onClick={saveSettings}>Save Attendance & Payroll Settings</Button>
        </div>
      </Card>

      <Card className="p-5">
        <CardHeader icon={<SlidersHorizontal className="h-4 w-4" />} title="Patient Process Thresholds" subtitle="Expected duration (minutes) for each stage before it's flagged as delayed" />
        <div className="grid grid-cols-2 gap-4 px-1 md:grid-cols-3">
          {Object.keys(STAGE_LABELS).map((stage) => (
            <Input
              key={stage} label={STAGE_LABELS[stage]} type="number"
              value={thresholds[stage] ?? ''} onChange={(e) => setThresholds({ ...thresholds, [stage]: e.target.value })}
            />
          ))}
        </div>
        <div className="mt-4 px-1">
          <Button variant="primary" loading={updateThresholds.isPending} onClick={saveThresholds}>Save Process Thresholds</Button>
        </div>
      </Card>
    </div>
  );
}
