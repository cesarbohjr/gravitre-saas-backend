import { afterEach, describe, expect, it } from "vitest"
import { WebSocket, WebSocketServer } from "ws"
import {
  VOICE_GENERIC_FAILURE_MESSAGE,
  VOICE_RECONNECT_MAX_ATTEMPTS,
  decideSocketFailure,
  isTerminalServerErrorClass,
  reconnectDelayMs,
  resolveFailureMessage,
} from "@/lib/voice-socket-reconnect"

/**
 * Cover for the "Voice connection interrupted" toast.
 *
 * Confirmed cause, measured against a real server by
 * scripts/probe-ws-error-conditions.mjs: `onerror` fires when a socket is closed
 * before its handshake completes, and `teardownMic()` closes unconditionally. So a
 * hangup the user asked for -- which the old mute button performed on every press --
 * reached the same handler as a real fault and toasted them about it.
 *
 * The pure tests pin the decision table. The integration tests below drive real
 * sockets against a real server, because a policy that only ever sees fake events
 * is exactly how this class of bug survived the last two passes.
 */

describe("decideSocketFailure", () => {
  const base = { sessionActive: true, attempt: 0, everOpened: true, intentional: false }

  it("ignores a deliberate teardown, whatever else is true", () => {
    // The regression itself. Intent outranks every other input, including a socket
    // that never opened and an exhausted attempt budget.
    for (const sessionActive of [true, false]) {
      for (const everOpened of [true, false]) {
        for (const attempt of [0, VOICE_RECONNECT_MAX_ATTEMPTS + 5]) {
          const d = decideSocketFailure({ intentional: true, sessionActive, everOpened, attempt })
          expect(d.action).toBe("ignore")
          expect(d).toMatchObject({ reason: "intentional" })
        }
      }
    }
  })

  it("ignores a failure for a session nobody is waiting on", () => {
    const d = decideSocketFailure({ ...base, sessionActive: false })
    expect(d).toEqual({ action: "ignore", reason: "session-ended" })
  })

  it("retries a genuine fault before telling the user anything", () => {
    const d = decideSocketFailure(base)
    expect(d.action).toBe("reconnect")
  })

  it("surfaces the error only once the ladder is spent", () => {
    // Every attempt below the cap retries; the first at the cap surfaces.
    for (let attempt = 0; attempt < VOICE_RECONNECT_MAX_ATTEMPTS; attempt += 1) {
      expect(decideSocketFailure({ ...base, attempt }).action).toBe("reconnect")
    }
    const final = decideSocketFailure({ ...base, attempt: VOICE_RECONNECT_MAX_ATTEMPTS })
    expect(final).toEqual({
      action: "surface-error",
      reason: "retries-exhausted",
      attempts: VOICE_RECONNECT_MAX_ATTEMPTS,
    })
  })

  it("retries a socket that never opened, so a refused first connect is not silent", () => {
    // sessionWanted is set before the first await precisely so this case is covered.
    const d = decideSocketFailure({ ...base, everOpened: false })
    expect(d.action).toBe("reconnect")
  })

  it("advances the attempt counter so the ladder terminates", () => {
    let attempt = 0
    const seen: number[] = []
    for (let i = 0; i < 20; i += 1) {
      const d = decideSocketFailure({ ...base, attempt })
      if (d.action !== "reconnect") break
      seen.push(d.delayMs)
      attempt = d.attempt
    }
    expect(seen).toHaveLength(VOICE_RECONNECT_MAX_ATTEMPTS)
    expect(attempt).toBe(VOICE_RECONNECT_MAX_ATTEMPTS)
  })
})

describe("reconnectDelayMs", () => {
  it("backs off exponentially and then caps", () => {
    expect(reconnectDelayMs(0, { baseMs: 100, maxMs: 1000 })).toBe(100)
    expect(reconnectDelayMs(1, { baseMs: 100, maxMs: 1000 })).toBe(200)
    expect(reconnectDelayMs(2, { baseMs: 100, maxMs: 1000 })).toBe(400)
    expect(reconnectDelayMs(9, { baseMs: 100, maxMs: 1000 })).toBe(1000)
  })

  it("never returns a negative or NaN delay for junk input", () => {
    expect(reconnectDelayMs(-5, { baseMs: 100 })).toBe(100)
    expect(Number.isFinite(reconnectDelayMs(1.7, { baseMs: 100 }))).toBe(true)
  })

  it("keeps jitter inside half the capped delay", () => {
    for (const r of [0, 0.5, 1]) {
      const d = reconnectDelayMs(2, { baseMs: 100, maxMs: 1000, jitter: () => r })
      expect(d).toBeGreaterThanOrEqual(200)
      expect(d).toBeLessThanOrEqual(400)
    }
  })
})

describe("isTerminalServerErrorClass", () => {
  it("treats refusals as settled so the user is not made to wait out retries", () => {
    for (const c of ["auth", "forbidden", "not_enabled", "not_configured", "billing"]) {
      expect(isTerminalServerErrorClass(c)).toBe(true)
    }
  })

  it("does not treat an unknown or absent class as terminal", () => {
    for (const c of [undefined, null, "", "transient", 42, {}]) {
      expect(isTerminalServerErrorClass(c)).toBe(false)
    }
  })
})

// ---------------------------------------------------------------------------
// Real sockets.
// ---------------------------------------------------------------------------

type Attempt = { surfaced: string[]; attempts: number; opened: boolean }

const servers: WebSocketServer[] = []
afterEach(() => {
  for (const s of servers.splice(0)) s.close()
})

