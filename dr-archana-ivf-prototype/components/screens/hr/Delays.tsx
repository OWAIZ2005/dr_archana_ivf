'use client';

import React, { useState } from 'react';
import { Card, Badge, Button, Select, Modal, Skeleton } from '@/components/ui/primitives';
import { Download } from 'lucide-react';
import { useDelays, useDelayReasons, useSetDelayReason, downloadHrReport, type PatientDelayOut } from '@/lib/api/hr';
import { useApp } from '@/lib/store';

function ReasonModal({ delay, onClose }: { delay: PatientDelayOut; onClose: () => void }) {
  const { data: reasons } = useDelayReasons();
  const setReason = useSetDelayReason();
  const { toast } = useApp();
  const [selected, setSelected] = useState(delay.delay_reason ?? '');

  const submit = () => {
    if (!delay.event_id || !selected) return;
    setReason.mutate({ eventId: delay.event_id, reason: selected }, {
      onSuccess: () => { toast({ title: 'Delay reason recorded', tone: 'success' }); onClose(); },
    });
  };

  return (
    <Modal open onClose={onClose} title={`${delay.patient_name} — ${delay.stage.replace('_', ' ')}`} subtitle="Record the reason for this delay"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button variant="primary" loading={setReason.isPending} disabled={!selected} onClick={submit}>Save Reason</Button></>}
    >
      <Select label="Reason" value={selected} onChange={(e) => setSelected(e.target.value)}>
        <option value="">Select a reason…</option>
        {(reasons ?? []).map((r) => <option key={r} value={r}>{r}</option>)}
      </Select>
    </Modal>
  );
}

export function HrDelays() {
  const [onlyDelayed, setOnlyDelayed] = useState(true);
  const { data, isLoading } = useDelays(onlyDelayed);
  const [selected, setSelected] = useState<PatientDelayOut | null>(null);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="tracking-display text-[20px] font-semibold text-ink-900">Delay Detection & Escalation</h1>
          <p className="mt-1 text-[13px] text-ink-500">Patients whose current stage has exceeded (or is approaching) its configured threshold.</p>
        </div>
        <Button variant="secondary" icon={<Download className="h-4 w-4" />} onClick={() => downloadHrReport('/hr/reports/delays.csv', 'delay_report.csv')}>Export</Button>
      </div>

      <label className="flex w-fit items-center gap-2 text-[13px] text-ink-600">
        <input type="checkbox" checked={onlyDelayed} onChange={(e) => setOnlyDelayed(e.target.checked)} className="h-4 w-4 rounded border-ink-300" />
        Show only delayed/critical (hide normal + approaching)
      </label>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20 rounded-2xl" />)}</div>
      ) : !data?.length ? (
        <Card className="p-8 text-center text-[13.5px] text-ink-400">No delayed patients right now.</Card>
      ) : (
        <div className="space-y-3">
          {data.map((d) => (
            <Card key={`${d.appointment_id}-${d.stage}`} className={`p-4 ${d.severity === 'critical' ? 'border-rose-300 bg-rose-50/40' : d.severity === 'delayed' ? 'border-rose-200' : ''}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-ink-900">{d.patient_name}</p>
                    <Badge size="sm" tone={d.severity === 'critical' ? 'critical' : d.severity === 'delayed' ? 'critical' : d.severity === 'warning' ? 'attention' : 'active'}>
                      {d.severity === 'critical' ? '🔴 Critical Delay' : d.severity === 'delayed' ? '⚠ Delayed' : d.severity === 'warning' ? 'Approaching' : 'Normal'}
                    </Badge>
                  </div>
                  <p className="mt-1 text-[13px] text-ink-500">
                    Stage: <strong className="text-ink-700">{d.stage.replace('_', ' ')}</strong> · Doctor: {d.doctor_name} · Started {new Date(d.started_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  </p>
                  <p className="mt-1 text-[13px] text-ink-600">
                    Expected {d.threshold_minutes} min · Actual {d.actual_minutes} min · <span className="font-semibold text-rose-600">Delay {d.delay_minutes} min</span>
                  </p>
                  {d.delay_reason && <p className="mt-1 text-[12.5px] italic text-ink-500">Reason: {d.delay_reason}</p>}
                </div>
                <Button size="sm" variant="secondary" onClick={() => setSelected(d)}>{d.delay_reason ? 'Update Reason' : 'Add Reason'}</Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {selected && <ReasonModal delay={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
