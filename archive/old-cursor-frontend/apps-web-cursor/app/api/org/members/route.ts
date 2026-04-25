import { NextRequest } from "next/server";
import { proxyOrgToBackend } from "@/lib/backend-proxy";

/** GET /api/org/members — proxy to FastAPI. */
export async function GET(request: NextRequest) {
  return proxyOrgToBackend(request, "/members");
}
