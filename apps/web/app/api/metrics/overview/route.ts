import { NextRequest } from "next/server";
import { proxyMetricsToBackend } from "@/lib/backend-proxy";

/** GET /api/metrics/overview — proxy to FastAPI. */
export async function GET(request: NextRequest) {
  const query = request.nextUrl.search;
  return proxyMetricsToBackend(request, `/overview${query}`);
}
