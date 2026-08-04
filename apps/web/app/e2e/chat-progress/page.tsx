import { notFound } from "next/navigation"

import { ChatProgressHarness } from "./harness"

export default async function ChatProgressE2EPage() {
  if (
    process.env.NEXT_PUBLIC_PLAYWRIGHT_E2E !== "1" &&
    process.env.PLAYWRIGHT_E2E !== "1"
  ) {
    notFound()
  }

  return <ChatProgressHarness />
}
