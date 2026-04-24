import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** POST /api/v1/operator/action-plan */
export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyApiToBackend(request, "/api/v1/operator/action-plan", {
    method: "POST",
    body,
  });
}
