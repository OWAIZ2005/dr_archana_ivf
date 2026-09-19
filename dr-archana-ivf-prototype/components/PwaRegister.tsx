'use client';

import { useEffect } from 'react';

/** Registers the app-shell service worker (public/sw.js). A no-op outside
 * a browser with SW support and a secure context — Safari on iPad supports
 * it (iOS 11.3+) but only over HTTPS or localhost, same constraint as the
 * WebAuthn/passkey ceremony elsewhere in this app. */
export function PwaRegister() {
  useEffect(() => {
    if (typeof window === 'undefined' || !('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Registration failing (e.g. insecure origin in local dev over a LAN
      // IP) should never block the app — the SW is a performance layer,
      // not a dependency.
    });
  }, []);

  return null;
}
