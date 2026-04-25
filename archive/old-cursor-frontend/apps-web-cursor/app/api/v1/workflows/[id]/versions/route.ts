import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

/** GET/POST /api/v1/workflows/:id/versions */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyApiToBackend(request, `/api/v1/workflows/${id}/versions`);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyApiToBackend(request, `/api/v1/workflows/${id}/versions`, {
    method: "POST",
  });
}
