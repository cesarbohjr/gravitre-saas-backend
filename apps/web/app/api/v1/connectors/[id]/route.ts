import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** GET/PATCH /api/v1/connectors/:id (legacy alias to integrations) */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyApiToBackend(request, `/api/v1/integrations/${id}`);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.text();
  return proxyApiToBackend(request, `/api/v1/integrations/${id}`, {
    method: "PATCH",
    body,
  });
}
