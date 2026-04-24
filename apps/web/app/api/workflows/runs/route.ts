import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

/** GET /api/workflows/runs — list runs with filters. */
export async function GET(request: NextRequest) {
  const search = request.nextUrl.search;
  return proxyToBackend(request, `/runs${search}`);
}
