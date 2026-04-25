import { NextRequest } from "next/server";
import { proxyRagToBackend } from "@/lib/backend-proxy";

/** GET /api/rag/documents?source_id=... — proxy to FastAPI. */
export async function GET(request: NextRequest) {
  const query = request.nextUrl.search;
  return proxyRagToBackend(request, `/documents${query}`);
}
