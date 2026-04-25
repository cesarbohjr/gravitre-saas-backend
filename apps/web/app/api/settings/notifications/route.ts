import { NextRequest, NextResponse } from "next/server"

export async function GET(request: NextRequest) {
  void request
  return NextResponse.json({
    notifications: {
      emailEnabled: false,
      slackEnabled: false,
      recipients: [],
    },
  })
}

export async function PATCH(request: NextRequest) {
  const body = await request.json().catch(() => ({}))
  return NextResponse.json({
    notifications: {
      emailEnabled: Boolean(body?.emailEnabled),
      slackEnabled: Boolean(body?.slackEnabled),
      recipients: Array.isArray(body?.recipients) ? body.recipients : [],
    },
  })
}
