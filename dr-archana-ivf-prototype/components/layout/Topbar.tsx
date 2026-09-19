'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '@/lib/store';
import { usePreferences } from '@/lib/preferences';
import { NOTIFICATIONS } from '@/lib/data';
import { SCREEN_TITLES } from './nav';
import { cn, TONE, TODAY } from '@/lib/utils';
import { Avatar, Badge, Button } from '@/components/ui/primitives';
import { useClock } from '@/lib/hooks';
import {
  Search,
  Bell,
  Plus,
  ChevronDown,
  ArrowLeft,
  ShieldCheck,
  CalendarPlus,
  FlaskConical,
  FileText,
  Check,
  Menu,
  Sliders,
  LogOut,
} from 'lucide-react';

export function Topbar({ onOpenMobileNav }: { onOpenMobileNav: () => void }) {
  const { user, screen, go, back, history, setPaletteOpen, notifOpen, setNotifOpen, toast, logout } =
    useApp();
  const { prefs } = usePreferences();
  const [quickOpen, setQuickOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const clock = useClock();
  const wrapRef = useRef<HTMLDivElement>(null);

  const unread = NOTIFICATIONS.filter((n) => n.unread).length;

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setQuickOpen(false);
        setUserOpen(false);
        setNotifOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [setNotifOpen]);

  // Deliberately excludes "Register Patient": that already has a permanent
  // home in the left menu, and offering the same task in two places is the
  // fastest way to make staff unsure which one is the real one. What stays
  // here are the actions with no screen of their own.
  const quickActions = [
    { label: 'Book Appointment', icon: CalendarPlus, action: () => toast({ title: 'Appointment scheduler', body: 'Opening the scheduling workspace.', tone: 'info' }) },
    { label: 'Create IVF Cycle', icon: FlaskConical, action: () => go('plan') },
    { label: 'Add Clinical Note', icon: FileText, action: () => toast({ title: 'Clinical note', body: 'Draft note started.', tone: 'info' }) },
  ];

  return (
    <header
      ref={wrapRef}
      className="relative z-20 flex h-[60px] shrink-0 items-center gap-2 border-b border-ink-200/70 bg-white/85 px-3 backdrop-blur-xl sm:h-[68px] sm:gap-4 sm:px-6"
    >
      {/* Mobile nav trigger */}
      <button
        onClick={onOpenMobileNav}
        className="press flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-800 lg:hidden"
        title="Open menu"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Context — the page title alone. The clinic name lives in the menu
          header and does not need repeating on every screen. */}
      <div className="flex min-w-0 items-center gap-2 sm:gap-3">
        {history.length > 0 && (
          <button
            onClick={back}
            className="press hidden h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-800 sm:flex"
            title="Back"
            aria-label="Go back"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
        )}
        <h1 className="truncate text-[16px] font-semibold tracking-[-0.012em] text-ink-900 sm:text-[17px]">
          {SCREEN_TITLES[screen]}
        </h1>
      </div>

      {/* Search — desktop. The label needs `truncate` (not just `flex-1`):
          when the header runs short on space (e.g. exactly 1024px — iPad
          landscape), flexbox squeezes this button below its intended
          300px, and without truncation the untruncated label wraps to
          several lines, spilling out of the fixed-height bar and over the
          screen title next to it. Left free to shrink (no shrink-0) so it
          still yields room to the controls after it instead of overflowing
          the header. */}
      <button
        onClick={() => setPaletteOpen(true)}
        className="group ml-auto hidden h-10 w-[300px] min-w-0 items-center gap-2.5 rounded-lg border border-ink-200 bg-ink-50/70 px-3 text-[14px] text-ink-500 transition-all hover:border-ink-300 hover:bg-white lg:flex"
      >
        <Search className="h-4 w-4 shrink-0" />
        <span className="min-w-0 flex-1 truncate text-left">Search patients, cycles, embryos…</span>
        <kbd className="shrink-0 rounded border border-ink-200 bg-white px-1.5 py-0.5 font-mono text-[10px] text-ink-400">
          ⌘K
        </kbd>
      </button>

      {/* Search — mobile / tablet icon trigger */}
      <button
        onClick={() => setPaletteOpen(true)}
        className="press ml-auto flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-800 lg:hidden"
        title="Search"
        aria-label="Search"
      >
        <Search className="h-5 w-5" />
      </button>

      {/* Date + clock — opt-in from Settings → User Interface */}
      {prefs.showClock && (
        <div className="hidden items-center gap-2 border-l border-ink-200 pl-4 xl:flex">
          <div className="text-right">
            <p className="tnum text-[12.5px] font-semibold text-ink-800">{TODAY}</p>
            <p className="tnum text-[11px] text-ink-400">
              {clock
                ? clock.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
                : '—'}
            </p>
          </div>
        </div>
      )}

      {/* New — the single "create something" entry point */}
      <div className="relative">
        <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => setQuickOpen((v) => !v)}>
          <span className="hidden sm:inline">New</span>
          <ChevronDown className={cn('hidden h-3.5 w-3.5 transition-transform sm:block', quickOpen && 'rotate-180')} />
        </Button>
        {quickOpen && (
          <div className="modal-in absolute right-0 top-full z-50 mt-2 w-60 max-w-[calc(100vw-24px)] overflow-hidden rounded-xl border border-ink-200/70 bg-white p-1.5 shadow-float">
            {quickActions.map((a) => {
              const Icon = a.icon;
              return (
                <button
                  key={a.label}
                  onClick={() => {
                    a.action();
                    setQuickOpen(false);
                  }}
                  className="flex min-h-[44px] w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[14px] font-medium text-ink-700 transition-colors hover:bg-brand-50 hover:text-brand-800"
                >
                  <Icon className="h-4 w-4 text-ink-400" />
                  {a.label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Notifications */}
      <div className="relative">
        <button
          onClick={() => setNotifOpen(!notifOpen)}
          aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
          title="Notifications"
          className="press relative flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-800"
        >
          <Bell className="h-5 w-5" />
          {unread > 0 && (
            <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[9px] font-bold text-white ring-2 ring-white">
              {unread}
            </span>
          )}
        </button>

        {notifOpen && (
          <div className="modal-in fixed inset-x-3 top-[64px] z-50 overflow-hidden rounded-xl border border-ink-200/70 bg-white shadow-float sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-2 sm:w-[380px]">
            <div className="flex items-center justify-between border-b border-ink-100 px-4 py-3">
              <p className="text-[13.5px] font-semibold text-ink-900">Notifications</p>
              <button
                onClick={() => toast({ title: 'All caught up', body: 'Notifications marked as read.', tone: 'success' })}
                className="flex items-center gap-1 text-[11.5px] font-medium text-brand-700 hover:text-brand-800"
              >
                <Check className="h-3 w-3" /> Mark all read
              </button>
            </div>
            <div className="scroll-area max-h-[380px] stagger">
              {NOTIFICATIONS.map((n, i) => (
                <div
                  key={n.id}
                  style={{ ['--i' as string]: i }}
                  className={cn(
                    'flex cursor-pointer gap-3 border-b border-ink-100 px-4 py-3 transition-colors last:border-0 hover:bg-ink-50',
                    n.unread && 'bg-brand-50/30'
                  )}
                >
                  <span className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', TONE[n.tone].dot)} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium leading-snug text-ink-900">{n.title}</p>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-ink-500">{n.body}</p>
                  </div>
                  <span className="shrink-0 text-[11px] text-ink-400">{n.time}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* User — now also the home for settings, session status and sign out */}
      {user && (
        <div className="relative">
          <button
            onClick={() => setUserOpen((v) => !v)}
            className="press flex items-center gap-2.5 rounded-lg py-1 pl-1 pr-2 transition-colors hover:bg-ink-100"
          >
            <Avatar initials={user.initials} size="sm" gradient={user.accent} />
            <div className="hidden text-left md:block">
              <p className="max-w-[150px] truncate text-[12.5px] font-semibold leading-tight text-ink-900">
                {user.name}
              </p>
              <p className="max-w-[150px] truncate text-[10.5px] text-ink-500">{user.title}</p>
            </div>
            <ChevronDown className={cn('h-3.5 w-3.5 text-ink-400 transition-transform', userOpen && 'rotate-180')} />
          </button>

          {userOpen && (
            <div className="modal-in fixed inset-x-3 top-[64px] z-50 overflow-hidden rounded-xl border border-ink-200/70 bg-white shadow-float sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-2 sm:w-72">
              <div className="border-b border-ink-100 bg-ink-50/60 p-4">
                <div className="flex items-center gap-3">
                  <Avatar initials={user.initials} size="md" gradient={user.accent} />
                  <div className="min-w-0">
                    <p className="truncate text-[13.5px] font-semibold text-ink-900">{user.name}</p>
                    <p className="truncate text-[11.5px] text-ink-500">{user.email}</p>
                  </div>
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <Badge tone="active" size="sm">
                    {user.title}
                  </Badge>
                </div>
              </div>

              <div className="p-1.5">
                <button
                  onClick={() => {
                    go('settings');
                    setUserOpen(false);
                  }}
                  className="flex min-h-[44px] w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[14px] font-medium text-ink-700 transition-colors hover:bg-ink-100"
                >
                  <Sliders className="h-4 w-4 text-ink-400" /> Interface settings
                </button>
                <button
                  onClick={() => {
                    go('access');
                    setUserOpen(false);
                  }}
                  className="flex min-h-[44px] w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[14px] font-medium text-ink-700 transition-colors hover:bg-ink-100"
                >
                  <ShieldCheck className="h-4 w-4 text-ink-400" /> My permissions
                </button>
                <button
                  onClick={logout}
                  className="flex min-h-[44px] w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-[14px] font-medium text-ink-700 transition-colors hover:bg-rose-50 hover:text-rose-700"
                >
                  <LogOut className="h-4 w-4 text-ink-400" /> Sign out
                </button>

                <div className="my-1 h-px bg-ink-100" />

                <div className="flex items-center gap-1.5 px-2.5 py-2">
                  <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-brand-600" />
                  <span className="text-[12px] text-ink-500">Secure session · all access logged</span>
                </div>
                <div className="px-2.5 pb-1.5">
                  <p className="text-[10.5px] uppercase tracking-wider text-ink-400">Staff ID</p>
                  <p className="tnum text-[12px] font-medium text-ink-700">{user.id}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
