/**
 * Which real socket transitions fire `onerror`?
 *
 * The "Voice connection interrupted" toast is wired to ws.onerror with nothing
 * distinguishing a deliberate hangup from a real fault. This probe establishes,
 * against a real server, which transitions actually reach that handler -- so the
 * reconnect policy is built on observed behaviour rather than assumption.
 *
 * Run: node scripts/probe-ws-error-conditions.mjs
 */
import { WebSocket, WebSocketServer } from "ws"

const results = []

function record(name, events) {
  results.push({ name, events: events.join(" -> ") || "(none)" })
}

function listen() {
  return new Promise((resolve) => {
    const wss = new WebSocketServer({ port: 0 }, () => resolve(wss))
  })
}

/** Deliberate close() while still CONNECTING -- the old mute/stop path. */
async function closeWhileConnecting() {
  const wss = await listen()
  const url = `ws://127.0.0.1:${wss.address().port}`
  const events = []
  await new Promise((resolve) => {
    const ws = new WebSocket(url)
    ws.onerror = () => events.push("error")
    ws.onclose = () => {
      events.push("close")
      resolve()
    }
    ws.onopen = () => events.push("open")
    // Same instant, before the handshake can complete.
    ws.close()
  })
  record("close() while CONNECTING", events)
  wss.close()
}

/** Deliberate close() after the socket is OPEN -- mute after connect. */
async function closeWhileOpen() {
  const wss = await listen()
  const url = `ws://127.0.0.1:${wss.address().port}`
  const events = []
  await new Promise((resolve) => {
    const ws = new WebSocket(url)
    ws.onerror = () => events.push("error")
    ws.onclose = () => {
      events.push("close")
      resolve()
    }
    ws.onopen = () => {
      events.push("open")
      ws.close()
    }
  })
  record("close() while OPEN", events)
  wss.close()
}

/** Server vanishes mid-session -- a redeploy or crash. */
async function serverDropsConnection() {
  const wss = await listen()
  const url = `ws://127.0.0.1:${wss.address().port}`
  const events = []
  wss.on("connection", (sock) => {
    // Destroy the underlying socket: no close frame, an unclean teardown.
    sock.terminate()
  })
  await new Promise((resolve) => {
    const ws = new WebSocket(url)
    ws.onerror = () => events.push("error")
    ws.onclose = () => {
      events.push("close")
      resolve()
    }
    ws.onopen = () => events.push("open")
  })
  record("server terminates socket (unclean)", events)
  wss.close()
}

/** Server refuses the upgrade -- the router's auth/forbidden 1008 path. */
async function serverClosesCleanlyWithCode() {
  const wss = await listen()
  const url = `ws://127.0.0.1:${wss.address().port}`
  const events = []
  wss.on("connection", (sock) => {
    sock.send(JSON.stringify({ type: "error", error_class: "auth" }))
    sock.close(1008, "auth")
  })
  await new Promise((resolve) => {
    const ws = new WebSocket(url)
    ws.onerror = () => events.push("error")
    ws.onclose = () => {
      events.push("close")
      resolve()
    }
    ws.onopen = () => events.push("open")
  })
  record("server close(1008) after error frame", events)
  wss.close()
}

/** Nothing listening at all. */
async function connectionRefused() {
  const events = []
  await new Promise((resolve) => {
    // Port 1 is reserved and will refuse.
    const ws = new WebSocket("ws://127.0.0.1:1")
    ws.onerror = () => events.push("error")
    ws.onclose = () => {
      events.push("close")
      resolve()
    }
    ws.onopen = () => events.push("open")
  })
  record("connection refused", events)
}

await closeWhileConnecting()
await closeWhileOpen()
await serverDropsConnection()
await serverClosesCleanlyWithCode()
await connectionRefused()

for (const r of results) {
  console.log(`${r.name.padEnd(38)} : ${r.events}`)
}
