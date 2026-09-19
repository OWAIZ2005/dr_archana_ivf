'use client';

import { AppQueryProvider } from '@/lib/query-client';
import { AuthProvider } from '@/lib/auth';
import { AppProvider } from '@/lib/store';
import { PreferencesProvider } from '@/lib/preferences';
import { IdleLockProvider, IdleLockOverlay } from '@/lib/idleLock';
import { AppShell } from '@/components/layout/AppShell';

export default function Page() {
  return (
    <AppQueryProvider>
      <AuthProvider>
        <PreferencesProvider>
          <AppProvider>
            <IdleLockProvider>
              <AppShell />
              <IdleLockOverlay />
            </IdleLockProvider>
          </AppProvider>
        </PreferencesProvider>
      </AuthProvider>
    </AppQueryProvider>
  );
}
