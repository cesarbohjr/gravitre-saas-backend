import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

/** PATCH/DELETE /api/workflows/nodes/:nodeId */
export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ nodeId: string }> }
) {
  const { nodeId } = await params;
  const body = await request.text();
  return proxyToBackend(request, `/nodes/${nodeId}`, {
    method: "PATCH",
    body,
  });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ nodeId: string }> }
) {
  const { nodeId } = await params;
  return proxyToBackend(request, `/nodes/${nodeId}`, {
    method: "DELETE",
  });
}
