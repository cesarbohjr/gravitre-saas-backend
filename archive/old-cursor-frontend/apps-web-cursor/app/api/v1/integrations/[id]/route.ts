import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

type Params = { params: { id: string } };

/** GET/PATCH /api/v1/integrations/:id */
export async function GET(request: NextRequest, { params }: Params) {
  return proxyApiToBackend(request, `/api/v1/integrations/${params.id}`);
}

export async function PATCH(request: NextRequest, { params }: Params) {
  const body = await request.text();
  return proxyApiToBackend(request, `/api/v1/integrations/${params.id}`, {
    method: "PATCH",
    body,
  });
}
