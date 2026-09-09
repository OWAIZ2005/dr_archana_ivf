'use client';

import React, { useMemo, useState } from 'react';
import { AlarmClock, BellRing, CheckCircle2, Clock, Syringe, Utensils } from 'lucide-react';

import { Badge, Button, Card, CardHeader, Field, InfoNote, Input } from '@/components/ui/primitives';
import { useApp } from '@/lib/store';
import { ApiError } from '@/lib/api/client';
import {
  useAcknowledgeTrigger,
  useConfirmTrigger,
  useCreateNpo,
  useCreateTrigger,
  useCycleNpo,
  useCycleTrigger,
  useNpoNotifications,
  useRescheduleTrigger,
  useTriggerNotifications,
  type EventMessageOut,
  type TriggerStatus,
} from '@/lib/api/ivf';

const TRIGGER_TONE: Record<TriggerStatus, 'scheduled' | 'completed' | 'critical'> = {
  planned: 'scheduled',
  confirmed: 'completed',
  overdue: 'critical',
};
const TRIGGER_LABEL: Record<TriggerStatus, string> = {
  planned: 'Planned',
  confirmed: 'Confirmed',
  overdue: 'Overdue',
};

/** <input type="datetime-local"> value <-> ISO. The input is naive local time. */
function toLocalInput(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function fromLocalInput(v: string): string {
  return new Date(v).toISOString();
}
function fmt(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—';
}

function NotificationRow({ m }: { m: EventMessageOut }) {
  return (
    <div className="flex items-start justify-between gap-3 border-t border-ink-100 py-2 text-[12.5px] first:border-t-0">
      <div className="min-w-0">
        <p className="text-ink-700">{m.body}</p>
        <p className="mt-0.5 text-ink-400">
          {m.event_type === 'trigger_due' ? `Trigger reminder #${m.attempt}` : 'NPO notification'} · {fmt(m.created_at)}
          {m.provider === 'console' && ' · demo (not delivered)'}
        </p>
      </div>
      <Badge tone={m.status === 'sent' ? 'completed' : 'neutral'} size="sm">
        {m.status}
      </Badge>
    </div>
  );
}

export function CycleTriggerNpoPanel({ cycleId }: { cycleId: string }) {
  const { toast } = useApp();

  const triggerQ = useCycleTrigger(cycleId);
  const npoQ = useCycleNpo(cycleId);
  const trigger = triggerQ.data ?? null;
  const npo = npoQ.data ?? null;

  const triggerNotifs = useTriggerNotifications(trigger?.id ?? null);
  const npoNotifs = useNpoNotifications(npo?.id ?? null);
  const history = useMemo<EventMessageOut[]>(
    () =>
      [...(triggerNotifs.data ?? []), ...(npoNotifs.data ?? [])].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      ),
    [triggerNotifs.data, npoNotifs.data],
  );

  const createTrigger = useCreateTrigger();
  const reschedule = useRescheduleTrigger();
  const acknowledge = useAcknowledgeTrigger();
  const confirm = useConfirmTrigger();
  const createNpo = useCreateNpo();

  const [medicine, setMedicine] = useState('');
  const [plannedAt, setPlannedAt] = useState('');
  const [editing, setEditing] = useState(false);
  const [editAt, setEditAt] = useState('');
  const [npoReason, setNpoReason] = useState('');
  const [npoStart, setNpoStart] = useState('');

  const err = (e: unknown) =>
    toast({ title: 'Action failed', body: e instanceof ApiError ? e.message : 'Please try again.', tone: 'error' });

  return (
    <Card>
      <CardHeader
        icon={<Syringe className="h-4 w-4" />}
        title="Trigger & NPO"
        subtitle="Hospital-side events and their internal staff notifications for this cycle."
      />

      <div className="space-y-5 px-5 pb-5">
        {/* ---------------- Trigger injection ---------------- */}
        <section>
          <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink-700">
            <AlarmClock className="h-3.5 w-3.5" /> Trigger Injection
          </div>

          {!trigger && (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <Input
                label="Medicine"
                value={medicine}
                onChange={(e) => setMedicine(e.target.value)}
                placeholder="Inj. Ovitrelle 250mcg"
              />
              <Input
                label="Planned time"
                type="datetime-local"
                value={plannedAt}
                onChange={(e) => setPlannedAt(e.target.value)}
              />
              <Button
                variant="primary"
                loading={createTrigger.isPending}
                disabled={!medicine || !plannedAt}
                onClick={() =>
                  createTrigger.mutate(
                    { cycleId, medicine, planned_at: fromLocalInput(plannedAt) },
                    { onError: err, onSuccess: () => { setMedicine(''); setPlannedAt(''); } },
                  )
                }
              >
                Plan Trigger
              </Button>
            </div>
          )}

          {trigger && (
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label="Medicine" value={trigger.medicine} />
                <Field label="Planned time" value={fmt(trigger.planned_at)} />
                <div>
                  <p className="text-[11.5px] font-medium uppercase tracking-wide text-ink-400">Status</p>
                  <Badge tone={TRIGGER_TONE[trigger.status]} size="sm" className="mt-1">
                    {TRIGGER_LABEL[trigger.status]}
                  </Badge>
                </div>
                <Field label="Reminders sent" value={String(trigger.reminders_sent)} />
                <Field label="Confirmed" value={fmt(trigger.confirmed_at)} />
                <Field label="Acknowledged" value={fmt(trigger.acknowledged_at)} />
              </div>

              <div className="flex flex-wrap items-end gap-2">
                {trigger.status !== 'confirmed' && !editing && (
                  <Button size="sm" variant="ghost" icon={<Clock className="h-3.5 w-3.5" />} onClick={() => { setEditing(true); setEditAt(toLocalInput(trigger.planned_at)); }}>
                    Edit planned time
                  </Button>
                )}
                {editing && (
                  <>
                    <Input label="New planned time" type="datetime-local" value={editAt} onChange={(e) => setEditAt(e.target.value)} />
                    <Button
                      size="sm"
                      variant="primary"
                      loading={reschedule.isPending}
                      onClick={() =>
                        reschedule.mutate(
                          { triggerId: trigger.id, cycleId, planned_at: fromLocalInput(editAt) },
                          { onError: err, onSuccess: () => { setEditing(false); toast({ title: 'Trigger rescheduled', tone: 'success' }); } },
                        )
                      }
                    >
                      Save
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
                  </>
                )}
                {!editing && trigger.status !== 'confirmed' && !trigger.acknowledged_at && (
                  <Button
                    size="sm"
                    icon={<BellRing className="h-3.5 w-3.5" />}
                    loading={acknowledge.isPending}
                    onClick={() => acknowledge.mutate({ triggerId: trigger.id, cycleId }, { onError: err })}
                  >
                    Acknowledge
                  </Button>
                )}
                {!editing && trigger.status !== 'confirmed' && (
                  <Button
                    size="sm"
                    variant="primary"
                    icon={<CheckCircle2 className="h-3.5 w-3.5" />}
                    loading={confirm.isPending}
                    onClick={() => confirm.mutate({ triggerId: trigger.id, cycleId }, { onError: err, onSuccess: () => toast({ title: 'Trigger confirmed', tone: 'success' }) })}
                  >
                    Confirm Trigger
                  </Button>
                )}
              </div>
            </div>
          )}
        </section>

        {/* ---------------- NPO ---------------- */}
        <section>
          <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink-700">
            <Utensils className="h-3.5 w-3.5" /> NPO (nil by mouth)
          </div>

          {!npo && (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <Input label="Reason" value={npoReason} onChange={(e) => setNpoReason(e.target.value)} placeholder="Oocyte retrieval under sedation" />
              <Input label="NPO start time" type="datetime-local" value={npoStart} onChange={(e) => setNpoStart(e.target.value)} />
              <Button
                variant="primary"
                loading={createNpo.isPending}
                disabled={!npoReason || !npoStart}
                onClick={() =>
                  createNpo.mutate(
                    { cycleId, reason: npoReason, start_at: fromLocalInput(npoStart) },
                    { onError: err, onSuccess: () => { setNpoReason(''); setNpoStart(''); } },
                  )
                }
              >
                Set NPO
              </Button>
            </div>
          )}

          {npo && (
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Start time" value={fmt(npo.start_at)} />
              <Field label="Reason" value={npo.reason} />
              <div>
                <p className="text-[11.5px] font-medium uppercase tracking-wide text-ink-400">Status</p>
                <Badge tone={npo.notified_at ? 'active' : 'scheduled'} size="sm" className="mt-1">
                  {npo.notified_at ? 'Started' : 'Pending'}
                </Badge>
              </div>
            </div>
          )}
        </section>

        {/* ---------------- Notification history ---------------- */}
        <section>
          <div className="mb-1 flex items-center gap-2 text-[13px] font-semibold text-ink-700">
            <BellRing className="h-3.5 w-3.5" /> Reminder / Notification History
          </div>
          {history.length === 0 ? (
            <InfoNote>No notifications generated yet for this cycle's trigger or NPO.</InfoNote>
          ) : (
            <div>
              {history.map((m) => (
                <NotificationRow key={m.id} m={m} />
              ))}
            </div>
          )}
        </section>
      </div>
    </Card>
  );
}
