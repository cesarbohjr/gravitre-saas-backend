import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** POST /api/v1/workflows/:id/versions/:versionId/activate */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; versionId: string }> }
) {
  const { id, versionId } = await params;
  return proxyApiToBackend(
    request,
    `/api/v1/workflows/${id}/versions/${versionId}/activate`,
    { method: "POST" }
  );
}
