import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** POST /api/billing/portal — proxy to FastAPI. */
export async function POST(request: NextRequest) {
  return proxyApiToBackend(request, "/api/billing/portal", { method: "POST" });
}
