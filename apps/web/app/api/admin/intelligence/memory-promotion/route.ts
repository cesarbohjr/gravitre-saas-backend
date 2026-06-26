import { NextRequest } from "next/server"
import { proxyOrDefault, DEFAULT_MEMORY_PROMOTION } from "@/lib/admin-intelligence"

export async function GET(request: NextRequest) {
  return proxyOrDefault(request, "/api/admin/intelligence/memory-promotion", DEFAULT_MEMORY_PROMOTION)
}
