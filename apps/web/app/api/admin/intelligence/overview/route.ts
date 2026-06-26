import { NextRequest } from "next/server"
import { proxyOrDefault, DEFAULT_OVERVIEW } from "@/lib/admin-intelligence"

export async function GET(request: NextRequest) {
  return proxyOrDefault(request, "/api/admin/intelligence/overview", DEFAULT_OVERVIEW)
}
