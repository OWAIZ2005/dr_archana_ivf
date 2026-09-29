'use client';

import React from 'react';
import { Card, Skeleton } from '@/components/ui/primitives';
import { useProcessFlow } from '@/lib/api/hr';

const STAGE_LABELS: Record<string, string> = {
  arrived: 'Front Desk',
  waiting: 'Waiting Room',
  consultation: 'Consultation',
  investigation: 'Investigation',
  billing: 'Billing',
  pharmacy: 'Pharmacy',
  follow_up: 'Follow-up',
};

function severityDot(sev: 'normal' | 'warning' | 'delayed' | 'critical') {
  return { normal: 'bg-emerald-500', warning: 'bg-amber-500', delayed: 'bg-rose-500', critical: 'bg-rose-800' }[sev];
}

export function HrPatientFlow() {
  const { data, isLoading } = useProcessFlow();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="tracking-display text-[20px] font-semibold text-ink-900">Real-Time Patient Flow</h1>
        <p className="mt-1 text-[13px] text-ink-500">
          Operational monitoring only — patient identity and clinical details stay in the clinical system. Refreshes automatically every 30s.
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">{Array.from({ length: 7 }).map((_, i) => <Skeleton key={i} className="h-32 rounded-2xl" />)}</div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {(data ?? []).map((s) => {
            const worst: 'normal' | 'warning' | 'delayed' | 'critical' = s.critical > 0 ? 'critical' : s.delayed > 0 ? 'delayed' : s.warning > 0 ? 'warning' : 'normal';
            return (
              <Card key={s.stage} className="p-4">
                <div className="flex items-center justify-between">
                  <p className="text-[13px] font-semibold text-ink-800">{STAGE_LABELS[s.stage] ?? s.stage}</p>
                  <span className={`h-2.5 w-2.5 rounded-full ${severityDot(worst)}`} />
                </div>
                <p className="tnum mt-2 text-[28px] font-semibold text-ink-900">{s.total}</p>
                <p className="text-[12px] text-ink-400">patients · threshold {s.threshold_minutes}m</p>
                <div className="mt-3 flex gap-1.5 text-[11px]">
                  {s.normal > 0 && <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-700">{s.normal} normal</span>}
                  {s.warning > 0 && <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-700">{s.warning} approaching</span>}
                  {s.delayed > 0 && <span className="rounded-full bg-rose-100 px-2 py-0.5 font-medium text-rose-700">{s.delayed} delayed</span>}
                  {s.critical > 0 && <span className="rounded-full bg-rose-900/10 px-2 py-0.5 font-medium text-rose-900">{s.critical} critical</span>}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Card className="p-4">
        <p className="mb-3 text-[13px] font-semibold text-ink-800">Stage Duration — Expected vs Threshold</p>
        <table className="w-full text-[13px]">
          <thead className="text-left text-[11.5px] font-semibold uppercase tracking-wide text-ink-500">
            <tr><th className="py-1.5">Stage</th><th className="py-1.5">Threshold</th><th className="py-1.5">Currently Waiting</th><th className="py-1.5">Delayed / Critical</th></tr>
          </thead>
          <tbody>
            {(data ?? []).map((s) => (
              <tr key={s.stage} className="border-t border-ink-100">
                <td className="py-1.5 font-medium text-ink-800">{STAGE_LABELS[s.stage] ?? s.stage}</td>
                <td className="py-1.5 tnum text-ink-600">{s.threshold_minutes} min</td>
                <td className="py-1.5 tnum text-ink-600">{s.total}</td>
                <td className="py-1.5 tnum text-rose-600">{s.delayed + s.critical}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
