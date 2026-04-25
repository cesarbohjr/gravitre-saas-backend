import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** GET /api/v1/approvals/pending */
export async function GET(request: NextRequest) {
  return proxyApiToBackend(request, "/api/v1/approvals/pending");
}
