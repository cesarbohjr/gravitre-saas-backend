import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

type Params = { params: { id: string } };

/** POST /api/v1/integrations/:id/secrets */
export async function POST(request: NextRequest, { params }: Params) {
  const body = await request.text();
  return proxyApiToBackend(request, `/api/v1/integrations/${params.id}/secrets`, {
    method: "POST",
    body,
  });
}
