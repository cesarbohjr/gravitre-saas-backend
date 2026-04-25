import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

/** GET /api/workflows — list workflows for org. Forward Authorization. */
export async function GET(request: NextRequest) {
  return proxyToBackend(request, "");
}
