import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

/** GET/POST /api/workflows/:id/edges */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyToBackend(request, `/${id}/edges`);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.text();
  return proxyToBackend(request, `/${id}/edges`, {
    method: "POST",
    body,
  });
}
