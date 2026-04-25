import { NextRequest } from "next/server";
import { proxyApiToBackend } from "@/lib/backend-proxy";

type Params = { params: { scheduleId: string } };

/** PATCH /api/v1/workflows/schedules/:scheduleId */
export async function PATCH(request: NextRequest, { params }: Params) {
  const body = await request.text();
  return proxyApiToBackend(request, `/api/v1/workflows/schedules/${params.scheduleId}`, {
    method: "PATCH",
    body,
  });
}
