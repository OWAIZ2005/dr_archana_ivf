import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, tokenStore } from './client';
import { createPasskeyCredential, getPasskeyCredential } from '../webauthn';
import type { TokenResponse, UserSummary } from './types';

export interface PasskeyOut {
  id: string;
  device_label: string | null;
  created_at: string;
  last_used_at: string | null;
}

export function usePasskeys() {
  return useQuery({
    queryKey: ['passkeys'],
    queryFn: () => apiFetch<PasskeyOut[]>('/auth/passkeys'),
  });
}

/** One mutation covers the whole ceremony (options -> Face ID prompt ->
 * verify) — callers never see the two-request round trip, matching how
 * loginRequest() in lib/api/auth.ts hides /auth/login + /auth/me behind
 * one call. */
export function useRegisterPasskey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (deviceLabel: string | null) => {
      const { options } = await apiFetch<{ options: any }>('/auth/passkeys/register/options', { method: 'POST' });
      const credential = await createPasskeyCredential(options);
      return apiFetch<PasskeyOut>('/auth/passkeys/register/verify', {
        method: 'POST',
        body: { credential, challenge: options.challenge, device_label: deviceLabel },
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['passkeys'] }),
  });
}

export function useDeletePasskey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/auth/passkeys/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['passkeys'] }),
  });
}

/** Mirrors loginRequest() in lib/api/auth.ts exactly — same tokenStore
 * side effect and /auth/me fetch on success, same "clear the token if
 * /auth/me somehow fails" cleanup — so lib/auth.tsx's loginWithPasskey can
 * treat this identically to a password login once it resolves. */
export async function loginWithPasskeyRequest(): Promise<UserSummary> {
  const { options } = await apiFetch<{ options: any }>('/auth/passkeys/login/options', {
    method: 'POST',
    skipAuthRetry: true,
  });
  const credential = await getPasskeyCredential(options);
  const tokens = await apiFetch<TokenResponse>('/auth/passkeys/login/verify', {
    method: 'POST',
    body: { credential, challenge: options.challenge },
    skipAuthRetry: true,
  });
  tokenStore.set(tokens.access_token);
  try {
    return await apiFetch<UserSummary>('/auth/me');
  } catch (err) {
    tokenStore.set(null);
    throw err;
  }
}
