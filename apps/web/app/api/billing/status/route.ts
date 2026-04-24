import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** GET /api/billing/status — proxy to FastAPI. */
export async function GET(request: NextRequest) {
  return proxyApiToBackend(request, "/api/billing/status");
}
