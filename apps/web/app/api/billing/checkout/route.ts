import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** POST /api/billing/checkout — proxy to FastAPI. */
export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyApiToBackend(request, "/api/billing/checkout", {
    method: "POST",
    body,
  });
}
