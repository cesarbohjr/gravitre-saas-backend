import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

type Params = { params: { id: string } };

/** POST /api/v1/workflows/runs/:id/rollback */
export async function POST(request: NextRequest, { params }: Params) {
  return proxyApiToBackend(request, `/api/v1/workflows/runs/${params.id}/rollback`, {
    method: "POST",
  });
}
