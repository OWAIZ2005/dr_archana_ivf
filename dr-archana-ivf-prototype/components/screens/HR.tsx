'use client';

import React, { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  Users,
  Fingerprint,
  Wallet,
  Activity,
  AlertTriangle,
  FileDown,
  SlidersHorizontal,
} from 'lucide-react';
import { HrDashboardHome } from './hr/Dashboard';
import { HrEmployees } from './hr/Employees';
import { HrAttendance } from './hr/Attendance';
import { HrPayroll } from './hr/Payroll';
import { HrPatientFlow } from './hr/PatientFlow';
import { HrDelays } from './hr/Delays';
import { HrReports } from './hr/Reports';
import { HrSettingsPanel } from './hr/SettingsPanel';

type HrView = 'dashboard' | 'employees' | 'attendance' | 'payroll' | 'flow' | 'delays' | 'reports' | 'settings';

const HR_NAV: { id: HrView; label: string; icon: any }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'employees', label: 'Employees', icon: Users },
  { id: 'attendance', label: 'Attendance', icon: Fingerprint },
  { id: 'payroll', label: 'Payroll', icon: Wallet },
  { id: 'flow', label: 'Patient Flow', icon: Activity },
  { id: 'delays', label: 'Delays', icon: AlertTriangle },
  { id: 'reports', label: 'Reports', icon: FileDown },
  { id: 'settings', label: 'Settings', icon: SlidersHorizontal },
];

/** The HR module's own internal shell — a second-level sidebar nested
 * inside the main app shell, per spec §29's wireframe ("HR dashboard
 * should have its own navigation/sidebar"). Kept as a single ScreenId
 * ('hr') in the outer nav rather than eight, so every sub-view lives in
 * its own component file under components/screens/hr/ but shares one
 * entry point, one internal nav, and one alerts banner. */
export function HR() {
  const [view, setView] = useState<HrView>('dashboard');

  return (
    <div className="flex h-full min-h-0">
      <nav className="flex w-56 shrink-0 flex-col gap-1 border-r border-ink-200/70 bg-white px-3 py-4">
        <p className="px-2.5 pb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-400">Human Resources</p>
        {HR_NAV.map((item) => {
          const Icon = item.icon;
          const active = item.id === view;
          return (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={cn(
                'flex h-10 items-center gap-2.5 rounded-lg px-2.5 text-[13.5px] font-medium transition-colors',
                active ? 'bg-brand-50 text-brand-700 ring-1 ring-brand-600/10' : 'text-ink-600 hover:bg-ink-50 hover:text-ink-900'
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {item.label}
            </button>
          );
        })}
      </nav>
      <div className="scroll-area min-w-0 flex-1 overflow-y-auto p-6">
        {view === 'dashboard' && <HrDashboardHome onNavigate={setView} />}
        {view === 'employees' && <HrEmployees />}
        {view === 'attendance' && <HrAttendance />}
        {view === 'payroll' && <HrPayroll />}
        {view === 'flow' && <HrPatientFlow />}
        {view === 'delays' && <HrDelays />}
        {view === 'reports' && <HrReports />}
        {view === 'settings' && <HrSettingsPanel />}
      </div>
    </div>
  );
}
