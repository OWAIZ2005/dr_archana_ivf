'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { fetchCurrentUser, loginRequest, logoutRequest, trySilentLogin } from './api/auth';
import { loginWithPasskeyRequest } from './api/passkeys';
import { setOnAuthExpired } from './api/client';
import type { UserSummary } from './api/types';

interface AuthState {
  user: UserSummary | null;
  /** True until the initial silent-refresh attempt (on page load) resolves. */
  initializing: boolean;
  login: (email: string, password: string) => Promise<void>;
  /** Additive alternative to `login` — Face ID/Touch ID via a registered
   *  passkey. Never a replacement: see backend/app/webauthn/models.py for
   *  why password stays the login every account can always fall back to. */
  loginWithPasskey: () => Promise<void>;
  logout: () => Promise<void>;
  /** Re-fetches /auth/me — used after actions that can change the user's
   * own record (e.g. a future profile edit). */
  refreshUser: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserSummary | null>(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    let cancelled = false;
    trySilentLogin().then((restored) => {
      if (!cancelled) {
        setUser(restored);
        setInitializing(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // A background refresh (triggered by apiFetch on a 401) can fail after
    // the session's already been showing as logged in — e.g. the refresh
    // token expired or was revoked elsewhere. Fall back to the Login
    // screen in that one place rather than every call site handling it.
    setOnAuthExpired(() => setUser(null));
    return () => setOnAuthExpired(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const loggedInUser = await loginRequest(email, password);
    setUser(loggedInUser);
  }, []);

  const loginWithPasskey = useCallback(async () => {
    const loggedInUser = await loginWithPasskeyRequest();
    setUser(loggedInUser);
  }, []);

  const logout = useCallback(async () => {
    await logoutRequest().catch(() => {
      // Best-effort — the local session is cleared either way so the UI
      // never gets stuck showing a "signed in" state the server disagrees with.
    });
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    setUser(await fetchCurrentUser());
  }, []);

  return (
    <Ctx.Provider value={{ user, initializing, login, loginWithPasskey, logout, refreshUser }}>{children}</Ctx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
