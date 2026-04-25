import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

/** GET /api/workflows/:id — workflow definition. Forward Authorization. */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyToBackend(request, `/${id}`);
}
