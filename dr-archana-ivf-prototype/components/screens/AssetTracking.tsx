'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  Boxes,
  CheckCircle2,
  Download,
  History,
  MapPin,
  Move,
  Plus,
  Printer,
  QrCode,
  Search,
} from 'lucide-react';

import { Badge, Button, Card, CardHeader, Field, InfoNote, Input, Modal, SectionTitle, Select } from '@/components/ui/primitives';
import { useApp } from '@/lib/store';
import { ApiError, apiFetchBlob } from '@/lib/api/client';
import {
  assetQrPreviewPath,
  openAssetLabel,
  resolveAssetQr,
  useAsset,
  useAssetHistory,
  useAssets,
  useCreateAsset,
  useCreateLocation,
  useLocations,
  useMoveAsset,
  type AssetOut,
  type AssetStatus,
  type AssetMovementOut,
} from '@/lib/api/assets';

const STATUS_LABEL: Record<AssetStatus, string> = {
  active: 'Active',
  under_maintenance: 'Under maintenance',
  sent_for_service: 'Sent for service',
  retired: 'Retired',
};
const STATUS_TONE: Record<AssetStatus, 'completed' | 'attention' | 'critical' | 'neutral'> = {
  active: 'completed',
  under_maintenance: 'attention',
  sent_for_service: 'attention',
  retired: 'neutral',
};

function fmt(iso: string | null): string {
  return iso
    ? new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : '—';
}

// =========================================================================
// Screen router: list vs detail vs a pending QR scan
// =========================================================================

export function AssetTracking() {
  const { selectedAssetId, scanMode, openScannedAsset, scanToken, clearScanToken } = useApp();

  // A phone camera opened the app at #scan=<token>. Resolve it once through
  // the existing endpoint, then show the lightweight mobile scan page. A bad
  // token lands on the same page in its "Asset not found" state.
  useEffect(() => {
    if (!scanToken) return;
    let cancelled = false;
    resolveAssetQr(scanToken)
      .then((asset) => { if (!cancelled) openScannedAsset(asset.id); })
      .catch(() => { if (!cancelled) openScannedAsset(null); })
      .finally(() => { if (!cancelled) clearScanToken(); });
    return () => { cancelled = true; };
  }, [scanToken, openScannedAsset, clearScanToken]);

  if (scanMode) return <MobileAssetScan assetId={selectedAssetId} />;
  if (selectedAssetId) return <AssetDetail assetId={selectedAssetId} />;
  return <AssetList />;
}

// =========================================================================
// Mobile QR-scan page — the lightweight view a phone shows after scanning an
// asset sticker. NOT the desktop dashboard: just the current location and,
// for users with `assets.move`, a simple move form. All data comes from the
// existing endpoints (`/assets/resolve`, `/assets/{id}`, `/assets/{id}/history`,
// `/assets/{id}/move`); nothing here is a second asset/movement system.
// =========================================================================

