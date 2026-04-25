import { NextRequest } from "next/server";
import { proxyRagToBackend } from "@/lib/backend-proxy";

/** GET /api/rag/documents/:id — proxy to FastAPI. */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const query = request.nextUrl.search;
  return proxyRagToBackend(request, `/documents/${id}${query}`);
}
