import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend-proxy";

/** DELETE /api/workflows/edges/:edgeId */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ edgeId: string }> }
) {
  const { edgeId } = await params;
  return proxyToBackend(request, `/edges/${edgeId}`, {
    method: "DELETE",
  });
}
