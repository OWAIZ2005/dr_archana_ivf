import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiFetchBlob } from './client';

export type AssetStatus = 'active' | 'under_maintenance' | 'sent_for_service' | 'retired';

export interface LocationOut {
  id: string;
  name: string;
  building: string | null;
  floor: string | null;
  description: string | null;
  in_charge: string | null;
  phone: string | null;
  is_active: boolean;
}

export interface AssetOut {
  id: string;
  asset_code: string;
  name: string;
  category: string | null;
  brand: string | null;
  model: string | null;
  serial_number: string | null;
  status: AssetStatus;
  qr_token: string;
  current_location: LocationOut | null;
  updated_at: string;
}

export interface AssetDetailOut extends AssetOut {
  purchase_date: string | null;
  cost_paise: number | null;
  warranty_until: string | null;
  amc_until: string | null;
  registered_by_id: string | null;
  created_at: string;
}

export interface AssetMovementOut {
  id: string;
  event_type: string; // "register" | "move"
  from_location: LocationOut | null;
  to_location: LocationOut | null;
  note: string | null;
  moved_by_id: string;
  moved_by_name: string | null;
  moved_at: string;
}

export interface AssetFilters {
  q?: string;
  location_id?: string;
  category?: string;
  status?: AssetStatus;
}

// ------------------------------- queries -------------------------------- #

export function useAssets(filters: AssetFilters = {}) {
  const params = new URLSearchParams();
  if (filters.q) params.set('q', filters.q);
  if (filters.location_id) params.set('location_id', filters.location_id);
  if (filters.category) params.set('category', filters.category);
  if (filters.status) params.set('status', filters.status);
  const qs = params.toString();
  return useQuery({
    queryKey: ['assets', filters],
    queryFn: () => apiFetch<AssetOut[]>(`/assets${qs ? `?${qs}` : ''}`),
  });
}

export function useAsset(assetId: string | null) {
  return useQuery({
    queryKey: ['asset', assetId],
    queryFn: () => apiFetch<AssetDetailOut>(`/assets/${assetId}`),
    enabled: !!assetId,
  });
}

export function useAssetHistory(assetId: string | null) {
  return useQuery({
    queryKey: ['asset-history', assetId],
    queryFn: () => apiFetch<AssetMovementOut[]>(`/assets/${assetId}/history`),
    enabled: !!assetId,
  });
}

export function useLocations() {
  return useQuery({
    queryKey: ['asset-locations'],
    queryFn: () => apiFetch<LocationOut[]>(`/assets/locations`),
  });
}

export function resolveAssetQr(token: string) {
  return apiFetch<AssetDetailOut>(`/assets/resolve/${encodeURIComponent(token)}`);
}

// ------------------------------ mutations ------------------------------- #

export function useCreateAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      name: string;
      current_location_id: string;
      category?: string | null;
      brand?: string | null;
      model?: string | null;
      serial_number?: string | null;
    }) => apiFetch<AssetDetailOut>('/assets', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assets'] }),
  });
}

export function useUpdateAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ assetId, ...body }: { assetId: string } & Partial<Pick<AssetDetailOut,
      'name' | 'category' | 'brand' | 'model' | 'serial_number' | 'status'>>) =>
      apiFetch<AssetDetailOut>(`/assets/${assetId}`, { method: 'PATCH', body }),
    onSuccess: (_, v) => {
      qc.invalidateQueries({ queryKey: ['asset', v.assetId] });
      qc.invalidateQueries({ queryKey: ['assets'] });
    },
  });
}

export function useMoveAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ assetId, to_location_id, note }: { assetId: string; to_location_id: string; note?: string | null }) =>
      apiFetch<AssetDetailOut>(`/assets/${assetId}/move`, { method: 'POST', body: { to_location_id, note } }),
    onSuccess: (_, v) => {
      qc.invalidateQueries({ queryKey: ['asset', v.assetId] });
      qc.invalidateQueries({ queryKey: ['asset-history', v.assetId] });
      qc.invalidateQueries({ queryKey: ['assets'] });
    },
  });
}

export function useCreateLocation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      name: string;
      building?: string | null;
      floor?: string | null;
      description?: string | null;
      in_charge?: string | null;
      phone?: string | null;
    }) => apiFetch<LocationOut>('/assets/locations', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['asset-locations'] }),
  });
}

/**
 * The application's own base URL — what a printed asset QR points at
 * (`<appBaseUrl>/#scan=<token>`). Comes from configuration
 * (`NEXT_PUBLIC_APP_URL`), never a hardcoded IP; falls back to the current
 * origin so local dev works with no env file. For the hospital deployment set
 * `NEXT_PUBLIC_APP_URL=http://<internal-server-ip>:3000` (or the https
 * hostname IT provides) and rebuild.
 */
export function appBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_APP_URL?.trim();
  if (configured) return configured.replace(/\/$/, '');
  if (typeof window !== 'undefined') return window.location.origin;
  return '';
}

function withBase(path: string): string {
  const base = appBaseUrl();
  if (!base) return path;
  return `${path}${path.includes('?') ? '&' : '?'}base=${encodeURIComponent(base)}`;
}

/** Path (with `?base=`) for an asset's QR PNG preview. */
export function assetQrPreviewPath(assetId: string): string {
  return withBase(`/assets/${assetId}/qr`);
}

/** Open the printable QR label PDF in a new tab. */
export async function openAssetLabel(assetId: string): Promise<void> {
  const blob = await apiFetchBlob(withBase(`/assets/${assetId}/label`));
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank', 'noopener');
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
