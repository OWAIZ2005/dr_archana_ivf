'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useApp } from '@/lib/store';
import { SYSTEM_SETTINGS_GROUPS, PROCEDURE_CHARGES, TREATMENT_PACKAGES, USERS } from '@/lib/data';
import { cn, formatINR } from '@/lib/utils';
import { Card, CardHeader, Badge, Button, SectionTitle, Tabs, InfoNote, ActionRow, Switch } from '@/components/ui/primitives';
import { useProcedureCharges, usePackages } from '@/lib/api/administration';
import { useRoles, usePermissionCatalogue, useUpdateRolePermissions } from '@/lib/api/roles';
import { ApiError } from '@/lib/api/client';
import {
  Users,
  ClipboardList,
  Receipt,
  Bell,
  ShieldCheck,
  Settings as SettingsIcon,
  ChevronRight,
  Package,
  Pencil,
  Lock,
} from 'lucide-react';

const ICONS: Record<string, any> = {
  users: Users,
  clipboard: ClipboardList,
  receipt: Receipt,
  bell: Bell,
  shield: ShieldCheck,
  settings: SettingsIcon,
};

function RolesPermissionsPanel() {
  const { toast, can } = useApp();
  const rolesQuery = useRoles();
  const catalogueQuery = usePermissionCatalogue();
  const updatePermissions = useUpdateRolePermissions();
  const roles = rolesQuery.data ?? [];
  const catalogue = catalogueQuery.data ?? [];
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [pendingCodes, setPendingCodes] = useState<Set<string> | null>(null);

  const selectedRole = roles.find((r) => r.id === selectedRoleId) ?? roles[0] ?? null;

  // Reset the working set of checked permissions whenever the selected
  // role changes (or its data arrives) — editing is against a local
  // draft so a mis-click doesn't PUT until "Save changes" is pressed.
  useEffect(() => {
    if (selectedRole) setPendingCodes(new Set(selectedRole.permissions.map((p) => p.code)));
  }, [selectedRole?.id]);

  if (!can('admin.manage_roles')) {
    return (
      <div className="p-5">
        <InfoNote tone="amber" icon={<Lock className="h-4 w-4" />}>
          Your account does not have the "Manage roles" permission, so this panel is read-only for you.
        </InfoNote>
      </div>
    );
  }

  if (rolesQuery.isLoading || catalogueQuery.isLoading) {
    return <p className="p-5 text-[13.5px] text-ink-500">Loading roles…</p>;
  }

  if (rolesQuery.isError || catalogueQuery.isError || roles.length === 0) {
    return (
      <div className="p-5">
        <InfoNote tone="amber" icon={<Lock className="h-4 w-4" />}>
          Could not load roles from the server. Try again in a moment.
        </InfoNote>
      </div>
    );
  }

  const modules = Array.from(new Set(catalogue.map((p) => p.module))).sort();

  const isAdministrator = selectedRole?.code === 'administrator';
  const dirty =
    !!selectedRole &&
    !!pendingCodes &&
    (pendingCodes.size !== selectedRole.permissions.length ||
      selectedRole.permissions.some((p) => !pendingCodes.has(p.code)));

  const togglePermission = (permissionId: string, code: string) => {
    setPendingCodes((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
    void permissionId; // kept for clarity at call sites; codes drive the Set
  };

  const handleSave = () => {
    if (!selectedRole || !pendingCodes) return;
    const permissionIds = catalogue.filter((p) => pendingCodes.has(p.code)).map((p) => p.id);
    updatePermissions.mutate(
      { roleId: selectedRole.id, permissionIds },
      {
        onSuccess: () => toast({ title: 'Permissions saved', body: `${selectedRole.name}'s access has been updated.`, tone: 'success' }),
        onError: (e) =>
          toast({
            title: 'Could not save permissions',
            body: e instanceof ApiError ? e.message : undefined,
            tone: 'error',
          }),
      }
    );
  };

  return (
    <div className="animate-fade-up grid gap-4 p-5 lg:grid-cols-[240px_1fr]">
      <div className="space-y-1.5">
        {roles.map((r) => (
          <button
            key={r.id}
            onClick={() => setSelectedRoleId(r.id)}
            className={cn(
              'flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2.5 text-left text-[13.5px] font-medium transition-colors',
              (selectedRole?.id ?? roles[0]?.id) === r.id
                ? 'bg-brand-50 text-brand-800 ring-1 ring-inset ring-brand-600/15'
                : 'text-ink-600 hover:bg-ink-100'
            )}
          >
            <span>{r.name}</span>
            <Badge tone="neutral" size="sm">
              {r.permissions.length}
            </Badge>
          </button>
        ))}
      </div>

      {selectedRole && pendingCodes && (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[15px] font-semibold text-ink-900">{selectedRole.name}</p>
              <p className="text-[12.5px] text-ink-500">
                {isAdministrator
                  ? 'The Administrator role always has every permission and cannot be edited.'
                  : `${pendingCodes.size} of ${catalogue.length} permissions granted`}
              </p>
            </div>
            <Button
              variant="primary"
              disabled={isAdministrator || !dirty}
              loading={updatePermissions.isPending}
              onClick={handleSave}
            >
              Save changes
            </Button>
          </div>

          <div className="max-h-[520px] space-y-4 overflow-y-auto pr-1">
            {modules.map((module) => {
              const perms = catalogue.filter((p) => p.module === module);
              return (
                <div key={module}>
                  <p className="mb-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-ink-400">{module}</p>
                  <div className="space-y-1 rounded-xl border border-ink-200/70">
                    {perms.map((p) => (
                      <div
                        key={p.id}
                        className="flex items-center justify-between gap-3 border-b border-ink-100 px-3.5 py-2.5 last:border-b-0"
                      >
                        <div className="min-w-0">
                          <p className="flex items-center gap-1.5 text-[13px] font-medium text-ink-800">
                            {p.description ?? p.code}
                            {p.is_critical && (
                              <Badge tone="attention" size="sm" dot={false}>
                                Critical
                              </Badge>
                            )}
                          </p>
                          <p className="tnum text-[11.5px] text-ink-400">{p.code}</p>
                        </div>
                        <Switch
                          label={`Grant ${p.code} to ${selectedRole.name}`}
                          checked={pendingCodes.has(p.code)}
                          disabled={isAdministrator}
                          onChange={() => togglePermission(p.id, p.code)}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export function Administration() {
  const { toast } = useApp();
  const [tab, setTab] = useState('settings');

  const chargesQuery = useProcedureCharges();
  const packagesQuery = usePackages();
  const hasRealCharges = (chargesQuery.data ?? []).length > 0;
  const hasRealPackages = (packagesQuery.data ?? []).length > 0;

  const charges = useMemo(
    () =>
      hasRealCharges
        ? (chargesQuery.data ?? []).map((c) => ({ procedure: c.procedure_name, charge: Math.round(c.charge_paise / 100) }))
        : PROCEDURE_CHARGES,
    [hasRealCharges, chargesQuery.data]
  );

  const packages = useMemo(
    () =>
      hasRealPackages
        ? (packagesQuery.data ?? []).map((p) => ({ name: p.name, price: Math.round(p.price_paise / 100), validity: p.validity_description ?? '—', inclusions: null as number | null }))
        : TREATMENT_PACKAGES.map((p) => ({ ...p, inclusions: p.inclusions as number | null })),
    [hasRealPackages, packagesQuery.data]
  );

  return (
    <div className="screen-enter mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6 lg:p-8">
      <SectionTitle
        eyebrow="Management"
        title="System Administration"
        description="Master settings for users, roles, doctors, charges, packages and system configuration"
      />

      <InfoNote tone="brand" icon={<ShieldCheck className="h-4 w-4" />}>
        Routine configuration changes — new doctors, updated pricing, new lab tests — are made here
        directly by hospital administrators, without needing a developer.
      </InfoNote>

      <Card className="overflow-hidden">
        <div className="px-4 pt-2">
          <Tabs
            tabs={[
              { id: 'settings', label: 'Settings' },
              { id: 'charges', label: 'Procedure Charges', count: charges.length },
              { id: 'packages', label: 'Treatment Packages', count: packages.length },
              { id: 'users', label: 'Users & Roles', count: Object.keys(USERS).length },
              { id: 'rbac', label: 'Roles & Permissions' },
            ]}
            active={tab}
            onChange={setTab}
          />
        </div>

        {tab === 'settings' && (
          <div className="animate-fade-up stagger grid gap-3.5 p-5 sm:grid-cols-2 xl:grid-cols-3">
            {SYSTEM_SETTINGS_GROUPS.map((g, i) => {
              const Icon = ICONS[g.icon] ?? SettingsIcon;
              return (
                <Card key={g.group} style={{ ['--i' as string]: i }} className="p-4" interactive>
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-600/12">
                    <Icon className="h-[18px] w-[18px]" />
                  </div>
                  <p className="mt-3 text-[14.5px] font-semibold text-ink-900">{g.group}</p>
                  <div className="mt-2 space-y-1">
                    {g.items.map((it) => (
                      <p key={it} className="flex items-center gap-1.5 text-[13px] text-ink-500">
                        <span className="h-1 w-1 shrink-0 rounded-full bg-ink-300" /> {it}
                      </p>
                    ))}
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        {tab === 'charges' && (
          <div className="animate-fade-up p-5">
            <div className="stagger space-y-2">
              {charges.map((c, i) => (
                <div
                  key={c.procedure}
                  style={{ ['--i' as string]: i }}
                  className="flex items-center justify-between gap-4 rounded-xl border border-ink-200/70 px-4 py-3"
                >
                  <span className="text-[14px] font-medium text-ink-800">{c.procedure}</span>
                  <div className="flex items-center gap-3">
                    <span className="tnum text-[14px] font-semibold text-ink-900">{formatINR(c.charge)}</span>
                    <button
                      onClick={() => toast({ title: 'Charge updated', body: `${c.procedure} pricing saved.`, tone: 'success' })}
                      aria-label={`Edit charge for ${c.procedure}`}
                      title="Edit charge"
                      className="flex h-10 w-10 items-center justify-center rounded-lg text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-700"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === 'packages' && (
          <div className="animate-fade-up stagger grid gap-3.5 p-5 sm:grid-cols-2">
            {packages.map((p, i) => (
              <Card key={p.name} style={{ ['--i' as string]: i }} className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-600/12">
                    <Package className="h-[18px] w-[18px]" />
                  </div>
                  {p.inclusions !== null && (
                    <Badge tone="neutral" size="sm">
                      {p.inclusions} inclusions
                    </Badge>
                  )}
                </div>
                <p className="mt-3 text-[14.5px] font-semibold text-ink-900">{p.name}</p>
                <p className="tnum mt-1 text-[22px] font-semibold text-ink-900">{formatINR(p.price)}</p>
                <p className="mt-1 text-[12.5px] text-ink-500">{hasRealPackages ? p.validity : `Valid for ${p.validity}`}</p>
              </Card>
            ))}
          </div>
        )}

        {tab === 'users' && (
          <div className="animate-fade-up stagger space-y-2 p-5">
            {Object.values(USERS).map((u, i) => (
              <ActionRow
                key={u.id}
                label={u.name}
                description={`${u.title} · ${u.department}`}
                icon={<Users className="h-4 w-4" />}
                onClick={() => toast({ title: 'Role editor', body: `Editing permissions for ${u.title}.`, tone: 'info' })}
              />
            ))}
          </div>
        )}

        {tab === 'rbac' && <RolesPermissionsPanel />}
      </Card>
    </div>
  );
}
