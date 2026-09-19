'use client';

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useAuth } from './auth';
import { isPasskeySupported } from './webauthn';
import { ApiError } from './api/client';
import { Button, Input } from '@/components/ui/primitives';
import { ScanFace, ShieldCheck, ArrowRight, AlertTriangle } from 'lucide-react';

interface IdleLockState {
  locked: boolean;
}

const Ctx = createContext<IdleLockState | null>(null);

const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'touchstart', 'wheel'] as const;
// Only used before GET /auth/me has returned idle_timeout_minutes (a brief
// window right after login/session-restore) — matches the backend's own
// Settings.IDLE_TIMEOUT_MINUTES default, so the two are never far apart
// even in that gap.
const FALLBACK_TIMEOUT_MINUTES = 30;

/**
 * A client-side idle-lock gate, additive to the real session underneath —
 * the JWT/refresh-cookie session the backend tracks keeps running exactly
 * as it already does (including the server's own independent idle-timeout
 * check in backend/app/auth/service.py, which this does not replace).
 * This just puts a full-screen lock in front of the UI after inactivity,
 * matters most for a shared front-desk/pharmacy iPad someone walked away
 * from. Unlocking calls the real login (password or passkey) again — a
 * genuine re-authentication, not a flag flip — so it also naturally
 * refreshes the underlying tokens.
 */
export function IdleLockProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [locked, setLocked] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const resetTimer = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!user) return;
    const minutes = user.idle_timeout_minutes ?? FALLBACK_TIMEOUT_MINUTES;
    timerRef.current = setTimeout(() => setLocked(true), minutes * 60_000);
  }, [user]);

  useEffect(() => {
    if (!user) {
      setLocked(false);
      return;
    }
    resetTimer();
    const onActivity = () => {
      // Deliberately no-op while locked: activity on the lock screen itself
      // (typing a password, tapping Face ID) must not silently dismiss the
      // lock without an actual successful re-auth.
      setLocked((isLocked) => {
        if (!isLocked) resetTimer();
        return isLocked;
      });
    };
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, onActivity, { passive: true }));
    return () => {
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, onActivity));
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, resetTimer]);

  return <Ctx.Provider value={{ locked }}>{children}</Ctx.Provider>;
}

export function useIdleLock() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useIdleLock must be used inside IdleLockProvider');
  return ctx;
}

/** Renders nothing while unlocked. Mount once, as a sibling of the rest of
 * the app (not inside a specific screen), so it can cover everything
 * regardless of which screen was open when the lock engaged. */
export function IdleLockOverlay() {
  const { locked } = useIdleLock();
  const { user, login, loginWithPasskey } = useAuth();
  const [password, setPassword] = useState('');
  const [passkeyAttempting, setPasskeyAttempting] = useState(false);
  const [passwordAttempting, setPasswordAttempting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!locked) {
      setPassword('');
      setError(null);
    }
  }, [locked]);

  if (!locked || !user) return null;

  const unlockWithPassword = () => {
    if (!password || passwordAttempting) return;
    setError(null);
    setPasswordAttempting(true);
    login(user.email, password)
      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : 'Incorrect password.'))
      .finally(() => setPasswordAttempting(false));
  };

  const unlockWithPasskey = () => {
    if (passkeyAttempting) return;
    setError(null);
    setPasskeyAttempting(true);
    loginWithPasskey()
      .catch((err: unknown) =>
        setError(
          err instanceof DOMException && err.name === 'NotAllowedError'
            ? 'Cancelled.'
            : 'Could not unlock with Face ID / Touch ID — use your password instead.'
        )
      )
      .finally(() => setPasskeyAttempting(false));
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-ink-950/92 p-6 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-pop">
        <div className="flex flex-col items-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 shadow-glow">
            <ShieldCheck className="h-7 w-7 text-white" />
          </div>
          <h2 className="tracking-display mt-4 text-[19px] font-semibold text-ink-900">Session locked</h2>
          <p className="mt-1 text-[13.5px] text-ink-500">
            Signed out due to inactivity — <span className="font-medium text-ink-800">{user.full_name}</span>, sign in
            again to continue.
          </p>
        </div>

        {isPasskeySupported() && (
          <>
            <Button
              variant="primary" size="lg" className="mt-5 w-full"
              icon={<ScanFace className="h-4 w-4" />}
              loading={passkeyAttempting}
              onClick={unlockWithPasskey}
            >
              {passkeyAttempting ? 'Waiting for Face ID / Touch ID…' : 'Unlock with Face ID / Touch ID'}
            </Button>
            <div className="my-4 flex items-center gap-3">
              <span className="h-px flex-1 bg-ink-200" />
              <span className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-400">or</span>
              <span className="h-px flex-1 bg-ink-200" />
            </div>
          </>
        )}

        <div className="space-y-3">
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && unlockWithPassword()}
            autoFocus
          />
          {error && (
            <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
              <p className="text-[13px] leading-relaxed text-rose-700">{error}</p>
            </div>
          )}
          <Button
            variant={isPasskeySupported() ? 'secondary' : 'primary'}
            size="lg" className="w-full"
            iconRight={<ArrowRight className="h-4 w-4" />}
            loading={passwordAttempting}
            disabled={!password}
            onClick={unlockWithPassword}
          >
            Unlock
          </Button>
        </div>
      </div>
    </div>
  );
}
