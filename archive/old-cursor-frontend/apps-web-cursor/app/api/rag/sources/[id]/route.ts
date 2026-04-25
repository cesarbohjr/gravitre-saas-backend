import { NextRequest } from "next/server";
import { proxyRagToBackend } from "@/lib/backend-proxy";

/** GET/PATCH /api/rag/sources/:id — proxy to FastAPI. */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyRagToBackend(request, `/sources/${id}`);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.text();
  return proxyRagToBackend(request, `/sources/${id}`, { method: "PATCH", body });
}