function MobileAssetScan({ assetId }: { assetId: string | null }) {
  const { can, role, exitScanMode, openAsset, toast } = useApp();
  const assetQuery = useAsset(assetId);
  const historyQuery = useAssetHistory(assetId);
  const locationsQuery = useLocations();
  const moveAsset = useMoveAsset();

  const [showMove, setShowMove] = useState(false);
  const [toId, setToId] = useState('');
  const [note, setNote] = useState('');
  const [moveError, setMoveError] = useState<string | null>(null);
  const [justMoved, setJustMoved] = useState<{ name: string; at: string } | null>(null);

  // Re-scanning a different sticker (or the same one afresh) starts clean.
  useEffect(() => {
    setShowMove(false);
    setToId('');
    setNote('');
    setMoveError(null);
    setJustMoved(null);
  }, [assetId]);

  const asset = assetQuery.data ?? null;
  const history = historyQuery.data ?? [];
  const lastMove = history.length ? history[history.length - 1] : null;
  const loc = asset?.current_location ?? null;

  const notFound =
    assetId === null ||
    (assetQuery.isError && assetQuery.error instanceof ApiError && assetQuery.error.status === 404);
  const isRetired = asset?.status === 'retired';
  const canMove = can('assets.move') && !isRetired;

  const moveOptions = useMemo(
    () => (locationsQuery.data ?? []).filter((l) => l.id !== loc?.id),
    [locationsQuery.data, loc?.id]
  );

  const shell = (children: React.ReactNode) => (
    <div className="screen-enter mx-auto max-w-md space-y-4 p-4 sm:p-6">{children}</div>
  );

  if (notFound) {
    return shell(
      <Card className="p-6 text-center">
        <QrCode className="mx-auto h-10 w-10 text-ink-300" />
        <h1 className="mt-3 text-[18px] font-semibold text-ink-900">Asset not found.</h1>
        <p className="mt-1 text-[14px] text-ink-500">
          This QR code is not recognised. Check that you scanned an asset sticker from this system.
        </p>
        {role === 'management' && (
          <Button className="mt-5 w-full" variant="secondary" onClick={() => { exitScanMode(); openAsset(null); }}>
            Go to Asset Tracking
          </Button>
        )}
      </Card>
    );
  }

  if (assetQuery.isLoading || !asset) {
    if (assetQuery.isError) {
      const forbidden = assetQuery.error instanceof ApiError && assetQuery.error.status === 403;
      return shell(
        <Card className="p-6 text-center">
          <h1 className="text-[17px] font-semibold text-ink-900">
            {forbidden ? 'No access to assets' : 'Can’t reach the system'}
          </h1>
          <p className="mt-1 text-[14px] text-ink-500">
            {forbidden
              ? 'Your account cannot view the asset register. Ask an administrator if you need access.'
              : 'The clinical system is unavailable right now. Check your connection and try again.'}
          </p>
          {!forbidden && (
            <Button className="mt-5 w-full" variant="secondary" onClick={() => assetQuery.refetch()}>
              Retry
            </Button>
          )}
        </Card>
      );
    }
    return shell(<Card className="p-8 text-center text-[14px] text-ink-500">Loading asset…</Card>);
  }

  return shell(
    <>
      {/* Identity */}
      <div>
        <h1 className="text-[22px] font-semibold leading-tight text-ink-900">{asset.name}</h1>
        <p className="tnum mt-1 text-[14px] font-medium text-ink-500">{asset.asset_code}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Badge tone={STATUS_TONE[asset.status]} size="sm">{STATUS_LABEL[asset.status]}</Badge>
          {asset.category && <span className="text-[13px] text-ink-500">{asset.category}</span>}
        </div>
      </div>

      {/* Current location — the whole point of the page */}
      <Card className="border-brand-200/70 bg-brand-50/50 p-4">
        <p className="text-[12px] font-semibold uppercase tracking-[0.09em] text-brand-700">Current location</p>
        <p className="mt-1 flex items-center gap-2 text-[20px] font-semibold text-ink-900">
          <MapPin className="h-5 w-5 shrink-0 text-brand-600" />
          {loc?.name ?? 'Not set'}
        </p>
        {loc && (loc.building || loc.floor) && (
          <p className="mt-1 text-[13.5px] text-ink-600">
            {[loc.building, loc.floor && `Floor ${loc.floor}`].filter(Boolean).join(' · ')}
          </p>
        )}
        <p className="mt-2 text-[12.5px] text-ink-500">
          Last updated {fmt(asset.updated_at)}
          {lastMove?.moved_by_name ? ` · by ${lastMove.moved_by_name}` : ''}
        </p>
      </Card>

      {/* Move outcome */}
      {justMoved && (
        <Card className="flex items-start gap-3 border-emerald-200 bg-emerald-50/70 p-4">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
          <div>
            <p className="text-[15px] font-semibold text-emerald-900">Location updated</p>
            <p className="mt-0.5 text-[13.5px] text-emerald-800">
              Now at <span className="font-semibold">{justMoved.name}</span> · {fmt(justMoved.at)}
            </p>
          </div>
        </Card>
      )}

      {/* Move action / form */}
      {canMove ? (
        !showMove ? (
          <Button className="w-full" variant="primary" icon={<Move className="h-4 w-4" />} onClick={() => setShowMove(true)}>
            Move Asset
          </Button>
        ) : (
          <Card className="space-y-4 p-4">
            <Field label="Current location" value={loc?.name ?? 'Not set'} />
            <Select label="New location" value={toId} onChange={(e) => setToId(e.target.value)}>
              <option value="">Select a location…</option>
              {moveOptions.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </Select>
            <label className="block">
              <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Note (optional)</span>
              <textarea
                className="min-h-[72px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[15px] text-ink-900"
                placeholder="Reason / who requested the move…"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
            {moveError && <p className="text-[13px] text-rose-600">{moveError}</p>}
            <div className="flex gap-2">
              <Button variant="ghost" className="flex-1" onClick={() => { setShowMove(false); setToId(''); setNote(''); setMoveError(null); }}>
                Cancel
              </Button>
              <Button
                variant="primary"
                className="flex-1"
                disabled={!toId || moveAsset.isPending}
                loading={moveAsset.isPending}
                onClick={() => {
                  setMoveError(null);
                  moveAsset.mutate(
                    { assetId: asset.id, to_location_id: toId, note: note.trim() || null },
                    {
                      onSuccess: (a) => {
                        setShowMove(false);
                        setToId('');
                        setNote('');
                        setJustMoved({ name: a.current_location?.name ?? '—', at: a.updated_at });
                        toast({ title: `Moved to ${a.current_location?.name}`, tone: 'success' });
                      },
                      onError: (e) => setMoveError(e instanceof ApiError ? e.message : 'Could not record the move.'),
                    }
                  );
                }}
              >
                Confirm Move
              </Button>
            </div>
          </Card>
        )
      ) : (
        <InfoNote>
          {isRetired
            ? 'This asset is retired and cannot be moved.'
            : 'You can view this asset’s location. Recording a move requires the asset-move permission.'}
        </InfoNote>
      )}

      {/* Optional deep link to the full Amazon-style journey — reuses the
          existing desktop detail screen, no second history view. Only for
          users whose role can open the desktop Asset Tracking module. */}
      {role === 'management' && (
        <button
          onClick={() => exitScanMode()}
          className="flex w-full items-center justify-center gap-1.5 py-2 text-[13.5px] font-medium text-ink-600 hover:text-ink-900"
        >
          <History className="h-4 w-4" /> View location history
        </button>
      )}
    </>
  );
}

// =========================================================================
// List / search
// =========================================================================

function AssetList() {
  const { openAsset } = useApp();
  const [q, setQ] = useState('');
  const [locationId, setLocationId] = useState('');
  const [status, setStatus] = useState<'' | AssetStatus>('');
  const [category, setCategory] = useState('');
  const [scanValue, setScanValue] = useState('');
  const [addAssetOpen, setAddAssetOpen] = useState(false);
  const [addLocationOpen, setAddLocationOpen] = useState(false);

  const locationsQuery = useLocations();
  const assetsQuery = useAssets({
    q: q.trim() || undefined,
    location_id: locationId || undefined,
    status: status || undefined,
    category: category.trim() || undefined,
  });

  const openByToken = async () => {
    const token = scanValue.trim();
    if (!token) return;
    try {
      const asset = await resolveAssetQr(token);
      openAsset(asset.id);
    } catch {
      // surfaced by the caller's toast in the screen router path; here keep simple
      setScanValue('');
    }
  };

  return (
    <div className="screen-enter mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6 lg:p-8">
      <AddAssetModal open={addAssetOpen} onClose={() => setAddAssetOpen(false)} />
      <AddLocationModal open={addLocationOpen} onClose={() => setAddLocationOpen(false)} />

      <SectionTitle
        eyebrow="Management"
        title="Asset & Item Tracking"
        description="Register a physical item, print its QR sticker, and record every location change. Search any asset to see where it is right now and its full location history."
      />

      <Card>
        <div className="flex flex-col gap-3 p-4 sm:p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
            <div className="flex-1">
              <Input
                label="Search"
                icon={<Search className="h-4 w-4" />}
                placeholder="Asset name, code or serial number…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>
            <div className="sm:w-56">
              <Select label="Location" value={locationId} onChange={(e) => setLocationId(e.target.value)}>
                <option value="">All locations</option>
                {(locationsQuery.data ?? []).map((l) => (
                  <option key={l.id} value={l.id}>{l.name}</option>
                ))}
              </Select>
            </div>
            <div className="sm:w-44">
              <Select label="Status" value={status} onChange={(e) => setStatus(e.target.value as '' | AssetStatus)}>
                <option value="">Any status</option>
                {(Object.keys(STATUS_LABEL) as AssetStatus[]).map((s) => (
                  <option key={s} value={s}>{STATUS_LABEL[s]}</option>
                ))}
              </Select>
            </div>
            <div className="sm:w-44">
              <Input label="Category" placeholder="e.g. Laptop" value={category} onChange={(e) => setCategory(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-3 border-t border-ink-100 pt-3 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex items-end gap-2">
              <div className="sm:w-72">
                <Input
                  label="Scan / enter QR token"
                  icon={<QrCode className="h-4 w-4" />}
                  placeholder="Paste a scanned QR value"
                  value={scanValue}
                  onChange={(e) => setScanValue(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && openByToken()}
                />
              </div>
              <Button variant="secondary" onClick={openByToken} disabled={!scanValue.trim()}>Open</Button>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" icon={<MapPin className="h-4 w-4" />} onClick={() => setAddLocationOpen(true)}>
                Add Location
              </Button>
              <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => setAddAssetOpen(true)}>
                Add Asset
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="hidden grid-cols-[2fr_1fr_1fr_1.4fr_1.2fr_110px] gap-4 border-b border-ink-200/70 bg-ink-50/60 px-5 py-2.5 md:grid">
          {['Asset', 'Code', 'Category', 'Current Location', 'Last Updated', 'Status'].map((h) => (
            <span key={h} className="text-[12px] font-semibold uppercase tracking-[0.09em] text-ink-400">{h}</span>
          ))}
        </div>
        {assetsQuery.isLoading ? (
          <p className="px-5 py-10 text-center text-[14px] text-ink-500">Loading assets…</p>
        ) : (assetsQuery.data ?? []).length === 0 ? (
          <p className="px-5 py-10 text-center text-[14px] text-ink-500">
            No assets match. Click <span className="font-medium">Add Asset</span> to register one.
          </p>
        ) : (
          <div className="stagger">
            {(assetsQuery.data ?? []).map((a: AssetOut, i) => (
              <button
                key={a.id}
                style={{ ['--i' as string]: i }}
                onClick={() => openAsset(a.id)}
                className="flex w-full flex-col gap-1.5 border-b border-ink-100 px-4 py-3 text-left last:border-0 hover:bg-ink-50/60 sm:px-5 md:grid md:grid-cols-[2fr_1fr_1fr_1.4fr_1.2fr_110px] md:items-center md:gap-4"
              >
                <span className="text-[14px] font-semibold text-ink-900">{a.name}</span>
                <span className="tnum text-[13px] text-ink-600">{a.asset_code}</span>
                <span className="text-[13px] text-ink-500">{a.category ?? '—'}</span>
                <span className="flex items-center gap-1.5 text-[13px] text-ink-700">
                  <MapPin className="h-3.5 w-3.5 text-brand-600" /> {a.current_location?.name ?? '—'}
                </span>
                <span className="text-[13px] text-ink-500">{fmt(a.updated_at)}</span>
                <Badge tone={STATUS_TONE[a.status]} size="sm">{STATUS_LABEL[a.status]}</Badge>
              </button>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

// =========================================================================
// Detail + Amazon-style location journey
// =========================================================================

function AssetDetail({ assetId }: { assetId: string }) {
  const { openAsset, toast } = useApp();
  const assetQuery = useAsset(assetId);
  const historyQuery = useAssetHistory(assetId);
  const [moveOpen, setMoveOpen] = useState(false);
  const [qrUrl, setQrUrl] = useState<string | null>(null);

  useEffect(() => {
    let url: string | null = null;
    apiFetchBlob(assetQrPreviewPath(assetId))
      .then((b) => { url = URL.createObjectURL(b); setQrUrl(url); })
      .catch(() => setQrUrl(null));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [assetId]);

  const asset = assetQuery.data;
  const loc = asset?.current_location ?? null;
  const history = historyQuery.data ?? [];

  return (
    <div className="screen-enter mx-auto max-w-[1100px] space-y-5 p-4 sm:p-6 lg:p-8">
      {asset && <MoveAssetModal asset={asset} open={moveOpen} onClose={() => setMoveOpen(false)} />}

      <button onClick={() => openAsset(null)} className="flex items-center gap-1.5 text-[13.5px] font-medium text-ink-600 hover:text-ink-900">
        <ArrowLeft className="h-4 w-4" /> All assets
      </button>

      {assetQuery.isLoading || !asset ? (
        <Card className="p-8 text-center text-[14px] text-ink-500">Loading asset…</Card>
      ) : (
        <>
          {/* Header + current location, visually prominent */}
          <Card className="overflow-hidden">
            <div className="relative">
              <div className="absolute inset-x-0 top-0 h-[68px] bg-gradient-to-r from-brand-50 via-emerald-50/60 to-transparent" />
              <div className="relative flex flex-wrap items-start justify-between gap-4 p-4 sm:p-5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <h1 className="tracking-display text-[20px] font-semibold text-ink-900 sm:text-[22px]">{asset.name}</h1>
                    <Badge tone={STATUS_TONE[asset.status]} size="sm">{STATUS_LABEL[asset.status]}</Badge>
                  </div>
                  <p className="tnum mt-1 text-[13.5px] font-medium text-ink-500">{asset.asset_code}</p>
                  <div className="mt-3.5 inline-flex items-start gap-3 rounded-xl border border-brand-200/70 bg-brand-50/60 px-3.5 py-2.5">
                    <MapPin className="mt-0.5 h-4 w-4 text-brand-600" />
                    <div>
                      <p className="text-[11.5px] font-semibold uppercase tracking-[0.09em] text-brand-700">Current location</p>
                      <p className="mt-0.5 text-[15px] font-semibold text-ink-900">{loc?.name ?? 'Not set'}</p>
                      <p className="mt-0.5 text-[12.5px] text-ink-500">
                        Last updated {fmt(asset.updated_at)}
                        {history[history.length - 1]?.moved_by_name ? ` · by ${history[history.length - 1]?.moved_by_name}` : ''}
                      </p>
                    </div>
                  </div>
                </div>
                <Button
                  variant="primary"
                  icon={<Move className="h-4 w-4" />}
                  onClick={() => setMoveOpen(true)}
                  className="w-full sm:w-auto"
                >
                  Move Asset
                </Button>
              </div>
            </div>
          </Card>

          <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
            {/* Asset information */}
            <Card>
              <CardHeader icon={<Boxes className="h-4 w-4" />} title="Asset information" />
              <div className="grid gap-3 px-5 pb-5 sm:grid-cols-2">
                <Field label="Category" value={asset.category ?? '—'} />
                <Field label="Status" value={STATUS_LABEL[asset.status]} />
                <Field label="Make" value={asset.brand ?? '—'} />
                <Field label="Model" value={asset.model ?? '—'} />
                <Field label="Serial number" value={asset.serial_number ?? '—'} />
                <Field label="Registered" value={fmt(asset.created_at)} />
              </div>
            </Card>

            {/* QR */}
            <Card>
              <CardHeader icon={<QrCode className="h-4 w-4" />} title="QR label" subtitle="Permanent — never changes when the asset moves." />
              <div className="flex flex-col items-center gap-3 px-5 pb-5">
                {qrUrl ? (
                  <img src={qrUrl} alt="Asset QR code" className="h-40 w-40 rounded-lg border border-ink-200 bg-white p-2" />
                ) : (
                  <div className="h-40 w-40 animate-pulse rounded-lg bg-ink-100" />
                )}
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    icon={<Printer className="h-3.5 w-3.5" />}
                    onClick={() => openAssetLabel(asset.id).catch(() => toast({ title: 'Could not open the label PDF', tone: 'error' }))}
                  >
                    Print label
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<Download className="h-3.5 w-3.5" />}
                    onClick={() => openAssetLabel(asset.id).catch(() => toast({ title: 'Could not open the label PDF', tone: 'error' }))}
                  >
                    Download
                  </Button>
                </div>
              </div>
            </Card>
          </div>

          {/* Current location detail */}
          {loc && (
            <Card>
              <CardHeader icon={<MapPin className="h-4 w-4" />} title={`Location — ${loc.name}`} />
              <div className="grid gap-3 px-5 pb-5 sm:grid-cols-3">
                <Field label="Building" value={loc.building ?? '—'} />
                <Field label="Floor" value={loc.floor ?? '—'} />
                <Field label="In-charge" value={loc.in_charge ?? '—'} />
                <Field label="Phone" value={loc.phone ?? '—'} />
                <div className="sm:col-span-3">
                  <Field label="Description" value={loc.description ?? '—'} />
                </div>
              </div>
            </Card>
          )}

          {/* Amazon-style location journey */}
          <Card>
            <CardHeader icon={<MapPin className="h-4 w-4" />} title="Location journey" subtitle="Every physical move, newest at the top." />
            <div className="px-5 pb-5">
              {historyQuery.isLoading ? (
                <p className="py-6 text-center text-[14px] text-ink-500">Loading history…</p>
              ) : history.length === 0 ? (
                <InfoNote>No movement records yet.</InfoNote>
              ) : (
                <LocationJourney history={history} />
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function LocationJourney({ history }: { history: AssetMovementOut[] }) {
  const rows = [...history].reverse(); // newest first
  return (
    <ol className="relative ml-1.5">
      {rows.map((m, i) => {
        const isCurrent = i === 0;
        return (
          <li key={m.id} className="relative pl-7 pb-6 last:pb-0">
            {i < rows.length - 1 && <span className="absolute left-[7px] top-4 h-full w-[2px] bg-ink-200" />}
            <span
              className={
                'absolute left-0 top-1.5 h-3.5 w-3.5 rounded-full ring-4 ring-white ' +
                (isCurrent ? 'bg-brand-600' : 'bg-ink-300')
              }
            />
            <p className="text-[14px] font-semibold text-ink-900">
              {m.to_location?.name ?? '—'}
              {isCurrent && (
                <span className="ml-2 rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-brand-700">
                  Current location
                </span>
              )}
            </p>
            <p className="tnum mt-0.5 text-[12.5px] text-ink-500">{fmt(m.moved_at)}</p>
            <p className="mt-0.5 text-[13px] text-ink-600">
              {m.event_type === 'register'
                ? 'Asset registered'
                : `Moved from ${m.from_location?.name ?? '—'}`}
              {m.moved_by_name ? ` · by ${m.moved_by_name}` : ''}
            </p>
            {m.note && <p className="mt-0.5 text-[12.5px] italic text-ink-500">“{m.note}”</p>}
          </li>
        );
      })}
    </ol>
  );
}

// =========================================================================
// Modals
// =========================================================================

function AddAssetModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { toast, openAsset } = useApp();
  const locationsQuery = useLocations();
  const createAsset = useCreateAsset();
  const [f, setF] = useState({ name: '', category: '', brand: '', model: '', serial_number: '', current_location_id: '' });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f, v: string) => setF((s) => ({ ...s, [k]: v }));
  const reset = () => { setF({ name: '', category: '', brand: '', model: '', serial_number: '', current_location_id: '' }); setError(null); createAsset.reset(); };
  const close = () => { reset(); onClose(); };

  return (
    <Modal
      open={open}
      onClose={close}
      title="Register Asset"
      subtitle="The asset code and QR token are generated automatically."
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!f.name.trim() || !f.current_location_id || createAsset.isPending}
              loading={createAsset.isPending}
              onClick={() => {
                setError(null);
                createAsset.mutate(
                  {
                    name: f.name.trim(),
                    current_location_id: f.current_location_id,
                    category: f.category.trim() || null,
                    brand: f.brand.trim() || null,
                    model: f.model.trim() || null,
                    serial_number: f.serial_number.trim() || null,
                  },
                  {
                    onSuccess: (a) => { close(); toast({ title: `Registered ${a.asset_code}`, tone: 'success' }); openAsset(a.id); },
                    onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not register the asset.'),
                  }
                );
              }}
            >
              Register
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Input label="Asset name" placeholder="Dell Latitude Laptop" value={f.name} onChange={(e) => set('name', e.target.value)} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Category" placeholder="Laptop / Furniture / Equipment" value={f.category} onChange={(e) => set('category', e.target.value)} />
          <Select label="Current / initial location" value={f.current_location_id} onChange={(e) => set('current_location_id', e.target.value)}>
            <option value="">Select a location…</option>
            {(locationsQuery.data ?? []).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </Select>
          <Input label="Make" value={f.brand} onChange={(e) => set('brand', e.target.value)} />
          <Input label="Model" value={f.model} onChange={(e) => set('model', e.target.value)} />
          <Input label="Serial number" value={f.serial_number} onChange={(e) => set('serial_number', e.target.value)} />
        </div>
        {(locationsQuery.data ?? []).length === 0 && (
          <InfoNote tone="amber">Add a location first — assets are always placed in a location from the master list.</InfoNote>
        )}
      </div>
    </Modal>
  );
}

function AddLocationModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { toast } = useApp();
  const createLocation = useCreateLocation();
  const [f, setF] = useState({ name: '', building: '', floor: '', description: '', in_charge: '', phone: '' });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f, v: string) => setF((s) => ({ ...s, [k]: v }));
  const reset = () => { setF({ name: '', building: '', floor: '', description: '', in_charge: '', phone: '' }); setError(null); createLocation.reset(); };
  const close = () => { reset(); onClose(); };

  return (
    <Modal
      open={open}
      onClose={close}
      title="Add Location"
      subtitle="A venue an asset can live in (OT-1, Andrology Lab, Store Room B…)."
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!f.name.trim() || createLocation.isPending}
              loading={createLocation.isPending}
              onClick={() => {
                setError(null);
                createLocation.mutate(
                  {
                    name: f.name.trim(),
                    building: f.building.trim() || null,
                    floor: f.floor.trim() || null,
                    description: f.description.trim() || null,
                    in_charge: f.in_charge.trim() || null,
                    phone: f.phone.trim() || null,
                  },
                  {
                    onSuccess: () => { close(); toast({ title: 'Location added', tone: 'success' }); },
                    onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not add the location.'),
                  }
                );
              }}
            >
              Add
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Input label="Name" placeholder="OT-1" value={f.name} onChange={(e) => set('name', e.target.value)} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Building" value={f.building} onChange={(e) => set('building', e.target.value)} />
          <Input label="Floor" value={f.floor} onChange={(e) => set('floor', e.target.value)} />
          <Input label="In-charge" value={f.in_charge} onChange={(e) => set('in_charge', e.target.value)} />
          <Input label="Phone" value={f.phone} onChange={(e) => set('phone', e.target.value)} />
        </div>
        <Input label="Description" value={f.description} onChange={(e) => set('description', e.target.value)} />
      </div>
    </Modal>
  );
}

function MoveAssetModal({ asset, open, onClose }: { asset: AssetOut; open: boolean; onClose: () => void }) {
  const { toast } = useApp();
  const locationsQuery = useLocations();
  const moveAsset = useMoveAsset();
  const [toId, setToId] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);
  const close = () => { setToId(''); setNote(''); setError(null); moveAsset.reset(); onClose(); };

  const options = useMemo(
    () => (locationsQuery.data ?? []).filter((l) => l.id !== asset.current_location?.id),
    [locationsQuery.data, asset.current_location?.id]
  );

  return (
    <Modal
      open={open}
      onClose={close}
      title="Move Asset"
      subtitle={`${asset.name} — currently at ${asset.current_location?.name ?? 'no location'}.`}
      footer={
        <div className="flex items-center justify-between gap-3">
          {error && <p className="text-[13px] text-rose-600">{error}</p>}
          <div className="ml-auto flex gap-2">
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!toId || moveAsset.isPending}
              loading={moveAsset.isPending}
              onClick={() => {
                setError(null);
                moveAsset.mutate(
                  { assetId: asset.id, to_location_id: toId, note: note.trim() || null },
                  {
                    onSuccess: (a) => { close(); toast({ title: `Moved to ${a.current_location?.name}`, tone: 'success' }); },
                    onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not record the move.'),
                  }
                );
              }}
            >
              Confirm Move
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-4">
        <Select label="New location" value={toId} onChange={(e) => setToId(e.target.value)}>
          <option value="">Select a location…</option>
          {options.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
        </Select>
        <label className="block">
          <span className="mb-1.5 block text-[13.5px] font-medium text-ink-700">Movement note (optional)</span>
          <textarea
            className="min-h-[80px] w-full rounded-lg border border-ink-200 bg-white p-3 text-[14px] text-ink-900"
            placeholder="Reason / who requested the move…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>
      </div>
    </Modal>
  );
}
