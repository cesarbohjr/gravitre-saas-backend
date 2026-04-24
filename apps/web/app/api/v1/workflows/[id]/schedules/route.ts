import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

type Params = { params: { id: string } };

/** GET/POST /api/v1/workflows/:id/schedules */
export async function GET(request: NextRequest, { params }: Params) {
  return proxyApiToBackend(request, `/api/v1/workflows/${params.id}/schedules`);
}

export async function POST(request: NextRequest, { params }: Params) {
  const body = await request.text();
  return proxyApiToBackend(request, `/api/v1/workflows/${params.id}/schedules`, {
    method: "POST",
    body,
  });
}
