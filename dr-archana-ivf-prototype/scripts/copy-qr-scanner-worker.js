// qr-scanner ships its WASM/asm.js decode worker as a standalone script that
// must be served at a real URL (QrScanner.WORKER_PATH in QrScanner.tsx) —
// it can't be bundled by webpack like a normal import. Runs on every
// `npm install` (postinstall) so a fresh checkout or a Docker build never
// silently ships without it — the alternative is a scanner that renders
// fine and then fails opaquely the first time someone tries to scan.
const fs = require('fs');
const path = require('path');

const src = path.join(__dirname, '..', 'node_modules', 'qr-scanner', 'qr-scanner-worker.min.js');
const destDir = path.join(__dirname, '..', 'public');
const dest = path.join(destDir, 'qr-scanner-worker.min.js');

if (!fs.existsSync(src)) {
  console.warn('[copy-qr-scanner-worker] node_modules/qr-scanner not found — skipping (is it installed?)');
  process.exit(0);
}

fs.mkdirSync(destDir, { recursive: true });
fs.copyFileSync(src, dest);
console.log('[copy-qr-scanner-worker] copied to public/qr-scanner-worker.min.js');
