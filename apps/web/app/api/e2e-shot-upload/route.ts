import { NextResponse } from "next/server"
import { mkdir, writeFile } from "node:fs/promises"
import { join } from "node:path"

/**
 * TEMPORARY capture utility — delete after refreshing product screenshots.
 *
 * The browser automation sandbox and the project sandbox have separate
 * filesystems, so a screenshot taken by the automation CLI cannot be written
 * straight into the repo. This receives those PNGs over HTTP instead.
 *
 * Hard-disabled outside development: this writes files to disk, which must
 * never be reachable on a deployed instance.
 */
export async function POST(request: Request) {
  if (process.env.NODE_ENV === "production") {
    return NextResponse.json({ error: "Not found" }, { status: 404 })
  }

  const form = await request.formData()
  const files = form.getAll("files").filter((f): f is File => f instanceof File)
  if (files.length === 0) {
    return NextResponse.json({ error: "No files" }, { status: 400 })
  }

  const outDir = join(process.cwd(), "public", "product")
  await mkdir(outDir, { recursive: true })

  const written: string[] = []
  for (const file of files) {
    // Strip any path component and allow only a safe basename, so a crafted
    // filename cannot escape the output directory.
    const safe = file.name.replace(/^.*[/\\]/, "").replace(/[^a-zA-Z0-9._-]/g, "")
    if (!safe.endsWith(".png") || safe.startsWith(".")) continue

    const bytes = Buffer.from(await file.arrayBuffer())
    // Reject anything that is not actually a PNG.
    if (bytes.length < 8 || bytes.readUInt32BE(0) !== 0x89504e47) continue

    await writeFile(join(outDir, safe), bytes)
    written.push(`${safe} (${bytes.length} bytes)`)
  }

  return NextResponse.json({ written })
}
