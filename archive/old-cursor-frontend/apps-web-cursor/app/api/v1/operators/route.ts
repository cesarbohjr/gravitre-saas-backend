import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** GET /api/v1/operators */
export async function GET(request: NextRequest) {
  return proxyApiToBackend(request, "/api/v1/operators");
}

/** POST /api/v1/operators */
export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyApiToBackend(request, "/api/v1/operators", {
    method: "POST",
    body,
  });
}
