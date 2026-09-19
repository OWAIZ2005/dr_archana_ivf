import type { MetadataRoute } from 'next';

/** Next 15's native manifest route — served at /manifest.webmanifest, no
 * static public/manifest.json needed. Icons are generated at build time by
 * icon.tsx/apple-icon.tsx in this same directory, not sourced from disk. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Dr. Archana IVF — Clinical Operating System',
    short_name: 'Dr. Archana IVF',
    description:
      'Hospital information management system for Dr. Archana IVF & Women Centre.',
    start_url: '/',
    display: 'standalone',
    background_color: '#fbfaf9',
    theme_color: '#059669',
    icons: [
      { src: '/icon', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/icon', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  };
}
