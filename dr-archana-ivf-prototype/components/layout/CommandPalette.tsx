'use client';

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useApp, type ScreenId } from '@/lib/store';
import { PATIENTS, EMBRYOS } from '@/lib/data';
import { navForRole } from './nav';
import { cn } from '@/lib/utils';
import { Search, CornerDownLeft, Users, Microscope, ArrowRight, Sliders } from 'lucide-react';
import { Avatar } from '@/components/ui/primitives';

interface Result {
  id: string;
  label: string;
  hint: string;
  group: string;
  icon?: any;
  initials?: string;
  run: () => void;
}

export function CommandPalette() {
  const { paletteOpen, setPaletteOpen, go, role, toast, permissions } = useApp();
  const [q, setQ] = useState('');
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (paletteOpen) {
      setQ('');
      setCursor(0);
      setTimeout(() => inputRef.current?.focus(), 40);
    }
  }, [paletteOpen]);

  const results = useMemo<Result[]>(() => {
    if (!role) return [];
    const nav = navForRole(role, permissions).map((n) => ({
      id: `nav-${n.id}`,
      label: n.label,
      hint: n.section,
      group: 'Navigate',
      icon: n.icon,
      run: () => go(n.id as ScreenId),
    }));

    // Interface settings have no menu entry (they live in the user menu),
    // so the palette is the other way staff find them by name.
    nav.push({
      id: 'nav-settings',
      label: 'Interface Settings',
      hint: 'Text size, density, contrast',
      group: 'Navigate',
      icon: Sliders,
      run: () => go('settings' as ScreenId),
    });

    const patients = PATIENTS.map((p) => ({
      id: `pat-${p.id}`,
      label: p.name,
      hint: `${p.id} · ${p.stage}`,
      group: 'Patients',
      initials: p.initials,
      run: () => {
        if (p.id === 'DAIVF-2026-00428') go('workspace');
        else toast({ title: p.name, body: `Opening record ${p.id}.`, tone: 'info' });
      },
    }));

    const embryos = EMBRYOS.map((e) => ({
      id: `emb-${e.id}`,
      label: `Embryo ${e.id} — Grade ${e.grade}`,
      hint: `Day ${e.day} · ${e.status}`,
      group: 'Embryology',
      icon: Microscope,
      run: () => go('embryology'),
    }));

    const all = [...nav, ...patients, ...embryos];
    if (!q.trim()) return all.slice(0, 9);
    const term = q.toLowerCase();
    return all
      .filter((r) => r.label.toLowerCase().includes(term) || r.hint.toLowerCase().includes(term))
      .slice(0, 12);
  }, [q, role, go, toast, permissions]);

  useEffect(() => setCursor(0), [q]);

  useEffect(() => {
    if (!paletteOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPaletteOpen(false);
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setCursor((c) => Math.min(c + 1, results.length - 1));
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setCursor((c) => Math.max(c - 1, 0));
      }
      if (e.key === 'Enter' && results[cursor]) {
        e.preventDefault();
        results[cursor].run();
        setPaletteOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [paletteOpen, results, cursor, setPaletteOpen]);

  if (!paletteOpen) return null;

  let lastGroup = '';

  return (
    <div className="fixed inset-0 z-[150] flex items-start justify-center px-3 pt-[10vh] sm:px-6 sm:pt-[14vh]">
      <div className="absolute inset-0 animate-fade-in bg-ink-950/25 backdrop-blur-[3px]" onClick={() => setPaletteOpen(false)} />
      <div className="modal-in relative w-full max-w-[600px] overflow-hidden rounded-2xl border border-ink-200/60 bg-white shadow-pop">
        <div className="flex items-center gap-3 border-b border-ink-100 px-4">
          <Search className="h-4 w-4 shrink-0 text-ink-400" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search patients, screens, embryos…"
            className="h-14 flex-1 border-0 bg-transparent text-[14.5px] text-ink-900 placeholder:text-ink-400 focus:outline-none focus:ring-0"
            style={{ boxShadow: 'none' }}
          />
          <kbd className="rounded border border-ink-200 bg-ink-50 px-1.5 py-0.5 font-mono text-[11.5px] text-ink-400">
            ESC
          </kbd>
        </div>

        <div className="scroll-area max-h-[380px] p-2">
          {results.length === 0 && (
            <div className="px-3 py-10 text-center">
              <p className="text-[14.5px] text-ink-500">No results for “{q}”</p>
              <p className="mt-1 text-[13px] text-ink-400">Try a patient name, screen or embryo ID.</p>
            </div>
          )}
          {results.map((r, i) => {
            const showGroup = r.group !== lastGroup;
            lastGroup = r.group;
            const Icon = r.icon;
            const active = i === cursor;
            return (
              <div key={r.id}>
                {showGroup && (
                  <p className="px-2.5 pb-1 pt-3 text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-400 first:pt-1">
                    {r.group}
                  </p>
                )}
                <button
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => {
                    r.run();
                    setPaletteOpen(false);
                  }}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-lg px-2.5 py-2.5 text-left transition-colors',
                    active ? 'bg-brand-50' : 'hover:bg-ink-50'
                  )}
                >
                  {r.initials ? (
                    <Avatar initials={r.initials} size="xs" gradient="from-ink-400 to-ink-600" />
                  ) : Icon ? (
                    <div className={cn('flex h-6 w-6 items-center justify-center rounded-md', active ? 'bg-brand-100 text-brand-700' : 'bg-ink-100 text-ink-500')}>
                      <Icon className="h-3.5 w-3.5" />
                    </div>
                  ) : (
                    <Users className="h-4 w-4 text-ink-400" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className={cn('truncate text-[14.5px] font-medium', active ? 'text-brand-900' : 'text-ink-800')}>
                      {r.label}
                    </p>
                    <p className="truncate text-[12.5px] text-ink-400">{r.hint}</p>
                  </div>
                  {active && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-brand-600" />}
                </button>
              </div>
            );
          })}
        </div>

        <div className="flex items-center justify-between border-t border-ink-100 bg-ink-50/60 px-4 py-2.5">
          <div className="flex items-center gap-3 text-[12px] text-ink-400">
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-ink-200 bg-white px-1 py-0.5 font-mono text-[9.5px]">↑↓</kbd> navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="rounded border border-ink-200 bg-white px-1 py-0.5 font-mono text-[9.5px]">↵</kbd> open
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-[12px] font-medium text-brand-700">
            <ArrowRight className="h-3 w-3" /> {results.length} results
          </div>
        </div>
      </div>
    </div>
  );
}
