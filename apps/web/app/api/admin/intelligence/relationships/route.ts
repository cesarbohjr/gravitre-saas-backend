import { NextRequest } from "next/server"
import { proxyOrDefault, DEFAULT_RELATIONSHIPS } from "@/lib/admin-intelligence"

export async function GET(request: NextRequest) {
  return proxyOrDefault(request, "/api/admin/intelligence/relationships", DEFAULT_RELATIONSHIPS)
}
