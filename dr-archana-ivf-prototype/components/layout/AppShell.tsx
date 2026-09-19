'use client';

import React, { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { useApp } from '@/lib/store';
import { useAuth } from '@/lib/auth';
import { usePreferences, preferenceClasses } from '@/lib/preferences';
import { useHotkey } from '@/lib/hooks';
import { canAccess } from './nav';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { CommandPalette } from './CommandPalette';
import { ToastStack, Button, Card } from '@/components/ui/primitives';

import { Login } from '@/components/screens/Login';
import { Dashboard } from '@/components/screens/Dashboard';
import { Patients } from '@/components/screens/Patients';
import { Workspace } from '@/components/screens/Workspace';
import { Appointments } from '@/components/screens/Appointments';
import { Timeline } from '@/components/screens/Timeline';
import { Monitoring } from '@/components/screens/Monitoring';
import { Plan } from '@/components/screens/Plan';
import { Embryology } from '@/components/screens/Embryology';
import { Cryostorage } from '@/components/screens/Cryostorage';
import { Transfer } from '@/components/screens/Transfer';
import { Pregnancy } from '@/components/screens/Pregnancy';
import { Laboratory } from '@/components/screens/Laboratory';
import { Pharmacy } from '@/components/screens/Pharmacy';
import { Inventory } from '@/components/screens/Inventory';
import { Registration } from '@/components/screens/Registration';
import { Billing } from '@/components/screens/Billing';
import { Accounting } from '@/components/screens/Accounting';
import { Staff } from '@/components/screens/Staff';
import { Reports } from '@/components/screens/Reports';
import { Access } from '@/components/screens/Access';
import { Audit } from '@/components/screens/Audit';
import { Administration } from '@/components/screens/Administration';
import { Donors } from '@/components/screens/Donors';
import { Messaging } from '@/components/screens/Messaging';
import { AssetTracking } from '@/components/screens/AssetTracking';
import { Settings } from '@/components/screens/Settings';

import { Lock, ArrowLeft } from 'lucide-react';

/** Shown when a role navigates to a module outside its permission set. */
function Restricted() {
  const { back, role } = useApp();
  return (
    <div className="screen-enter flex h-full items-center justify-center p-8">
      <Card className="max-w-md p-8 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-ink-100">
          <Lock className="h-7 w-7 text-ink-400" />
        </div>
        <h2 className="tracking-display mt-5 text-[20px] font-semibold text-ink-900">
          You do not have permission to view this module
        </h2>
        <p className="mt-2 text-[13.5px] leading-relaxed text-ink-500">
          Your current role does not include access to this area of the clinical system. This
          attempt has been recorded in the audit trail.
        </p>
        <Button className="mt-6" icon={<ArrowLeft className="h-4 w-4" />} onClick={back}>
          Go back
        </Button>
      </Card>
    </div>
  );
}

function ScreenRouter() {
  const { screen, role, scanMode } = useApp();
  if (!role) return null;
  // A QR scan can bring any signed-in user to the asset scan page regardless
  // of the sidebar's role map — the page and its APIs still enforce
  // `assets.read` / `assets.move` on the backend.
  const scanBypass = screen === 'assets' && scanMode;
  if (!scanBypass && !canAccess(role, screen)) return <Restricted />;

  switch (screen) {
    case 'dashboard':
      return <Dashboard />;
    case 'patients':
      return <Patients />;
    case 'registration':
      return <Registration />;
    case 'workspace':
      return <Workspace />;
    case 'appointments':
      return <Appointments />;
    case 'timeline':
      return <Timeline />;
    case 'monitoring':
      return <Monitoring />;
    case 'plan':
      return <Plan />;
    case 'embryology':
      return <Embryology />;
    case 'cryostorage':
      return <Cryostorage />;
    case 'transfer':
      return <Transfer />;
    case 'pregnancy':
      return <Pregnancy />;
    case 'laboratory':
      return <Laboratory />;
    case 'pharmacy':
      return <Pharmacy />;
    case 'inventory':
      return <Inventory />;
    case 'billing':
      return <Billing />;
    case 'accounting':
      return <Accounting />;
    case 'staff':
      return <Staff />;
    case 'reports':
      return <Reports />;
    case 'access':
      return <Access />;
    case 'audit':
      return <Audit />;
    case 'administration':
      return <Administration />;
    case 'donors':
      return <Donors />;
    case 'messaging':
      return <Messaging />;
    case 'assets':
      return <AssetTracking />;
    case 'settings':
      return <Settings />;
    default:
      return <Dashboard />;
  }
}

export function AppShell() {
  const { role, toasts, dismissToast, setPaletteOpen, paletteOpen, screen } = useApp();
  const { initializing } = useAuth();
  const { prefs } = usePreferences();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useHotkey('k', () => setPaletteOpen(!paletteOpen));

  // Close the mobile drawer automatically whenever navigation happens
  // from a source other than the drawer itself (e.g. command palette).
  useEffect(() => {
    setMobileNavOpen(false);
  }, [screen]);

  // Silent-refresh (restoring a session from the httpOnly cookie on page
  // load) is in flight — hold off rendering Login so an already-signed-in
  // user doesn't see a login flash before landing back on their screen.
  if (initializing) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-ink-50">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
      </div>
    );
  }

  if (!role) return <Login />;

  return (
    <div
      className={cn(
        // Only bites once installed as a standalone PWA with
        // viewport-fit=cover (app/layout.tsx) — env() resolves to 0px in an
        // ordinary browser tab, so this is a no-op there. Applied on the
        // outermost shell rather than inside Topbar/Sidebar individually so
        // it can't fight their own fixed heights.
        'flex h-screen w-full overflow-hidden bg-ink-50',
        'pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)]',
        preferenceClasses(prefs)
      )}
    >
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((c) => !c)}
        mobileOpen={mobileNavOpen}
        onCloseMobile={() => setMobileNavOpen(false)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenMobileNav={() => setMobileNavOpen(true)} />
        <main key={screen} className="scroll-area relative flex-1">
          <ScreenRouter />
        </main>
      </div>

      <CommandPalette />
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
