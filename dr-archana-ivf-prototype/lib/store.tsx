'use client';

import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import type { Role, StaffUser } from './data';
import type { ToastItem } from '@/components/ui/primitives';
import { useAuth } from './auth';
import { usePreferences } from './preferences';
import { toDisplayUser } from './roleMeta';
import { canAccess } from '@/components/layout/nav';

export type ScreenId =
  | 'dashboard'
  | 'patients'
  | 'registration'
  | 'workspace'
  | 'appointments'
  | 'timeline'
  | 'monitoring'
  | 'plan'
  | 'embryology'
  | 'cryostorage'
  | 'transfer'
  | 'pregnancy'
  | 'laboratory'
  | 'pharmacy'
  | 'inventory'
  | 'billing'
  | 'accounting'
  | 'staff'
  | 'reports'
  | 'access'
  | 'audit'
  | 'administration'
  | 'donors'
  | 'messaging'
  | 'assets'
  | 'settings';

interface AppState {
  role: Role | null;
  user: StaffUser | null;
  screen: ScreenId;
  history: ScreenId[];
  toasts: ToastItem[];
  paletteOpen: boolean;
  notifOpen: boolean;
  transferComplete: boolean;
  /** The patient every patient-scoped screen (Workspace, Timeline,
   * Monitoring, Plan, Transfer, Pregnancy, Embryology, Cryostorage) reads
   * from — set via `openPatient` from Patients/Registration/Dashboard,
   * replacing the old build's single hardcoded demo patient. */
  selectedPatientId: string | null;
  /** The asset the Asset & Item Tracking screen shows a detail view for;
   * null = the search/list view. */
  selectedAssetId: string | null;
  /** A pending `#scan=<token>` from a QR the user opened with a phone
   * camera; the Asset Tracking screen resolves it once, then clears it. */
  scanToken: string | null;
  /** True when the current asset view was entered by scanning a QR — the
   * Asset Tracking screen then renders the lightweight mobile scan page
   * instead of the full desktop detail. Cleared by a normal list click or
   * by "View full detail". */
  scanMode: boolean;
  /** Permission codes the signed-in user's role grants (from /auth/me). */
  permissions: string[];
  /** True when the signed-in user's role grants `code`. The backend still
   * enforces every action — this only decides what to show. */
  can: (code: string) => boolean;
  logout: () => void;
  go: (screen: ScreenId) => void;
  /** Sets the active patient and navigates to `screen` (defaults to the
   * patient workspace) in one call. */
  openPatient: (patientId: string, screen?: ScreenId) => void;
  /** Opens the Asset & Item Tracking screen; a non-null id shows that
   * asset's detail view, null shows the list. */
  openAsset: (assetId: string | null) => void;
  /** Show the lightweight mobile scan page for a resolved asset (or a
   * "not found" state when null). Used only on the QR-scan path. */
  openScannedAsset: (assetId: string | null) => void;
  /** Leave the mobile scan page and show the full desktop asset detail
   * for the same asset. */
  exitScanMode: () => void;
  clearScanToken: () => void;
  back: () => void;
  toast: (t: Omit<ToastItem, 'id'>) => void;
  dismissToast: (id: number) => void;
  setPaletteOpen: (v: boolean) => void;
  setNotifOpen: (v: boolean) => void;
  completeTransfer: () => void;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const { user: authUser, logout: authLogout } = useAuth();
  const { prefs } = usePreferences();
  const role = authUser ? toDisplayUser(authUser).role : null;
  const user = authUser ? toDisplayUser(authUser) : null;
  const permissions = authUser?.permissions ?? [];
  const can = useCallback(
    (code: string) => (authUser?.permissions ?? []).includes(code),
    [authUser]
  );
  // Read through a ref so changing the preference later never yanks the
  // user off the screen they are currently working on.
  const startScreenRef = useRef(prefs.startScreen);
  startScreenRef.current = prefs.startScreen;

  const [screen, setScreen] = useState<ScreenId>('dashboard');
  const [history, setHistory] = useState<ScreenId[]>([]);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [transferComplete, setTransferComplete] = useState(false);
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [scanToken, setScanToken] = useState<string | null>(null);
  const [scanMode, setScanMode] = useState(false);
  const toastId = useRef(0);
  const prevAuthed = useRef(false);

