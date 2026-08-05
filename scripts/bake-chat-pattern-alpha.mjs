/**
 * Bake a constant alpha multiplier into 8-bit RGBA non-interlaced PNGs.
 *
 * The design handoff specifies the department chat patterns at `opacity: 0.15`.
 * Rather than render them through an absolutely-positioned opacity layer — which
 * does not reliably cover the full scrollable height of a scroll container, and
 * would require the message list to claim its own z-index — we pre-multiply the
 * alpha into the tiles. The chat canvas can then use plain `background-image`
 * with `background-attachment: local`, matching the existing scroll-safe
 * approach and leaving message content untouched.
 *
 * Usage:
 *   node scripts/bake-chat-pattern-alpha.mjs <src-dir> <out-dir> [alpha]
 *
 * Re-run this if design ships new source tiles. Only the baked output in
 * apps/web/public/patterns is committed.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs"
import { inflateSync, deflateSync } from "node:zlib"
import { basename, join } from "node:path"

const SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])

const TILES = [
  "gw-mkt-light.png", "gw-mkt-dark.png",
  "gw-sales-light.png", "gw-sales-dark.png",
  "gw-dev-light.png", "gw-dev-dark.png",
  "gw-ops-light.png", "gw-ops-dark.png",
]

const CRC_TABLE = (() => {
  const t = new Int32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    t[n] = c
  }
  return t
})()

function crc32(buf) {
  let c = 0xffffffff
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length, 0)
  const td = Buffer.concat([Buffer.from(type, "ascii"), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(td), 0)
  return Buffer.concat([len, td, crc])
}

function paeth(a, b, c) {
  const p = a + b - c
  const pa = Math.abs(p - a)
  const pb = Math.abs(p - b)
  const pc = Math.abs(p - c)
  if (pa <= pb && pa <= pc) return a
  if (pb <= pc) return b
  return c
}

function bake(srcPath, outPath, alpha) {
  const buf = readFileSync(srcPath)
  if (!buf.subarray(0, 8).equals(SIG)) throw new Error(`${srcPath}: not a PNG`)

  const width = buf.readUInt32BE(16)
  const height = buf.readUInt32BE(20)
  const depth = buf[24]
  const colorType = buf[25]
  const interlace = buf[28]
  if (depth !== 8 || colorType !== 6 || interlace !== 0) {
    throw new Error(
      `${srcPath}: expected 8-bit RGBA non-interlaced, got depth=${depth} color=${colorType} interlace=${interlace}`,
    )
  }

  // A PNG may split its single zlib stream across many IDAT chunks.
  const idat = []
  let off = 8
  while (off < buf.length) {
    const len = buf.readUInt32BE(off)
    const type = buf.toString("ascii", off + 4, off + 8)
    if (type === "IDAT") idat.push(buf.subarray(off + 8, off + 8 + len))
    off += 12 + len
    if (type === "IEND") break
  }
  const raw = inflateSync(Buffer.concat(idat))

  const bpp = 4
  const stride = width * bpp
  if (raw.length !== (stride + 1) * height) {
    throw new Error(`${srcPath}: unexpected inflated length ${raw.length}`)
  }

  // Reverse the per-scanline filters into a flat RGBA buffer.
  const px = Buffer.alloc(stride * height)
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)]
    const line = raw.subarray(y * (stride + 1) + 1, y * (stride + 1) + 1 + stride)
    const cur = px.subarray(y * stride, (y + 1) * stride)
    const prev = y > 0 ? px.subarray((y - 1) * stride, y * stride) : null
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? cur[x - bpp] : 0
      const b = prev ? prev[x] : 0
      const c = prev && x >= bpp ? prev[x - bpp] : 0
      let v
      switch (filter) {
        case 0: v = line[x]; break
        case 1: v = line[x] + a; break
        case 2: v = line[x] + b; break
        case 3: v = line[x] + ((a + b) >> 1); break
        case 4: v = line[x] + paeth(a, b, c); break
        default: throw new Error(`${srcPath}: bad filter ${filter} on row ${y}`)
      }
      cur[x] = v & 0xff
    }
  }

  let before = 0
  let after = 0
  for (let i = 3; i < px.length; i += 4) {
    if (px[i] > before) before = px[i]
    px[i] = Math.round(px[i] * alpha)
    if (px[i] > after) after = px[i]
  }

  // Re-emit with filter 0 (None) — zlib still compresses these tiles well.
  const out = Buffer.alloc((stride + 1) * height)
  for (let y = 0; y < height; y++) {
    out[y * (stride + 1)] = 0
    px.copy(out, y * (stride + 1) + 1, y * stride, (y + 1) * stride)
  }

  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(width, 0)
  ihdr.writeUInt32BE(height, 4)
  ihdr[8] = 8
  ihdr[9] = 6
  const png = Buffer.concat([
    SIG,
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(out, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ])
  writeFileSync(outPath, png)
  console.log(
    `${basename(outPath).padEnd(22)} ${width}x${height}  peak alpha ${before} -> ${after}  ${(png.length / 1024).toFixed(1)}kb`,
  )
}

const [srcDir, outDir, alphaArg] = process.argv.slice(2)
if (!srcDir || !outDir) {
  console.error("usage: node scripts/bake-chat-pattern-alpha.mjs <src-dir> <out-dir> [alpha]")
  process.exit(1)
}
const alpha = alphaArg ? Number(alphaArg) : 0.15
mkdirSync(outDir, { recursive: true })
for (const name of TILES) bake(join(srcDir, name), join(outDir, name), alpha)
console.log(`\nBaked ${TILES.length} tiles at alpha ${alpha}.`)
