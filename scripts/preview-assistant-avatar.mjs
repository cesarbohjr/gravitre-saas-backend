/**
 * Render a before/after preview of the assistant (Gravitre) chat avatar without
 * a browser.
 *
 * Chromium cannot launch in the v0 sandbox (missing system libs), so this
 * composites the REAL icon asset at the REAL CSS pixel sizes onto the actual
 * canvas colors. It is a faithful preview of the two things that changed — glyph
 * size and removal of the circular shell — but it is NOT a render of the running
 * app. Layout/alignment inside the message row still needs a real browser check.
 *
 * Usage:
 *   node scripts/preview-assistant-avatar.mjs [out.png]
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs"
import { inflateSync, deflateSync } from "node:zlib"
import { dirname } from "node:path"

const SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])

const CRC_TABLE = (() => {
  const t = new Int32Array(256)
  for (let n = 0; n < 256; n++) {
    let c = n
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    t[n] = c
  }
  return t
})()
const crc32 = (buf) => {
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
  const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c)
  if (pa <= pb && pa <= pc) return a
  if (pb <= pc) return b
  return c
}

/** Decode an 8-bit RGBA non-interlaced PNG into {width,height,px}. */
function decode(path) {
  const buf = readFileSync(path)
  if (!buf.subarray(0, 8).equals(SIG)) throw new Error(`${path}: not a PNG`)
  const width = buf.readUInt32BE(16)
  const height = buf.readUInt32BE(20)
  if (buf[24] !== 8 || buf[25] !== 6 || buf[28] !== 0) {
    throw new Error(`${path}: expected 8-bit RGBA non-interlaced`)
  }
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
  const bpp = 4, stride = width * bpp
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
        default: throw new Error(`bad filter ${filter}`)
      }
      cur[x] = v & 0xff
    }
  }
  return { width, height, px }
}

function encode(width, height, px, outPath) {
  const stride = width * 4
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
  mkdirSync(dirname(outPath), { recursive: true })
  writeFileSync(outPath, Buffer.concat([
    SIG, chunk("IHDR", ihdr), chunk("IDAT", deflateSync(out, { level: 9 })), chunk("IEND", Buffer.alloc(0)),
  ]))
}

/** Simple canvas of solid RGB. */
function canvas(w, h, [r, g, b]) {
  const px = Buffer.alloc(w * h * 4)
  for (let i = 0; i < px.length; i += 4) {
    px[i] = r; px[i + 1] = g; px[i + 2] = b; px[i + 3] = 255
  }
  return px
}

/** Box-filter downscale of `src` to size x size, then alpha-composite at (dx,dy). */
function drawScaled(dst, dstW, src, size, dx, dy) {
  const ratio = src.width / size
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const x0 = Math.floor(x * ratio), x1 = Math.min(src.width, Math.ceil((x + 1) * ratio))
      const y0 = Math.floor(y * ratio), y1 = Math.min(src.height, Math.ceil((y + 1) * ratio))
      let r = 0, g = 0, b = 0, a = 0, n = 0
      for (let sy = y0; sy < y1; sy++) {
        for (let sx = x0; sx < x1; sx++) {
          const o = (sy * src.width + sx) * 4
          const sa = src.px[o + 3] / 255
          // Weight color by alpha so transparent pixels don't darken the average.
          r += src.px[o] * sa; g += src.px[o + 1] * sa; b += src.px[o + 2] * sa
          a += src.px[o + 3]; n++
        }
      }
      if (!n) continue
      const aa = a / n / 255
      if (aa <= 0.001) continue
      // Un-weight to recover the average color of the covered pixels.
      const sr = r / n / aa, sg = g / n / aa, sb = b / n / aa
      const o = ((dy + y) * dstW + (dx + x)) * 4
      dst[o] = Math.round(sr * aa + dst[o] * (1 - aa))
      dst[o + 1] = Math.round(sg * aa + dst[o + 1] * (1 - aa))
      dst[o + 2] = Math.round(sb * aa + dst[o + 2] * (1 - aa))
    }
  }
}

