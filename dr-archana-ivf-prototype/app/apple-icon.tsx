import { ImageResponse } from 'next/og';

export const size = { width: 180, height: 180 };
export const contentType = 'image/png';

/** iOS applies its own corner mask/shine to apple-touch-icon, so this stays
 * a plain square with no transparency (a transparent apple-touch-icon gets
 * a black backfill from iOS, not the brand background) and no border-radius
 * of its own — see app/icon.tsx for the PWA/favicon variant, which does add
 * radius since browsers/Android don't mask that one for you. */
export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #10B981 0%, #047857 100%)',
        }}
      >
        <svg width="100" height="100" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 21c-1.5-3-5-5.2-5-9a5 5 0 0110 0c0 3.8-3.5 6-5 9z"
            fill="white"
            fillOpacity={0.95}
          />
          <circle cx="12" cy="11" r="2.1" fill="#059669" />
        </svg>
      </div>
    ),
    { ...size }
  );
}