function startServer(port: number): Promise<WebSocketServer> {
  return new Promise((resolve, reject) => {
    const wss = new WebSocketServer({ port }, () => {
      servers.push(wss)
      resolve(wss)
    })
    wss.on("error", reject)
  })
}

async function freePort(): Promise<number> {
  const probe = new WebSocketServer({ port: 0 })
  await new Promise((r) => probe.on("listening", r))
  const port = (probe.address() as { port: number }).port
  await new Promise((r) => probe.close(r))
  return port
}

/**
 * The hook's loop, reduced to its transport behaviour: connect, and on failure ask
 * the policy whether to ignore, retry, or surface. Deliberately mirrors the hook so
 * the assertions below are about the shipped decision path, not a parallel one.
 */
function connectWithPolicy(opts: {
  url: string
  wantSession: () => boolean
  intentional: () => boolean
  maxAttempts?: number
}): Promise<Attempt> {
  return new Promise((resolve) => {
    const surfaced: string[] = []
    let attempt = 0
    let opened = false
    let settled = false

    const finish = () => {
      if (settled) return
      settled = true
      resolve({ surfaced, attempts: attempt, opened })
    }

    const dial = () => {
      const ws = new WebSocket(opts.url)
      let handled = false

      const onFailure = () => {
        if (handled) return
        handled = true
        const decision = decideSocketFailure({
          intentional: opts.intentional(),
          sessionActive: opts.wantSession(),
          attempt,
          everOpened: opened,
          maxAttempts: opts.maxAttempts,
          baseDelayMs: 5,
          maxDelayMs: 20,
        })
        if (decision.action === "ignore") return finish()
        if (decision.action === "reconnect") {
          attempt = decision.attempt
          setTimeout(dial, decision.delayMs)
          return
        }
        surfaced.push("Voice connection interrupted")
        finish()
      }

      ws.onopen = () => {
        opened = true
        ws.close()
        finish()
      }
      ws.onerror = onFailure
      ws.onclose = onFailure
    }

    dial()
  })
}

describe("reconnect against real sockets", () => {
  it("recovers when the connection becomes available again", async () => {
    // Nothing listening yet, so the first dials genuinely fail (error -> close).
    const port = await freePort()
    const url = `ws://127.0.0.1:${port}`
    setTimeout(() => void startServer(port), 30)

    const result = await connectWithPolicy({
      url,
      wantSession: () => true,
      intentional: () => false,
      maxAttempts: 8,
    })

    expect(result.opened).toBe(true)
    expect(result.attempts).toBeGreaterThan(0)
    // The whole point: the user is never told about a fault we recovered from.
    expect(result.surfaced).toEqual([])
  })

  it("surfaces the error exactly once when the connection never recovers", async () => {
    const port = await freePort()
    const result = await connectWithPolicy({
      url: `ws://127.0.0.1:${port}`,
      wantSession: () => true,
      intentional: () => false,
      maxAttempts: 3,
    })

    expect(result.opened).toBe(false)
    expect(result.attempts).toBe(3)
    expect(result.surfaced).toEqual(["Voice connection interrupted"])
  })

  it("stays silent for a deliberate hangup mid-handshake", async () => {
    // The reported regression, end to end: a real server exists and would have
    // connected, but the app closes during CONNECTING, which raises `error`.
    const port = await freePort()
    await startServer(port)

    const surfaced: string[] = []
    let intentional = false

    await new Promise<void>((resolve) => {
      const ws = new WebSocket(`ws://127.0.0.1:${port}`)
      const onFailure = () => {
        const decision = decideSocketFailure({
          intentional,
          // Deliberately still "wanted". teardownMic() runs with sessionWanted true
          // on the reconnect path, so intent is the only thing standing between a
          // deliberate close and a spurious toast -- isolate it here rather than
          // letting the session-ended guard mask a missing intent check.
          sessionActive: true,
          attempt: 0,
          everOpened: false,
          baseDelayMs: 5,
        })
        if (decision.action === "reconnect") surfaced.push("unexpected-retry")
        if (decision.action === "surface-error") surfaced.push("Voice connection interrupted")
        resolve()
      }
      ws.onerror = onFailure
      ws.onclose = onFailure
      // What teardownMic() does, with intent recorded first.
      intentional = true
      ws.close()
    })

    expect(surfaced).toEqual([])
  })
})

describe("resolveFailureMessage", () => {
  it("repeats what the server said rather than the generic string", () => {
    // The defect this pins: `service_failure` (every STT provider failed to start)
    // is retryable, so the server's explanation arrived, the ladder ran, and the
    // final toast replaced an accurate message with strictly less information.
    expect(resolveFailureMessage("Deepgram flux failed to start")).toBe(
      "Deepgram flux failed to start",
    )
  })

  it("falls back to the generic string when the socket died silently", () => {
    expect(resolveFailureMessage(null)).toBe(VOICE_GENERIC_FAILURE_MESSAGE)
    expect(resolveFailureMessage(undefined)).toBe(VOICE_GENERIC_FAILURE_MESSAGE)
  })

  it("treats a blank or whitespace-only server message as no message", () => {
    expect(resolveFailureMessage("")).toBe(VOICE_GENERIC_FAILURE_MESSAGE)
    expect(resolveFailureMessage("   \n")).toBe(VOICE_GENERIC_FAILURE_MESSAGE)
  })

  it("keeps service_failure retryable, which is why the ladder runs at all", () => {
    expect(isTerminalServerErrorClass("service_failure")).toBe(false)
    expect(isTerminalServerErrorClass("auth")).toBe(true)
  })
})
