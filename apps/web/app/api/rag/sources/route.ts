import { NextRequest } from "next/server";
import { proxyRagToBackend } from "@/lib/backend-proxy";

/** GET/POST /api/rag/sources — proxy to FastAPI. */
export async function GET(request: NextRequest) {
  return proxyRagToBackend(request, "/sources");
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyRagToBackend(request, "/sources", { method: "POST", body });
}