/** Filled circle — stands in for the old `rounded-full bg-zinc-100` shell. */
function drawCircle(dst, dstW, cx, cy, radius, [r, g, b], border) {
  for (let y = cy - radius - 1; y <= cy + radius + 1; y++) {
    for (let x = cx - radius - 1; x <= cx + radius + 1; x++) {
      const d = Math.hypot(x - cx + 0.5, y - cy + 0.5)
      const cov = Math.max(0, Math.min(1, radius - d + 0.5))
      if (cov <= 0) continue
      const onEdge = border && d > radius - 1.2
      const [er, eg, eb] = onEdge ? border : [r, g, b]
      const o = (y * dstW + x) * 4
      dst[o] = Math.round(er * cov + dst[o] * (1 - cov))
      dst[o + 1] = Math.round(eg * cov + dst[o + 1] * (1 - cov))
      dst[o + 2] = Math.round(eb * cov + dst[o + 2] * (1 - cov))
    }
  }
}

const SCALE = 3 // render at 3x so the comparison is legible
const black = decode("apps/web/public/images/gravitre-icon-black.png")
const white = decode("apps/web/public/images/gravitre-icon-white.png")

// Canvas surfaces straight from the app's light/dark --background.
const LIGHT = [250, 250, 250]
const DARK = [24, 24, 27]
const ZINC100 = [244, 244, 245]
const ZINC200 = [228, 228, 231]

const ROW_H = 60 * SCALE
const W = 460 * SCALE
const H = ROW_H * 4

const px = Buffer.alloc(W * H * 4)

const rows = [
  { bg: LIGHT, icon: black, bare: false, label: "light / BEFORE" },
  { bg: LIGHT, icon: black, bare: true, label: "light / AFTER" },
  { bg: DARK, icon: white, bare: false, label: "dark / BEFORE" },
  { bg: DARK, icon: white, bare: true, label: "dark / AFTER" },
]

rows.forEach((row, i) => {
  const top = i * ROW_H
  const band = canvas(W, ROW_H, row.bg)
  band.copy(px, top * W * 4)

  const boxPx = 36 * SCALE // h-9/w-9 footprint, unchanged
  const left = 24 * SCALE
  const cy = top + ROW_H / 2

  if (row.bare) {
    // AFTER: no shell, 32px glyph centered in the same 36px footprint.
    const g = 32 * SCALE
    drawScaled(px, W, row.icon, g, left + (boxPx - g) / 2, Math.round(cy - g / 2))
  } else {
    // BEFORE: 36px zinc-100 circle w/ zinc-200 border, 20px glyph.
    drawCircle(px, W, left + boxPx / 2, Math.round(cy), boxPx / 2, ZINC100, ZINC200)
    const g = 20 * SCALE
    drawScaled(px, W, black, g, left + (boxPx - g) / 2, Math.round(cy - g / 2))
  }

  // Stand-in for the message bubble, so relative scale reads true.
  const bx = left + boxPx + 10 * SCALE
  const bw = W - bx - 24 * SCALE
  const bh = 34 * SCALE
  const by = Math.round(cy - bh / 2)
  const bubble = row.bg === DARK ? [39, 39, 42] : [255, 255, 255]
  for (let y = by; y < by + bh; y++) {
    for (let x = bx; x < bx + bw; x++) {
      const o = (y * W + x) * 4
      px[o] = bubble[0]; px[o + 1] = bubble[1]; px[o + 2] = bubble[2]
    }
  }
})

const out = process.argv[2] || ".playwright-out/assistant-avatar-preview.png"
encode(W, H, px, out)
console.log(`Wrote ${out}  ${W}x${H} (${SCALE}x)`)
console.log("Rows top->bottom: light BEFORE, light AFTER, dark BEFORE, dark AFTER")
console.log("BEFORE = 20px glyph in 36px zinc circle. AFTER = bare 32px glyph, same 36px footprint.")