  // Land on a role-appropriate starting screen the moment a login
  // succeeds (mirrors the old fake login()'s behavior), and reset
  // navigation/UI state the moment a session ends.
  useEffect(() => {
    if (authUser && !prevAuthed.current) {
      const roleDefault: ScreenId =
        role === 'management' ? 'reports' : role === 'embryologist' ? 'embryology' : role === 'receptionist' ? 'patients' : role === 'pharmacist' ? 'pharmacy' : role === 'prescription' ? 'appointments' : 'dashboard';
      // A staff member can pin their own landing screen in Settings →
      // User Interface. Fall back to the role default if that choice is
      // no longer one their role may open.
      const chosen = startScreenRef.current;
      const landing =
        chosen !== 'role-default' && role && canAccess(role, chosen as ScreenId)
          ? (chosen as ScreenId)
          : roleDefault;
      setScreen(landing);
      setHistory([]);
    } else if (!authUser && prevAuthed.current) {
      setHistory([]);
      setToasts([]);
      setTransferComplete(false);
      setSelectedPatientId(null);
      setSelectedAssetId(null);
      setScanMode(false);
      setScanToken(null);
    }
    prevAuthed.current = !!authUser;
  }, [authUser, role]);

  // A phone camera / scanner that reads an asset QR opens the app at
  // `…/#scan=<token>`. Capture the token once, strip it from the URL, and
  // let the Asset Tracking screen resolve it (after auth).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const m = window.location.hash.match(/[#&]scan=([A-Za-z0-9_-]+)/);
    if (m) {
      setScanToken(m[1]);
      setScanMode(true);
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const toast = useCallback(
    (t: Omit<ToastItem, 'id'>) => {
      const id = ++toastId.current;
      setToasts((prev) => [...prev, { ...t, id }]);
      setTimeout(() => dismissToast(id), 4600);
    },
    [dismissToast]
  );

  const go = useCallback((next: ScreenId) => {
    setScreen((cur) => {
      if (cur !== next) setHistory((h) => [...h.slice(-12), cur]);
      return next;
    });
    if (next !== 'assets') setScanMode(false);
    setPaletteOpen(false);
    setNotifOpen(false);
  }, []);

  const openPatient = useCallback(
    (patientId: string, screen: ScreenId = 'workspace') => {
      setSelectedPatientId(patientId);
      go(screen);
    },
    [go]
  );

  const openAsset = useCallback(
    (assetId: string | null) => {
      setSelectedAssetId(assetId);
      setScanMode(false);
      go('assets');
    },
    [go]
  );

  const openScannedAsset = useCallback(
    (assetId: string | null) => {
      setSelectedAssetId(assetId);
      setScanMode(true);
      go('assets');
    },
    [go]
  );

  const exitScanMode = useCallback(() => setScanMode(false), []);

  const clearScanToken = useCallback(() => setScanToken(null), []);

  // Once a QR-scan token is pending AND the user is signed in, route to the
  // Asset Tracking screen so it can resolve the token → asset detail. This is
  // what carries a scan through the login screen: the token is captured before
  // auth (see the hash effect above), held in state across the login
  // transition, then picked up here.
  useEffect(() => {
    if (authUser && scanToken && screen !== 'assets') go('assets');
  }, [authUser, scanToken, screen, go]);

  const back = useCallback(() => {
    setHistory((h) => {
      if (!h.length) return h;
      const prev = h[h.length - 1];
      setScreen(prev);
      return h.slice(0, -1);
    });
  }, []);

  const logout = useCallback(() => {
    authLogout();
  }, [authLogout]);

  const completeTransfer = useCallback(() => setTransferComplete(true), []);

  return (
    <Ctx.Provider
      value={{
        role,
        user,
        screen,
        history,
        toasts,
        paletteOpen,
        notifOpen,
        transferComplete,
        selectedPatientId,
        selectedAssetId,
        scanToken,
        scanMode,
        permissions,
        can,
        logout,
        go,
        openPatient,
        openAsset,
        openScannedAsset,
        exitScanMode,
        clearScanToken,
        back,
        toast,
        dismissToast,
        setPaletteOpen,
        setNotifOpen,
        completeTransfer,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useApp() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}
