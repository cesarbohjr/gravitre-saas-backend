// Compile the development-only filesystem preview out of normal production
// builds. A runtime-only 404 gate still makes the bundler trace its filesystem.
export async function GET(req: Request, context: { params: Promise<{ path: string[] }> }) {
  if (process.env.GRAVITRE_STATIC_PREVIEW_ENABLED !== "1") {
    return new Response("Not found", { status: 404 })
  }
  const preview = await import("./static-preview")
  return preview.GET(req, context)
}
