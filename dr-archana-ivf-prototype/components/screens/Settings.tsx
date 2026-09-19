'use client';

import React, { useState } from 'react';
import { useApp } from '@/lib/store';
import { usePreferences, preferenceClasses } from '@/lib/preferences';
import type { TextScale, Density, SidebarSections } from '@/lib/preferences';
import { navForRole, SCREEN_TITLES } from '@/components/layout/nav';
import { cn } from '@/lib/utils';
import { isPasskeySupported } from '@/lib/webauthn';
import { usePasskeys, useRegisterPasskey, useDeletePasskey } from '@/lib/api/passkeys';
import { ApiError } from '@/lib/api/client';
import {
  Card,
  CardHeader,
  Badge,
  Button,
  SectionTitle,
  Select,
  Switch,
  SegmentedControl,
  SettingRow,
  InfoNote,
  Input,
  Modal,
} from '@/components/ui/primitives';
import {
  Type,
  Rows,
  Contrast,
  Zap,
  PanelLeft,
  Clock,
  LogIn,
  RotateCcw,
  Eye,
  Monitor,
  ScanFace,
  Plus,
  Trash2,
} from 'lucide-react';

/** Registered passkeys for the signed-in account — self-service register
 *  and revoke, same "no extra permission code" reasoning as the backend
 *  (backend/app/webauthn/router.py): this only ever touches your own
 *  credentials, never anyone else's. */
function AddPasskeyModal({ onClose }: { onClose: () => void }) {
  const { toast } = useApp();
  const register = useRegisterPasskey();
  const [label, setLabel] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = () => {
    setError(null);
    register.mutate(label.trim() || null, {
      onSuccess: () => {
        toast({ title: 'Passkey added', body: 'You can now sign in here with Face ID or Touch ID.', tone: 'success' });
        onClose();
      },
      onError: (e) => {
        setError(
          e instanceof DOMException && e.name === 'NotAllowedError'
            ? 'Cancelled.'
            : e instanceof ApiError
            ? e.message
            : 'Could not add this passkey.'
        );
      },
    });
  };

  return (
    <Modal
      open onClose={onClose} title="Add a Passkey"
      subtitle="Your device will prompt for Face ID or Touch ID to finish setting this up."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={register.isPending} onClick={submit}>Continue</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Input
          label="Name this device (optional)"
          placeholder="e.g. My iPad, Front Desk iPad"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
        {error && <p className="text-[13px] text-rose-600">{error}</p>}
      </div>
    </Modal>
  );
}

