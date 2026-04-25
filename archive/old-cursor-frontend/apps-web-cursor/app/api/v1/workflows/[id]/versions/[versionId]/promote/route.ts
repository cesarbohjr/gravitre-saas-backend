import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** POST /api/v1/workflows/:id/versions/:versionId/promote */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; versionId: string }> }
) {
  const { id, versionId } = await params;
  const body = await request.text();
  return proxyApiToBackend(
    request,
    `/api/v1/workflows/${id}/versions/${versionId}/promote`,
    { method: "POST", body }
  );
}
