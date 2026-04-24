import { NextRequest } from "next/server";
import { proxyRagToBackend } from "@/lib/backend-proxy";

/** POST /api/rag/ingest — proxy to FastAPI. */
export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyRagToBackend(request, "/ingest", { method: "POST", body });
}
