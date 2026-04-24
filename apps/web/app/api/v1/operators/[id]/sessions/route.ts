import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** GET /api/v1/operators/:id/sessions */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyApiToBackend(request, `/api/v1/operators/${id}/sessions`);
}

/** POST /api/v1/operators/:id/sessions */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body = await request.text();
  return proxyApiToBackend(request, `/api/v1/operators/${id}/sessions`, {
    method: "POST",
    body,
  });
}
