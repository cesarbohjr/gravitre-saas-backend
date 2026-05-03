import { NextResponse } from "next/server"
import { getDemoStore } from "@/lib/demo-runtime-store"

export async function GET() {
  return NextResponse.json({ approvals: getDemoStore().approvals })
}
