/**
 * Is the production voice WebSocket reachable at all?
 *
 * The reconnect ladder now surfaces "Voice connection interrupted" only after three
 * genuine failures, so the toast still appearing means the socket really cannot
 * connect. This distinguishes the possible reasons:
 *
 *   handshake refused / 404 / 502   -> endpoint not reachable, `error` fires
 *   accepted then close(1008)       -> reachable, auth rejected (expected here)
 *
 * Run: node scripts/probe-live-voice-ws.mjs
 */
import { WebSocket } from "ws"

const BASES = [
  "wss://gravitre-saas-backend-production.up.railway.app",
  "wss://gravitre.app",
]
const PATH = "/api/voice/pipecat/ws?access_token=probe-invalid&org_id=probe"

for (const base of BASES) {
  const url = base + PATH
  const events = []
  let closeInfo = ""
  let httpStatus = ""

  await new Promise((resolve) => {
    const ws = new WebSocket(url, { handshakeTimeout: 15000 })
    const done = () => resolve()

    // Fires when the server answers the upgrade with a normal HTTP response.
    ws.on("unexpected-response", (_req, res) => {
      httpStatus = `HTTP ${res.statusCode}`
      events.push("unexpected-response")
      ws.terminate()
      done()
    })
    ws.on("open", () => events.push("open"))
    ws.on("error", (err) => {
      events.push("error")
      if (!httpStatus) httpStatus = err.message
    })
    ws.on("message", (data) => {
      const text = String(data).slice(0, 160)
      events.push(`message:${text}`)
    })
    ws.on("close", (code, reason) => {
      events.push("close")
      closeInfo = `code=${code} reason=${String(reason).slice(0, 120)}`
      done()
    })
    setTimeout(done, 16000)
  })

  console.log(`\n${base}`)
  console.log(`  events : ${events.join(" -> ") || "(none)"}`)
  console.log(`  close  : ${closeInfo || "(none)"}`)
  console.log(`  detail : ${httpStatus || "(none)"}`)

  if (events.includes("open")) {
    console.log("  VERDICT: endpoint reachable (upgrade accepted)")
  } else {
    console.log("  VERDICT: upgrade NOT accepted -- this is what fires ws.onerror")
  }
}
