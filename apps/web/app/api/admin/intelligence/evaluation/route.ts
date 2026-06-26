import { NextRequest } from "next/server"
import { proxyOrDefault, DEFAULT_EVALUATION } from "@/lib/admin-intelligence"

export async function GET(request: NextRequest) {
  return proxyOrDefault(request, "/api/admin/intelligence/evaluation", DEFAULT_EVALUATION)
}
