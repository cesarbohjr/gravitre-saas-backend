import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

/** POST /api/workflows/dry-run — dry-run with body { workflow_id?, definition?, parameters? }. */
export async function POST(request: NextRequest) {
  const body = await request.text();
  return proxyToBackend(request, "/dry-run", { method: "POST", body });
}
