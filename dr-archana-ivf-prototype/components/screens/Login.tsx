'use client';

import React, { useState, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { USERS, type Role } from '@/lib/data';
import { ApiError } from '@/lib/api/client';
import { isPasskeySupported } from '@/lib/webauthn';
import { cn } from '@/lib/utils';
import { Button, Input } from '@/components/ui/primitives';
import { useSequence } from '@/lib/hooks';
import {
  Lock,
  Eye,
  EyeOff,
  ShieldCheck,
  Sparkles,
  Microscope,
  HeartPulse,
  Check,
  ArrowRight,
  Fingerprint,
  ScanFace,
  AlertTriangle,
  Pill,
} from 'lucide-react';

const AUTH_STEPS = [
  'Verifying credentials',
  'Establishing secure channel',
  'Loading role permissions',
  'Preparing clinical workspace',
];

/** Emails match the demo accounts seeded by backend/scripts/seed_db.py —
 * picking a card here is a convenience prefill, not a fake local login. */
const ROLE_CARDS: { role: Role; label: string; desc: string; icon: any; email: string }[] = [
  { role: 'doctor', label: 'Dr. Archana', desc: 'Chief Consultant & IVF Specialist', icon: HeartPulse, email: 'archana@drarchanaivf.in' },
  { role: 'receptionist', label: 'Front Office', desc: 'Registration, scheduling & queue', icon: Fingerprint, email: 'lakshmi@drarchanaivf.in' },
  { role: 'embryologist', label: 'Embryology Lab', desc: 'Oocytes, embryos & cryostorage', icon: Microscope, email: 'meera@drarchanaivf.in' },
  { role: 'management', label: 'Management', desc: 'Operations, revenue & analytics', icon: Sparkles, email: 'rajesh@drarchanaivf.in' },
  { role: 'pharmacist', label: 'Pharmacy', desc: 'Medicines, vendors, purchases & stock', icon: Pill, email: 'ganesh@drarchanaivf.in' },
];

const DEMO_PASSWORD = 'ChangeMe123!';
const MIN_STEP_MS = AUTH_STEPS.length * 420 + 320;

export function Login() {
  const { login, loginWithPasskey } = useAuth();
  const [selected, setSelected] = useState<Role>('doctor');
  const [email, setEmail] = useState(ROLE_CARDS[0].email);
  const [password, setPassword] = useState(DEMO_PASSWORD);
  const [showPass, setShowPass] = useState(false);
  const [authenticating, setAuthenticating] = useState(false);
  const [passkeyAttempting, setPasskeyAttempting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const step = useSequence(AUTH_STEPS.length, 420, authenticating);
  const attemptId = useRef(0);
  // Evaluated once on mount, not during render, so server and client agree
  // on the first paint — matching the hydration-safety rule this codebase
  // already follows for preferences (see lib/preferences.tsx). navigator
  // doesn't exist during SSR at all, so this can never be a useState
  // initializer either.
  const [passkeySupported, setPasskeySupported] = useState(false);
  React.useEffect(() => setPasskeySupported(isPasskeySupported()), []);

  const selectRole = (r: Role) => {
    setSelected(r);
    setEmail(ROLE_CARDS.find((c) => c.role === r)!.email);
    setError(null);
  };

  const handleSubmit = () => {
    if (authenticating) return;
    setError(null);
    setAuthenticating(true);
    const id = ++attemptId.current;
    const startedAt = Date.now();

    login(email, password)
      .then(() => {
        // No further action needed here — once login() resolves, useAuth's
        // `user` flips to non-null and AppShell swaps away from <Login />
        // on its own. Nothing to clean up if this component has already unmounted.
      })
      .catch((err: unknown) => {
        if (id !== attemptId.current) return; // a newer attempt superseded this one
        const elapsed = Date.now() - startedAt;
        const remaining = Math.max(MIN_STEP_MS - elapsed, 0);
        // Let the choreography finish its current step visually rather
        // than snapping back mid-animation on a fast failure.
        setTimeout(() => {
          if (id !== attemptId.current) return;
          setAuthenticating(false);
          setError(
            err instanceof ApiError
              ? err.message
              : 'Could not reach the clinical system. Check your connection and try again.'
          );
        }, Math.min(remaining, 600));
      });
  };

  const handlePasskeySubmit = () => {
    if (authenticating || passkeyAttempting) return;
    setError(null);
    setPasskeyAttempting(true);
    loginWithPasskey()
      .catch((err: unknown) => {
        // A cancelled Face ID prompt (user tapped away, or backed out of
        // the system sheet) is not a "wrong password"-shaped failure — it
        // shouldn't read as an account/system problem.
        const message =
          err instanceof DOMException && err.name === 'NotAllowedError'
            ? 'Face ID / Touch ID was cancelled.'
            : err instanceof ApiError
            ? err.message
            : err instanceof Error
            ? err.message
            : 'Could not sign in with a passkey. Use your password instead.';
        setError(message);
      })
      .finally(() => setPasskeyAttempting(false));
  };

  const user = USERS[selected];

  return (
    <div className="relative flex h-screen w-full overflow-hidden bg-ink-50">
      {/* ================= LEFT — BRAND SCENE ================= */}
      <div className="relative hidden w-[52%] shrink-0 overflow-hidden bg-gradient-to-br from-brand-950 via-brand-900 to-emerald-950 lg:block">
        {/* drifting aurora */}
        <div
          className="aurora animate-drift"
          style={{ width: 520, height: 520, top: '-12%', left: '-8%', background: 'radial-gradient(circle, rgba(16,185,129,.38), transparent 70%)' }}
        />
        <div
          className="aurora animate-drift"
          style={{ width: 460, height: 460, bottom: '-14%', right: '-6%', background: 'radial-gradient(circle, rgba(45,212,191,.28), transparent 70%)', animationDelay: '-6s' }}
        />
        <div
          className="aurora animate-drift"
          style={{ width: 380, height: 380, top: '38%', left: '42%', background: 'radial-gradient(circle, rgba(52,211,153,.2), transparent 70%)', animationDelay: '-12s' }}
        />
        <div className="grid-texture absolute inset-0 opacity-[0.4]" />
        <div className="noise-texture absolute inset-0" />

        <div className="relative z-10 flex h-full flex-col justify-between p-12 xl:p-14">
          {/* Wordmark */}
          <div className="animate-fade-up">
            <div className="flex items-center gap-3.5">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/12 ring-1 ring-inset ring-white/20 backdrop-blur-sm">
                <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none">
                  <path d="M12 21c-1.5-3-5-5.2-5-9a5 5 0 0110 0c0 3.8-3.5 6-5 9z" fill="white" fillOpacity="0.95" />
                  <circle cx="12" cy="11" r="2.1" fill="#065F46" />
                </svg>
              </div>
              <div>
                <p className="font-display text-[24px] leading-tight text-white">Dr. Archana</p>
                <p className="text-[12px] font-medium uppercase tracking-[0.18em] text-brand-300">
                  IVF &amp; Women Centre
                </p>
              </div>
            </div>
          </div>

          {/* Statement */}
          <div className="max-w-[440px]">
            <h1
              className="tracking-display animate-fade-up font-display text-[46px] leading-[1.08] text-white xl:text-[52px]"
              style={{ animationDelay: '0.1s' }}
            >
              The complete fertility journey,
              <span className="text-brand-300"> in one clinical system.</span>
            </h1>
            <p
              className="animate-fade-up mt-5 text-[15px] leading-relaxed text-brand-100/70"
              style={{ animationDelay: '0.2s' }}
            >
              From first consultation through stimulation, embryology, transfer and pregnancy —
              every record connected, every decision documented, every outcome tracked.
            </p>

            <div className="mt-10 grid grid-cols-3 gap-3">
              {[
                { icon: HeartPulse, label: 'Clinical Excellence', sub: 'Complete fertility care' },
                { icon: ShieldCheck, label: 'Secure & Private', sub: 'Audit-ready records' },
                { icon: Microscope, label: 'Embryology Grade', sub: 'Laboratory precision' },
              ].map((f, i) => {
                const Icon = f.icon;
                return (
                  <div
                    key={f.label}
                    className="animate-fade-up rounded-xl border border-white/10 bg-white/[0.06] p-3.5 backdrop-blur-sm"
                    style={{ animationDelay: `${0.3 + i * 0.09}s` }}
                  >
                    <Icon className="h-4.5 w-4.5 text-brand-300" style={{ height: 18, width: 18 }} />
                    <p className="mt-2.5 text-[13.5px] font-semibold leading-tight text-white">{f.label}</p>
                    <p className="mt-1 text-[12px] leading-snug text-brand-100/55">{f.sub}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Footer stats */}
          <div className="animate-fade-up flex items-center gap-8 border-t border-white/10 pt-6" style={{ animationDelay: '0.6s' }}>
            {[
              { v: '2,400+', l: 'Couples treated' },
              { v: '62%', l: 'Clinical pregnancy rate' },
              { v: '18 yrs', l: 'Of fertility care' },
            ].map((s) => (
              <div key={s.l}>
                <p className="tnum font-display text-[22px] leading-none text-white">{s.v}</p>
                <p className="mt-1.5 text-[12px] text-brand-100/50">{s.l}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ================= RIGHT — ACCESS ================= */}
      <div className="relative flex flex-1 items-center justify-center overflow-y-auto p-6 sm:p-10">
        <div className="grid-texture pointer-events-none absolute inset-0 opacity-60" />

        <div className="relative w-full max-w-[420px]">
          {/* mobile brand */}
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700">
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none">
                <path d="M12 21c-1.5-3-5-5.2-5-9a5 5 0 0110 0c0 3.8-3.5 6-5 9z" fill="white" />
                <circle cx="12" cy="11" r="2.1" fill="#059669" />
              </svg>
            </div>
            <div>
              <p className="font-display text-[18px] leading-tight text-ink-900">Dr. Archana</p>
              <p className="text-[11.5px] font-medium uppercase tracking-[0.14em] text-brand-700">
                IVF &amp; Women Centre
              </p>
            </div>
          </div>

          {!authenticating ? (
            <div className="animate-fade-up">
              <div className="mb-1.5 flex items-center gap-2">
                <span className="h-px w-6 bg-brand-500" />
                <span className="text-[12px] font-semibold uppercase tracking-[0.12em] text-brand-700">
                  Clinical Access
                </span>
              </div>
              <h2 className="tracking-display text-[28px] font-semibold text-ink-900">
                Sign in securely
              </h2>
              <p className="mt-1.5 text-[14.5px] leading-relaxed text-ink-500">
                Secure access to clinical and hospital operations.
              </p>

              {/* Role selector */}
              <div className="mt-7">
                <p className="mb-2.5 text-[13px] font-medium text-ink-700">Select your role</p>
                <div className="grid grid-cols-2 gap-2">
                  {ROLE_CARDS.map((r, i) => {
                    const Icon = r.icon;
                    const active = selected === r.role;
                    return (
                      <button
                        key={r.role}
                        onClick={() => selectRole(r.role)}
                        className={cn(
                          'press group relative overflow-hidden rounded-xl border p-3 text-left transition-all duration-250',
                          active
                            ? 'border-brand-500 bg-brand-50/70 shadow-glow'
                            : 'border-ink-200 bg-white hover:border-ink-300 hover:bg-ink-50/60'
                        )}
                        style={{ animationDelay: `${i * 60}ms` }}
                      >
                        <div className="flex items-start justify-between">
                          <div
                            className={cn(
                              'flex h-8 w-8 items-center justify-center rounded-lg transition-colors',
                              active ? 'bg-brand-600 text-white' : 'bg-ink-100 text-ink-500'
                            )}
                          >
                            <Icon className="h-4 w-4" />
                          </div>
                          {active && (
                            <div className="animate-scale-in flex h-4 w-4 items-center justify-center rounded-full bg-brand-600">
                              <Check className="h-2.5 w-2.5 text-white" strokeWidth={3.5} />
                            </div>
                          )}
                        </div>
                        <p
                          className={cn(
                            'mt-2.5 text-[13.5px] font-semibold leading-tight',
                            active ? 'text-brand-900' : 'text-ink-800'
                          )}
                        >
                          {r.label}
                        </p>
                        <p className="mt-0.5 text-[12px] leading-snug text-ink-500">{r.desc}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Credentials */}
              <div className="mt-5 space-y-3">
                <Input
                  label="Employee ID or Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  icon={<Fingerprint className="h-3.5 w-3.5" />}
                />
                <div className="relative">
                  <Input
                    label="Password"
                    type={showPass ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                    icon={<Lock className="h-3.5 w-3.5" />}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPass((v) => !v)}
                    className="absolute right-3 top-[34px] text-ink-400 transition-colors hover:text-ink-700"
                  >
                    {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <p className="text-[12px] text-ink-400">Demo password: {DEMO_PASSWORD}</p>

                {error && (
                  <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
                    <p className="text-[13.5px] leading-relaxed text-rose-700">{error}</p>
                  </div>
                )}
              </div>

              <div className="mt-4 flex items-center justify-end">
                <button className="text-[13.5px] font-medium text-brand-700 hover:text-brand-800">
                  Forgot password?
                </button>
              </div>

              <Button
                variant="primary"
                size="lg"
                className="mt-6 w-full"
                iconRight={<ArrowRight className="h-4 w-4" />}
                onClick={handleSubmit}
                disabled={!email || !password}
              >
                Sign In Securely
              </Button>

              {passkeySupported && (
                <>
                  <div className="my-4 flex items-center gap-3">
                    <span className="h-px flex-1 bg-ink-200" />
                    <span className="text-[12px] font-medium uppercase tracking-[0.08em] text-ink-400">or</span>
                    <span className="h-px flex-1 bg-ink-200" />
                  </div>
                  <Button
                    variant="secondary"
                    size="lg"
                    className="w-full"
                    icon={<ScanFace className="h-4 w-4" />}
                    loading={passkeyAttempting}
                    onClick={handlePasskeySubmit}
                  >
                    {passkeyAttempting ? 'Waiting for Face ID / Touch ID…' : 'Sign in with Face ID / Touch ID'}
                  </Button>
                  <p className="mt-2 text-center text-[12px] text-ink-400">
                    Only works if a passkey was already registered for your account on this device — set one up from Settings once signed in.
                  </p>
                </>
              )}

              <div className="mt-6 flex items-start gap-2.5 rounded-xl border border-ink-200/70 bg-ink-50/70 p-3">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
                <p className="text-[12.5px] leading-relaxed text-ink-500">
                  Protected clinical information. Authorised hospital personnel only. All access is
                  logged to the audit trail and session activity is monitored.
                </p>
              </div>
            </div>
          ) : (
            /* ============ AUTHENTICATION CHOREOGRAPHY ============ */
            <div className="animate-scale-in">
              <div className="flex flex-col items-center text-center">
                <div className="relative flex h-20 w-20 items-center justify-center">
                  <span className="absolute inset-0 animate-pulse-ring rounded-full bg-brand-500/25" />
                  <span
                    className="absolute inset-0 animate-pulse-ring rounded-full bg-brand-500/20"
                    style={{ animationDelay: '0.8s' }}
                  />
                  <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 shadow-glow">
                    <ShieldCheck className="h-8 w-8 text-white" strokeWidth={1.8} />
                  </div>
                </div>

                <h2 className="tracking-display mt-7 text-[22px] font-semibold text-ink-900">
                  Establishing secure session
                </h2>
                <p className="mt-1.5 text-[14.5px] text-ink-500">
                  Signing in as <span className="font-medium text-ink-800">{user.name}</span>
                </p>

                <div className="mt-8 w-full space-y-2.5">
                  {AUTH_STEPS.map((s, i) => {
                    const done = step > i;
                    const current = step === i;
                    return (
                      <div
                        key={s}
                        className={cn(
                          'flex items-center gap-3 rounded-xl border px-3.5 py-2.5 transition-all duration-400',
                          done
                            ? 'border-brand-200 bg-brand-50/60'
                            : current
                            ? 'border-brand-300 bg-white shadow-glow'
                            : 'border-ink-200/60 bg-ink-50/40 opacity-50'
                        )}
                      >
                        <div
                          className={cn(
                            'flex h-5 w-5 shrink-0 items-center justify-center rounded-full transition-colors',
                            done ? 'bg-brand-600' : current ? 'bg-brand-100' : 'bg-ink-200'
                          )}
                        >
                          {done ? (
                            <Check className="h-3 w-3 text-white" strokeWidth={3.5} />
                          ) : current ? (
                            <span className="h-2.5 w-2.5 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
                          ) : null}
                        </div>
                        <span
                          className={cn(
                            'text-[14px] font-medium',
                            done ? 'text-brand-800' : current ? 'text-ink-900' : 'text-ink-400'
                          )}
                        >
                          {s}
                        </span>
                        {done && <Check className="ml-auto h-3.5 w-3.5 text-brand-500" />}
                      </div>
                    );
                  })}
                </div>

                <div className="bar-indeterminate relative mt-7 h-1 w-full overflow-hidden rounded-full bg-ink-100" />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
