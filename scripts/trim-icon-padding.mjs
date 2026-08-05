#!/usr/bin/env node
/**
 * Trim fully-transparent padding from a PNG.
 *
 * The Gravitre mark ships on a square 2133x2133 canvas, but its ink only fills
 * ~49% of the width and ~29% of the height. Rendering that file into a 36px box
 * therefore yields a ~16x9px visible glyph, which reads far smaller than the
 * 36px filled circle used for the user avatar sitting opposite it.
 *
 * Cropping to the ink bounding box lets the mark be sized by its actual glyph,
 * so `w-9` really means "36px of mark" and the two avatars carry equal visual
 * weight without any layout-breaking transform or overflow.
 *
 * Usage: node scripts/trim-icon-padding.mjs <in.png> <out.png>
 *
 * Deliberately dependency-free (no sharp/canvas): decodes 8-bit RGBA PNGs with
 * zlib, undoes the five PNG filter types, crops, and re-encodes as a single
 * unfiltered IDAT.
 */
import { readFileSync, writeFileSync } from "node:fs"
import { deflateSync, inflateSync } from "node:zlib"

const PNG_SIG = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])

function crc32(buf) {
  let c = ~0
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i]
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1))
  }
  return ~c >>> 0
}

function chunk(type, data) {
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const body = Buffer.concat([Buffer.from(type, "ascii"), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body))
  return Buffer.concat([len, body, crc])
}

/** Decode an 8-bit truecolour-with-alpha PNG into flat RGBA bytes. */
function decode(file) {
  const buf = readFileSync(file)
  if (!buf.subarray(0, 8).equals(PNG_SIG)) throw new Error(`${file}: not a PNG`)

  const width = buf.readUInt32BE(16)
  const height = buf.readUInt32BE(20)
  const depth = buf[24]
  const colorType = buf[25]
  const interlace = buf[28]

  if (depth !== 8) throw new Error(`${file}: expected 8-bit, got ${depth}`)
  if (colorType !== 6) throw new Error(`${file}: expected RGBA (6), got ${colorType}`)
  if (interlace !== 0) throw new Error(`${file}: interlaced PNGs unsupported`)

  const idat = []
  let offset = 8
  while (offset < buf.length) {
    const len = buf.readUInt32BE(offset)
    const type = buf.toString("ascii", offset + 4, offset + 8)
    if (type === "IDAT") idat.push(buf.subarray(offset + 8, offset + 8 + len))
    if (type === "IEND") break
    offset += 12 + len
  }

  const raw = inflateSync(Buffer.concat(idat))
  const bpp = 4
  const rowBytes = width * bpp
  const pixels = Buffer.alloc(rowBytes * height)

  for (let y = 0; y < height; y++) {
    const filter = raw[y * (rowBytes + 1)]
    const line = raw.subarray(y * (rowBytes + 1) + 1, y * (rowBytes + 1) + 1 + rowBytes)
    for (let i = 0; i < rowBytes; i++) {
      const left = i >= bpp ? pixels[y * rowBytes + i - bpp] : 0
      const up = y > 0 ? pixels[(y - 1) * rowBytes + i] : 0
      const upLeft = i >= bpp && y > 0 ? pixels[(y - 1) * rowBytes + i - bpp] : 0
      let v = line[i]
      if (filter === 1) v += left
      else if (filter === 2) v += up
      else if (filter === 3) v += (left + up) >> 1
      else if (filter === 4) {
        const p = left + up - upLeft
        const pa = Math.abs(p - left)
        const pb = Math.abs(p - up)
        const pc = Math.abs(p - upLeft)
        v += pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft
      }
      pixels[y * rowBytes + i] = v & 0xff
    }
  }

  return { width, height, pixels }
}

/** Bounding box of pixels with alpha above `threshold`. */
function inkBounds({ width, height, pixels }, threshold = 8) {
  let minX = width
  let minY = height
  let maxX = -1
  let maxY = -1
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (pixels[(y * width + x) * 4 + 3] > threshold) {
        if (x < minX) minX = x
        if (x > maxX) maxX = x
        if (y < minY) minY = y
        if (y > maxY) maxY = y
      }
    }
  }
  if (maxX < 0) throw new Error("image is fully transparent")
  return { minX, minY, maxX, maxY }
}

function encode(width, height, pixels) {
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(width, 0)
  ihdr.writeUInt32BE(height, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 6 // RGBA
  const rowBytes = width * 4
  const raw = Buffer.alloc((rowBytes + 1) * height)
  for (let y = 0; y < height; y++) {
    raw[y * (rowBytes + 1)] = 0 // filter: none
    pixels.copy(raw, y * (rowBytes + 1) + 1, y * rowBytes, (y + 1) * rowBytes)
  }
  return Buffer.concat([
    PNG_SIG,
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ])
}

const [input, output] = process.argv.slice(2)
if (!input || !output) {
  console.error("usage: node scripts/trim-icon-padding.mjs <in.png> <out.png>")
  process.exit(1)
}

const image = decode(input)
const { minX, minY, maxX, maxY } = inkBounds(image)
const cropW = maxX - minX + 1
const cropH = maxY - minY + 1

const cropped = Buffer.alloc(cropW * cropH * 4)
for (let y = 0; y < cropH; y++) {
  image.pixels.copy(
    cropped,
    y * cropW * 4,
    ((minY + y) * image.width + minX) * 4,
    ((minY + y) * image.width + minX + cropW) * 4,
  )
}

writeFileSync(output, encode(cropW, cropH, cropped))
console.log(
  `${input} ${image.width}x${image.height} -> ${output} ${cropW}x${cropH} ` +
    `(aspect ${(cropW / cropH).toFixed(2)}:1)`,
)
