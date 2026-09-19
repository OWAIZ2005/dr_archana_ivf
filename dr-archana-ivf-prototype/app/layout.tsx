import type { Metadata, Viewport } from 'next';
import { Inter, Instrument_Serif } from 'next/font/google';
import { PwaRegister } from '@/components/PwaRegister';
import './globals.css';

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

const display = Instrument_Serif({
  subsets: ['latin'],
  weight: '400',
  variable: '--font-display',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Dr. Archana IVF — Clinical Operating System',
  description:
    'A secure, integrated IVF hospital management system designed around the complete fertility patient journey.',
  manifest: '/manifest.webmanifest',
  appleWebApp: {
    capable: true,
    // 'default' (not 'black-translucent') — the shell already reserves its
    // own header bar via Topbar; a translucent status bar would put the OS
    // clock/battery icons directly on top of it instead of above it.
    statusBarStyle: 'default',
    title: 'Dr. Archana IVF',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#059669',
  // Lets the shell draw under the rounded corners / home indicator once
  // this is installed as a standalone PWA, so AppShell can then pad those
  // areas itself with env(safe-area-inset-*) instead of leaving a stray
  // system-drawn bar. No effect in ordinary browser tabs.
  viewportFit: 'cover',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${display.variable}`}>
      <body className="font-sans antialiased">
        {children}
        <PwaRegister />
      </body>
    </html>
  );
}
