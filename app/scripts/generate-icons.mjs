// Generates PWA PNG icons (192, 512, maskable) with a simple flame design.
// Run: node scripts/generate-icons.mjs
import { deflateSync } from "node:zlib";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = join(__dirname, "..", "public", "icons");
mkdirSync(outDir, { recursive: true });

// ---- Minimal PNG encoder (RGBA, no interlace) ----
function crc32(buf) {
  let c = ~0;
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i];
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
  }
  return ~c >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const typeBuf = Buffer.from(type, "ascii");
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])));
  return Buffer.concat([len, typeBuf, data, crcBuf]);
}

function encodePng(width, height, rgba) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // color type RGBA
  // raw scanlines with filter byte 0
  const raw = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (width * 4 + 1)] = 0;
    rgba.copy(raw, y * (width * 4 + 1) + 1, y * width * 4, (y + 1) * width * 4);
  }
  const idat = deflateSync(raw, { level: 9 });
  return Buffer.concat([
    sig,
    chunk("IHDR", ihdr),
    chunk("IDAT", idat),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// ---- Flame drawing ----
// Colors
const BG = [234, 88, 12, 255]; // orange-600
const FLAME_OUTER = [255, 237, 213, 255]; // orange-100
const FLAME_INNER = [255, 247, 237, 255]; // orange-50

function makeIcon(size, maskable) {
  const px = Buffer.alloc(size * size * 4);
  const safe = maskable ? 0.2 : 0.0; // maskable safe zone inset

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      // Normalized coords in [0,1]
      const nx = x / size;
      const ny = y / size;
      const i = (y * size + x) * 4;

      // Background
      px[i] = BG[0];
      px[i + 1] = BG[1];
      px[i + 2] = BG[2];
      px[i + 3] = BG[3];

      // Flame shape: teardrop centered horizontally, pointing up.
      // Center x = 0.5, base near bottom.
      const cx = 0.5;
      const dx = nx - cx;
      // Vertical: flame occupies roughly y in [0.15, 0.85]
      const t = (ny - 0.15) / 0.7; // 0 at top of flame, 1 at bottom
      if (t < 0 || t > 1) continue;

      // Half-width of flame at height t (teardrop): widest near bottom.
      const halfW = 0.28 * Math.pow(t, 0.6) * (1 - 0.25 * t);
      if (Math.abs(dx) > halfW) continue;

      // Inner core (smaller teardrop)
      const innerHalfW = halfW * 0.45;
      const inInner = Math.abs(dx) < innerHalfW;

      // Apply safe-zone inset for maskable icons
      if (maskable) {
        const inset = safe;
        if (nx < inset || nx > 1 - inset || ny < inset || ny > 1 - inset) {
          px[i] = BG[0];
          px[i + 1] = BG[1];
          px[i + 2] = BG[2];
          px[i + 3] = BG[3];
          continue;
        }
      }

      const c = inInner ? FLAME_INNER : FLAME_OUTER;
      px[i] = c[0];
      px[i + 1] = c[1];
      px[i + 2] = c[2];
      px[i + 3] = c[3];
    }
  }
  return encodePng(size, size, px);
}

writeFileSync(join(outDir, "icon-192.png"), makeIcon(192, false));
writeFileSync(join(outDir, "icon-512.png"), makeIcon(512, false));
writeFileSync(join(outDir, "icon-maskable-512.png"), makeIcon(512, true));
console.log("Icons written to", outDir);