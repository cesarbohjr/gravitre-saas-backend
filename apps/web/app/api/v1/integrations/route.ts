import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** GET/POST /api/v1/integrations */
export async function GET(request: NextRequest) {
  return proxyApiToBackend(request, "/api/v1/integrations");
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyApiToBackend(request, "/api/v1/integrations", {
    method: "POST",
    body,
  });
}
