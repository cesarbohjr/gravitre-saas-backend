import { NextRequest } from "next/server";
import { proxyRagToBackend } from "@/lib/backend-proxy";

/** GET /api/rag/ingest/:id — proxy to FastAPI. */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyRagToBackend(request, `/ingest/${id}`);
}