function PasskeysCard() {
  const { toast } = useApp();
  const supported = isPasskeySupported();
  const passkeysQuery = usePasskeys();
  const remove = useDeletePasskey();
  const [addOpen, setAddOpen] = useState(false);

  return (
    <Card className="overflow-hidden">
      {addOpen && <AddPasskeyModal onClose={() => setAddOpen(false)} />}
      <CardHeader
        icon={<ScanFace className="h-4 w-4" />}
        title="Passkeys"
        subtitle="Sign in with Face ID or Touch ID instead of typing your password"
        action={
          supported && (
            <Button size="sm" variant="secondary" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => setAddOpen(true)}>
              Add a passkey
            </Button>
          )
        }
      />
      <div className="px-5 pb-5">
        {!supported ? (
          <InfoNote tone="neutral">This browser or device doesn't support passkeys — sign in with your password here instead.</InfoNote>
        ) : passkeysQuery.isLoading ? (
          <p className="text-[13.5px] text-ink-500">Loading…</p>
        ) : (passkeysQuery.data ?? []).length === 0 ? (
          <InfoNote tone="neutral">
            No passkeys yet. Add one on a device you use regularly — a shared front-desk iPad can't reliably
            recognise more than one person's face, so this works best on your own device.
          </InfoNote>
        ) : (
          <div className="space-y-2">
            {(passkeysQuery.data ?? []).map((p) => (
              <div key={p.id} className="flex items-center justify-between gap-3 rounded-xl border border-ink-100 p-3">
                <div className="min-w-0">
                  <p className="truncate text-[13.5px] font-medium text-ink-900">{p.device_label || 'Unnamed device'}</p>
                  <p className="text-[12px] text-ink-500">
                    Added {new Date(p.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                    {p.last_used_at && ` · Last used ${new Date(p.last_used_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}`}
                  </p>
                </div>
                <button
                  onClick={() =>
                    remove.mutate(p.id, {
                      onSuccess: () => toast({ title: 'Passkey removed', tone: 'success' }),
                      onError: () => toast({ title: 'Could not remove this passkey', tone: 'error' }),
                    })
                  }
                  aria-label={`Remove passkey: ${p.device_label || 'Unnamed device'}`}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ink-400 hover:bg-rose-50 hover:text-rose-600"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

/** A miniature of the real interface that re-renders under whatever the
 *  staff member has just selected, so the effect of a setting is visible
 *  before they go back to a clinical screen and discover it. */
function LivePreview() {
  const { prefs } = usePreferences();
  return (
    <div className={cn('rounded-xl border border-ink-200 bg-ink-50/60 p-4', preferenceClasses(prefs))}>
      <div className="rounded-lg border border-ink-200 bg-white">
        <div className="flex items-center justify-between border-b border-ink-100 px-4 py-3">
          <div>
            <p className="text-[14.5px] font-semibold text-ink-900">Priya Raman</p>
            <p className="text-[12.5px] text-ink-500">DAIVF-2026-00428 · Stimulation Day 8</p>
          </div>
          <Badge tone="active" size="sm">
            Active cycle
          </Badge>
        </div>
        {[
          { l: 'Estradiol (E2)', v: '1,240 pg/mL', t: 'completed' as const, s: 'Normal' },
          { l: 'LH', v: '4.2 mIU/mL', t: 'attention' as const, s: 'Review' },
        ].map((r) => (
          <div key={r.l} className="flex items-center justify-between border-b border-ink-100 px-4 py-3 last:border-0">
            <span className="text-[14px] text-ink-800">{r.l}</span>
            <div className="flex items-center gap-3">
              <span className="tnum text-[14px] font-semibold text-ink-900">{r.v}</span>
              <Badge tone={r.t} size="sm">
                {r.s}
              </Badge>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2.5 text-[12px] text-ink-400">
        This preview uses your current settings. Nothing here is real patient data.
      </p>
    </div>
  );
}

export function Settings() {
  const { role, toast } = useApp();
  const { prefs, setPref, reset } = usePreferences();

  // Only offer landing screens this role can actually open — otherwise a
  // staff member could pin themselves to a permission-denied screen.
  const startScreenOptions = role ? navForRole(role) : [];

  return (
    <div className="screen-enter mx-auto max-w-[1000px] space-y-5 p-4 sm:p-6 lg:p-8">
      <SectionTitle
        eyebrow="Preferences"
        title="User Interface"
        description="Change how this system looks and behaves for you. These settings apply to your account on this device only — they do not affect your colleagues or any clinical record."
        action={
          <Button
            icon={<RotateCcw className="h-4 w-4" />}
            onClick={() => {
              reset();
              toast({ title: 'Settings reset', body: 'Interface preferences are back to their defaults.', tone: 'info' });
            }}
          >
            Reset to defaults
          </Button>
        }
      />

      <div className="grid gap-5 lg:grid-cols-[1fr_340px]">
        <div className="space-y-5">
          {/* ---------------- READABILITY ---------------- */}
          <Card className="overflow-hidden">
            <CardHeader
              icon={<Eye className="h-4 w-4" />}
              title="Readability"
              subtitle="Make text and content easier to read"
            />
            <SettingRow
              icon={<Type className="h-4 w-4" />}
              title="Text size"
              description="Increases the size of everything on screen. Useful on tablets and larger displays."
              control={
                <SegmentedControl<TextScale>
                  label="Text size"
                  value={prefs.textScale}
                  onChange={(v) => setPref('textScale', v)}
                  options={[
                    { id: 'standard', label: 'Standard' },
                    { id: 'large', label: 'Large' },
                    { id: 'xl', label: 'Extra large' },
                  ]}
                />
              }
            />
            <SettingRow
              icon={<Rows className="h-4 w-4" />}
              title="Display density"
              description="Compact fits more rows on screen for scanning long lists. Comfortable leaves more breathing room."
              control={
                <SegmentedControl<Density>
                  label="Display density"
                  value={prefs.density}
                  onChange={(v) => setPref('density', v)}
                  options={[
                    { id: 'comfortable', label: 'Comfortable' },
                    { id: 'compact', label: 'Compact' },
                  ]}
                />
              }
            />
            <SettingRow
              icon={<Contrast className="h-4 w-4" />}
              title="High contrast"
              description="Darkens text and strengthens borders for bright clinic lighting or washed-out screens."
              control={
                <Switch
                  label="High contrast"
                  checked={prefs.highContrast}
                  onChange={(v) => setPref('highContrast', v)}
                />
              }
            />
            <SettingRow
              icon={<Zap className="h-4 w-4" />}
              title="Reduce motion"
              description="Turns off sliding and fading animations. Screens change instantly instead."
              control={
                <Switch
                  label="Reduce motion"
                  checked={prefs.reduceMotion}
                  onChange={(v) => setPref('reduceMotion', v)}
                />
              }
            />
          </Card>

          {/* ---------------- LAYOUT ---------------- */}
          <Card className="overflow-hidden">
            <CardHeader
              icon={<Monitor className="h-4 w-4" />}
              title="Layout & navigation"
              subtitle="Control what the menu and top bar show"
            />
            <SettingRow
              icon={<PanelLeft className="h-4 w-4" />}
              title="Menu sections"
              description="Keep every section of the left menu open, or show only the section you are currently working in."
              control={
                <SegmentedControl<SidebarSections>
                  label="Menu sections"
                  value={prefs.sidebarSections}
                  onChange={(v) => setPref('sidebarSections', v)}
                  options={[
                    { id: 'active-only', label: 'Current only' },
                    { id: 'all-open', label: 'All open' },
                  ]}
                />
              }
            />
            <SettingRow
              icon={<Clock className="h-4 w-4" />}
              title="Show date and time"
              description="Adds the date and a live clock to the top bar. Off by default to keep the bar uncluttered."
              control={
                <Switch
                  label="Show date and time"
                  checked={prefs.showClock}
                  onChange={(v) => setPref('showClock', v)}
                />
              }
            />
            <SettingRow
              icon={<LogIn className="h-4 w-4" />}
              title="Screen after sign-in"
              description="Choose which screen opens when you sign in, instead of the default for your role."
              control={
                <div className="w-full sm:w-[220px]">
                  <Select
                    aria-label="Screen after sign-in"
                    value={prefs.startScreen}
                    onChange={(e) => setPref('startScreen', e.target.value)}
                  >
                    <option value="role-default">Default for my role</option>
                    {startScreenOptions.map((n) => (
                      <option key={n.id} value={n.id}>
                        {SCREEN_TITLES[n.id]}
                      </option>
                    ))}
                  </Select>
                </div>
              }
            />
          </Card>

          {/* ---------------- SIGN-IN & SECURITY ---------------- */}
          <PasskeysCard />

          <InfoNote tone="brand" icon={<Monitor className="h-4 w-4" />}>
            These preferences are stored in this browser. Signing in on a different computer or
            tablet starts from the defaults again, and clearing browser data resets them.
          </InfoNote>
        </div>

        {/* ---------------- PREVIEW ---------------- */}
        <div className="lg:sticky lg:top-6 lg:self-start">
          <Card className="p-4">
            <p className="mb-3 text-[12px] font-semibold uppercase tracking-[0.09em] text-ink-400">
              Live preview
            </p>
            <LivePreview />
          </Card>
        </div>
      </div>
    </div>
  );
}
