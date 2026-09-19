/**
 * Thin browser-side WebAuthn layer: base64url <-> ArrayBuffer conversion
 * (the backend's options/verify JSON, from Python's `webauthn` package,
 * encodes every binary field as base64url text — the real
 * `navigator.credentials.create()/get()` APIs want raw BufferSource
 * instead) plus two functions that run the actual ceremony and hand back
 * a JSON-serializable object shaped exactly like what
 * backend/app/webauthn/schemas.py's RegistrationVerifyRequest /
 * AuthenticationVerifyRequest expect.
 *
 * Safari on iPadOS supports all of this from iOS/iPadOS 14+, with Face ID
 * or Touch ID satisfying the platform-authenticator prompt — see
 * app/webauthn/service.py's `authenticator_attachment=PLATFORM` on the
 * backend, which is what requests that specific behavior rather than
 * allowing a roaming security key too.
 */

export function isPasskeySupported(): boolean {
  return typeof window !== 'undefined' && typeof window.PublicKeyCredential !== 'undefined' && !!navigator.credentials;
}

function base64urlToBuffer(base64url: string): ArrayBuffer {
  const padding = '='.repeat((4 - (base64url.length % 4)) % 4);
  const base64 = (base64url + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return bytes.buffer;
}

function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let str = '';
  for (const b of bytes) str += String.fromCharCode(b);
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Runs navigator.credentials.create() against server-issued registration
 * options and returns the RegistrationResponseJSON shape the backend's
 * verify_registration_response() (via py_webauthn) expects. */
export async function createPasskeyCredential(options: any): Promise<Record<string, unknown>> {
  if (!isPasskeySupported()) {
    throw new Error('Passkeys are not supported in this browser.');
  }
  const publicKey: PublicKeyCredentialCreationOptions = {
    ...options,
    challenge: base64urlToBuffer(options.challenge),
    user: { ...options.user, id: base64urlToBuffer(options.user.id) },
    excludeCredentials: (options.excludeCredentials ?? []).map((c: any) => ({
      ...c,
      id: base64urlToBuffer(c.id),
    })),
  };

  const credential = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential | null;
  if (!credential) throw new Error('Passkey creation was cancelled.');
  const response = credential.response as AuthenticatorAttestationResponse;

  return {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: (credential as any).authenticatorAttachment ?? undefined,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
      attestationObject: bufferToBase64url(response.attestationObject),
      transports: response.getTransports?.() ?? undefined,
    },
  };
}

/** Runs navigator.credentials.get() against server-issued authentication
 * options and returns the AuthenticationResponseJSON shape
 * verify_authentication_response() expects. No allowCredentials means the
 * platform picks from whichever passkeys for this site are on the
 * device — the discoverable-credential flow this app uses so it never has
 * to ask "who are you" before "prove it" (see app/webauthn/service.py). */
export async function getPasskeyCredential(options: any): Promise<Record<string, unknown>> {
  if (!isPasskeySupported()) {
    throw new Error('Passkeys are not supported in this browser.');
  }
  const publicKey: PublicKeyCredentialRequestOptions = {
    ...options,
    challenge: base64urlToBuffer(options.challenge),
    allowCredentials: (options.allowCredentials ?? []).map((c: any) => ({
      ...c,
      id: base64urlToBuffer(c.id),
    })),
  };

  const credential = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential | null;
  if (!credential) throw new Error('Passkey sign-in was cancelled.');
  const response = credential.response as AuthenticatorAssertionResponse;

  return {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
      authenticatorData: bufferToBase64url(response.authenticatorData),
      signature: bufferToBase64url(response.signature),
      userHandle: response.userHandle ? bufferToBase64url(response.userHandle) : undefined,
    },
  };
}
