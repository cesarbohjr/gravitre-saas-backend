import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** POST /api/v1/workflows/runs/:id/approve */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.text();
  return proxyApiToBackend(request, `/api/v1/workflows/runs/${id}/approve`, {
    method: "POST",
    body,
  });
}
