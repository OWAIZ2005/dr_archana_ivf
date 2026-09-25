'use client';

import React, { useState } from 'react';
import { useApp } from '@/lib/store';
import { ROLE_MATRIX, USERS, type Role } from '@/lib/data';
import { cn } from '@/lib/utils';
import { Card, CardHeader, Badge, Button, SectionTitle, Avatar, InfoNote } from '@/components/ui/primitives';
import { ShieldCheck, Check, X, Lock, Users2, Info } from 'lucide-react';

const ROLES: Role[] = ['doctor', 'receptionist', 'embryologist', 'management', 'pharmacist', 'prescription'];

export function Access() {
  const { role: currentRole, user: currentUser, toast } = useApp();
  const [view, setView] = useState<Role>(currentRole ?? 'doctor');
  const matrix = ROLE_MATRIX[view];
  const user = USERS[view];

  return (
    <div className="screen-enter mx-auto max-w-[1200px] space-y-5 p-4 sm:p-6 lg:p-8">
      <SectionTitle
        eyebrow="Security"
        title="Role-Based Access Control"
        description="Every staff member sees only the modules, records and actions their role requires."
      />

      <InfoNote tone="brand" icon={<ShieldCheck className="h-4 w-4" />}>
        You are currently signed in as{' '}
        <span className="font-semibold">{currentUser?.title ?? USERS[currentRole ?? 'doctor'].title}</span>.
        Sign out and select a different demo account on the login screen to experience how the
        interface adapts.
      </InfoNote>

      {/* ============ ROLE SWITCHER ============ */}
      <div className="stagger grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4">
        {ROLES.map((r, i) => {
          const u = USERS[r];
          const active = view === r;
          const isCurrent = currentRole === r;
          return (
            <button
              key={r}
              onClick={() => setView(r)}
              style={{ ['--i' as string]: i }}
              className={cn(
                'lift rounded-2xl border p-4 text-left transition-all',
                active ? 'border-brand-400 bg-brand-50/50 shadow-lift ring-1 ring-brand-500/15' : 'border-ink-200/70 bg-white hover:border-ink-300'
              )}
            >
              <div className="flex items-start justify-between">
                <Avatar initials={u.initials} size="md" gradient={u.accent} />
                {isCurrent && (
                  <Badge tone="active" size="sm">
                    You
                  </Badge>
                )}
              </div>
              <p className="mt-3 text-[14.5px] font-semibold text-ink-900">{u.title}</p>
              <p className="mt-0.5 text-[12.5px] text-ink-500">{u.name}</p>
              <div className="mt-2.5 flex items-center gap-3 text-[12px]">
                <span className="flex items-center gap-1 text-brand-700">
                  <Check className="h-3 w-3" /> {ROLE_MATRIX[r].allowed.length} allowed
                </span>
                <span className="flex items-center gap-1 text-ink-400">
                  <Lock className="h-3 w-3" /> {ROLE_MATRIX[r].restricted.length} restricted
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* ============ PERMISSION DETAIL ============ */}
      <Card>
        <CardHeader
          icon={<Users2 className="h-4 w-4" />}
          title={`${user.title} — Permission Set`}
          subtitle={matrix.summary}
          action={
            <Button
              size="sm"
              onClick={() => toast({ title: 'Permissions updated', body: `${user.title} permission set saved and audited.`, tone: 'success' })}
            >
              Edit permissions
            </Button>
          }
        />

        <div className="grid gap-5 px-5 pb-5 lg:grid-cols-2">
          {/* allowed */}
          <div>
            <div className="mb-2.5 flex items-center gap-2">
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-brand-600">
                <Check className="h-3 w-3 text-white" strokeWidth={3.5} />
              </div>
              <p className="text-[13px] font-semibold uppercase tracking-[0.08em] text-brand-700">
                Allowed ({matrix.allowed.length})
              </p>
            </div>
            <div className="stagger space-y-1.5">
              {matrix.allowed.map((a, i) => (
                <div
                  key={a}
                  style={{ ['--i' as string]: i }}
                  className="flex items-center gap-2.5 rounded-lg border border-brand-200/60 bg-brand-50/40 px-3 py-2.5"
                >
                  <Check className="h-3.5 w-3.5 shrink-0 text-brand-600" strokeWidth={3} />
                  <span className="text-[13.5px] font-medium text-brand-900">{a}</span>
                </div>
              ))}
            </div>
          </div>

          {/* restricted */}
          <div>
            <div className="mb-2.5 flex items-center gap-2">
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-ink-300">
                <X className="h-3 w-3 text-white" strokeWidth={3.5} />
              </div>
              <p className="text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-500">
                Restricted ({matrix.restricted.length})
              </p>
            </div>
            <div className="stagger space-y-1.5">
              {matrix.restricted.map((r, i) => (
                <div
                  key={r}
                  style={{ ['--i' as string]: i }}
                  className="flex items-center gap-2.5 rounded-lg border border-ink-200/60 bg-ink-50/60 px-3 py-2.5"
                >
                  <Lock className="h-3.5 w-3.5 shrink-0 text-ink-400" />
                  <span className="text-[13.5px] text-ink-500">{r}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t border-ink-100 p-5">
          <InfoNote tone="neutral" icon={<Info className="h-4 w-4" />}>
            Permissions are enforced at the API layer as well as the interface. Every access attempt —
            successful or denied — is written to the audit trail with the user, timestamp and IP address.
          </InfoNote>
        </div>
      </Card>

      {/* ============ MATRIX GRID ============ */}
      <Card>
        <CardHeader title="Module Access Matrix" subtitle="At-a-glance comparison across all four roles" />
        <div className="overflow-x-auto">
          <div className="min-w-[720px]">
            <div className="grid grid-cols-[2fr_repeat(4,1fr)] gap-4 border-y border-ink-200/70 bg-ink-50/60 px-5 py-2.5">
              <span className="text-[12px] font-semibold uppercase tracking-[0.09em] text-ink-400">
                Module
              </span>
              {ROLES.map((r) => (
                <span key={r} className="text-center text-[12px] font-semibold uppercase tracking-[0.09em] text-ink-400">
                  {USERS[r].title.split(' ')[0]}
                </span>
              ))}
            </div>

            {[
              { m: 'Patient Registration', a: ['doctor', 'receptionist'] },
              { m: 'Clinical Notes & Plans', a: ['doctor'] },
              { m: 'Follicle Monitoring', a: ['doctor', 'embryologist'] },
              { m: 'Embryology & Grading', a: ['doctor', 'embryologist'] },
              { m: 'Cryostorage', a: ['doctor', 'embryologist'] },
              { m: 'Billing & Payments', a: ['doctor', 'receptionist', 'management'] },
              { m: 'Revenue Reports', a: ['management'] },
              { m: 'Audit Log', a: ['doctor', 'management'] },
            ].map((row, i) => (
              <div
                key={row.m}
                style={{ ['--i' as string]: i }}
                className="grid grid-cols-[2fr_repeat(4,1fr)] items-center gap-4 border-b border-ink-100 px-5 py-3 last:border-0 hover:bg-ink-50/60"
              >
                <span className="text-[13.5px] font-medium text-ink-800">{row.m}</span>
                {ROLES.map((r) => {
                  const ok = row.a.includes(r);
                  return (
                    <div key={r} className="flex justify-center">
                      <div
                        className={cn(
                          'flex h-6 w-6 items-center justify-center rounded-full',
                          ok ? 'bg-brand-100' : 'bg-ink-100'
                        )}
                      >
                        {ok ? (
                          <Check className="h-3.5 w-3.5 text-brand-700" strokeWidth={3} />
                        ) : (
                          <X className="h-3.5 w-3.5 text-ink-300" strokeWidth={3} />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
}
