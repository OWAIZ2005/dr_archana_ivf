import { ImageResponse } from 'next/og';

export const size = { width: 512, height: 512 };
export const contentType = 'image/png';

/** Generated at build time — same droplet mark and brand gradient used for
 * the sidebar logo (components/layout/Sidebar.tsx), so the home-screen icon
 * reads as the same product rather than a placeholder. No binary asset on
 * disk to keep in sync with that mark if it ever changes. */
export default function Icon() {
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
          borderRadius: 96,
        }}
      >
        <svg width="280" height="280" viewBox="0 0 24 24" fill="none">
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
