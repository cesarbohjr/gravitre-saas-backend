import { NextRequest } from "next/server";
import { proxyAuditToBackend } from "@/lib/backend-proxy";

/** GET /api/audit — proxy to FastAPI; forwards Authorization and query params. */
export async function GET(request: NextRequest) {
  const queryString = request.nextUrl.search;
  return proxyAuditToBackend(request, queryString);
}
