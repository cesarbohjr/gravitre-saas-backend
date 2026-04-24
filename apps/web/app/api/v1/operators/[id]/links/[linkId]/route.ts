import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** DELETE /api/v1/operators/:id/links/:linkId */
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; linkId: string }> }
) {
  const { id, linkId } = await params;
  return proxyApiToBackend(request, `/api/v1/operators/${id}/links/${linkId}`, {
    method: "DELETE",
  });
}
