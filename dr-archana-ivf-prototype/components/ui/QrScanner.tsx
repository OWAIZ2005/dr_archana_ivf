'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import QrScanner from 'qr-scanner';
import { AlertTriangle, X } from 'lucide-react';

// Safari on iOS/iPadOS has no usable native barcode API (the Shape Detection
// API's BarcodeDetector never shipped there, even behind a flag as of 2026 —
// confirmed before building this), so this decodes frames in a dedicated
// worker via qr-scanner instead. That worker is a standalone script, not
// something webpack can bundle — see scripts/copy-qr-scanner-worker.js,
// which copies it into public/ on every `npm install` so it's never
// silently missing from a fresh checkout or a Docker build.
QrScanner.WORKER_PATH = '/qr-scanner-worker.min.js';

type Props = {
  /** Called once per successful decode. The parent owns what happens next
   *  (resolve the token, close the scanner) — this component never
   *  interprets the decoded text itself. */
  onDecode: (text: string) => void;
  onClose: () => void;
};

/** A full-screen-ish live camera QR scanner. Kept deliberately separate from
 * PhotoCapture (which captures one still frame) rather than generalized into
 * a single component — a continuous decode loop with worker-thread frames
 * is a different lifecycle from "open camera, take one photo, stop". */
export function QrScannerView({ onDecode, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const scannerRef = useRef<QrScanner | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const handleDecode = useCallback(
    (result: QrScanner.ScanResult) => {
      onDecode(result.data);
    },
    [onDecode]
  );

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let cancelled = false;
    const scanner = new QrScanner(video, handleDecode, {
      onDecodeError: () => {
        // Fires continuously while no code is in frame — expected, not an error state.
      },
      preferredCamera: 'environment',
      highlightScanRegion: true,
      highlightCodeOutline: true,
      maxScansPerSecond: 5,
    });
    scannerRef.current = scanner;

    scanner
      .start()
      .then(() => {
        if (!cancelled) setReady(true);
      })
      .catch(() => {
        if (!cancelled) setError('Camera permission was denied, or no camera is available on this device.');
      });

    return () => {
      cancelled = true;
      scanner.stop();
      scanner.destroy();
      scannerRef.current = null;
    };
  }, [handleDecode]);

  return (
    <div className="fixed inset-0 z-[110] flex flex-col bg-ink-950">
      <div className="flex items-center justify-between p-4">
        <p className="text-[14.5px] font-medium text-white">Scan asset QR code</p>
        <button
          onClick={onClose}
          aria-label="Close scanner"
          className="flex h-11 w-11 items-center justify-center rounded-lg text-white/80 hover:bg-white/10"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="relative flex-1">
        <video ref={videoRef} playsInline muted className="h-full w-full object-cover" />
        {!ready && !error && (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-[13.5px] text-white/70">Starting camera…</p>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <div className="flex max-w-sm flex-col items-center gap-2 rounded-xl bg-white p-5 text-center">
              <AlertTriangle className="h-5 w-5 text-rose-600" />
              <p className="text-[13.5px] text-ink-700">{error}</p>
              <p className="text-[12.5px] text-ink-500">Use "Scan / enter QR token" below instead.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
