'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Check, PenLine, RotateCcw, X } from 'lucide-react';
import { Button } from '@/components/ui/primitives';

type Props = {
  /** Stable id prefix for the control's heading (must be unique per signer). */
  idPrefix: string;
  /** Visible label, e.g. "Patient signature" or "Witness — Embryologist". */
  label: string;
  /** Currently captured signature, or null. Owned by the parent so it
   *  survives step navigation, same convention as PhotoCapture's `value`. */
  value: File | null;
  onChange: (file: File | null) => void;
};

/**
 * A signature pad built on the Pointer Events API — not a canvas drawing
 * library — so it picks up real Apple Pencil pressure (`event.pressure`)
 * and tilt for free on iPad, while still working with a finger or a mouse
 * (both report a fixed 0.5 pressure while a button/contact is down, so the
 * stroke stays a normal constant width for them). `pointerType` is read
 * only to decide stroke-width sensitivity, never to block input — a
 * clinician without a Pencil handy must still be able to sign.
 *
 * Mirrors PhotoCapture's prop shape (idPrefix/label/value/onChange) and its
 * captured/uncaptured two-state layout, since this is the same kind of
 * control: draw or capture, preview, redo, remove.
 */
export function SignatureCapture({ idPrefix, label, value, onChange }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawingRef = useRef(false);
  const lastPointRef = useRef<{ x: number; y: number } | null>(null);
  const [hasStroke, setHasStroke] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Keep an object URL for the saved signature; revoke it when it changes.
  useEffect(() => {
    if (!value) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(value);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [value]);

  // Backing store sized in real device pixels (devicePixelRatio) so a
  // Pencil's fine lines stay crisp on a Retina iPad instead of blurring —
  // the CSS size stays the logical 100% width x 160px the layout expects.
  const sizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.scale(dpr, dpr);
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = '#1c1917';
    }
  }, []);

  useEffect(() => {
    if (value) return; // no live pad to size while showing a saved preview
    sizeCanvas();
    window.addEventListener('resize', sizeCanvas);
    return () => window.removeEventListener('resize', sizeCanvas);
  }, [value, sizeCanvas]);

  const clear = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (canvas && ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasStroke(false);
    setError(null);
  }, []);

  const pointerDown = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.setPointerCapture(e.pointerId);
    drawingRef.current = true;
    const rect = canvas.getBoundingClientRect();
    lastPointRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    setHasStroke(true);
  }, []);

  const pointerMove = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    const last = lastPointRef.current;
    if (!canvas || !ctx || !last) return;

    const rect = canvas.getBoundingClientRect();
    const point = { x: e.clientX - rect.left, y: e.clientY - rect.top };

    // event.pressure defaults to 0.5 for touch/mouse (no pressure sensor),
    // and a real 0-1 value for a Pencil — so this only varies stroke width
    // when pressure-sensitive input is actually present.
    const pressure = e.pressure > 0 ? e.pressure : 0.5;
    ctx.lineWidth = 1.5 + pressure * 2.5;

    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
    lastPointRef.current = point;
  }, []);

  const pointerUp = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    drawingRef.current = false;
    lastPointRef.current = null;
    canvasRef.current?.releasePointerCapture(e.pointerId);
  }, []);

  const save = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !hasStroke) return;
    canvas.toBlob((blob) => {
      if (!blob) {
        setError('Could not save the signature — try again.');
        return;
      }
      onChange(new File([blob], `${idPrefix}-signature.png`, { type: 'image/png' }));
    }, 'image/png');
  }, [hasStroke, idPrefix, onChange]);

  const redo = useCallback(() => {
    onChange(null);
    setHasStroke(false);
  }, [onChange]);

  const headingId = `${idPrefix}-signature-heading`;

  return (
    <section aria-labelledby={headingId} className="rounded-xl border border-ink-200 bg-white p-4">
      <p id={headingId} className="mb-3 flex items-center gap-1.5 text-[13.5px] font-semibold text-ink-900">
        <PenLine className="h-3.5 w-3.5 text-ink-400" /> {label}
      </p>

      {value && previewUrl ? (
        <div className="space-y-3">
          <div className="flex items-center justify-center rounded-xl border border-ink-100 bg-ink-50/60 p-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previewUrl} alt={`Captured signature: ${label}`} className="h-24 max-w-full object-contain" />
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-emerald-700">
              <Check className="h-3.5 w-3.5" /> Signature captured
            </span>
            <Button type="button" size="sm" variant="ghost" icon={<RotateCcw className="h-3.5 w-3.5" />} onClick={redo}>
              Redo
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <canvas
            ref={canvasRef}
            role="img"
            aria-label={`${label} — draw your signature here with a finger, stylus or Apple Pencil`}
            onPointerDown={pointerDown}
            onPointerMove={pointerMove}
            onPointerUp={pointerUp}
            onPointerCancel={pointerUp}
            className="h-[160px] w-full touch-none rounded-xl border border-dashed border-ink-300 bg-ink-50/40"
          />
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="primary" disabled={!hasStroke} onClick={save} icon={<Check className="h-3.5 w-3.5" />}>
              Save signature
            </Button>
            <Button type="button" size="sm" variant="ghost" disabled={!hasStroke} icon={<X className="h-3.5 w-3.5" />} onClick={clear}>
              Clear
            </Button>
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2.5 text-[12.5px] text-rose-700">
          {error}
        </p>
      )}
    </section>
  );
}
