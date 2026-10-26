import { useEffect, useState, type ReactNode } from "react"
import { openWeb, type DesktopRelease } from "../lib/api"
import { clearPendingSignIn, formatCode, loadPendingSignIn, newSignInCode, PENDING_TTL_MS, savePendingSignIn, type PendingSignIn } from "../lib/session"
import { useStore } from "../store"
import { Icon, MarkTile, WorkspaceTile, type IconName } from "../ui"

const APP_BASE = "https://gravitre.app"
const linkFor = (code: string) => `${APP_BASE}/desktop/connect?code=${code}`

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="shell" style={{ alignItems: "center", justifyContent: "center", background: "var(--cv)" }}>
      <div className="fade" style={{ width: 380, display: "flex", flexDirection: "column", alignItems: "center", gap: 14, textAlign: "center" }}>
        {children}
      </div>
    </div>
  )
}

function Badge({ icon, tone }: { icon: IconName; tone: "ok" | "wait" | "fail" }) {
  const colors = { ok: ["var(--brs)", "var(--brk)"], wait: ["var(--aps)", "var(--apk)"], fail: ["var(--dgs)", "var(--dgk)"] }[tone]
  return (
    <span style={{ width: 40, height: 40, borderRadius: "50%", background: colors[0], color: colors[1], display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
      <Icon name={icon} size={18} />
    </span>
  )
}

const H = ({ children }: { children: ReactNode }) => <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, lineHeight: 1.2 }}>{children}</h1>
const P = ({ children }: { children: ReactNode }) => <p style={{ margin: 0, fontSize: 14, color: "var(--t2)" }}>{children}</p>

function Actions({ children }: { children: ReactNode }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%", marginTop: 18 }}>{children}</div>
}

export function SignIn({ notice }: { notice: string | null }) {
  const [pending, setPending] = useState<PendingSignIn | null>(() => loadPendingSignIn())
  const [copied, setCopied] = useState(false)

  // The browser has five minutes to answer; after that the screen says so.
  useEffect(() => {
    if (!pending || pending.expired) return
    const left = pending.startedAt + PENDING_TTL_MS - Date.now()
    const t = window.setTimeout(() => setPending(loadPendingSignIn()), Math.max(0, left) + 50)
    return () => window.clearTimeout(t)
  }, [pending])

  const start = () => {
    const code = newSignInCode()
    savePendingSignIn(code)
    setPending(loadPendingSignIn())
    setCopied(false)
    void openWeb(APP_BASE, linkFor(code))
  }

  const cancel = () => {
    clearPendingSignIn()
    setPending(null)
  }

  if (pending?.expired) {
    return (
      <Frame>
        <Badge icon="clock" tone="wait" />
        <H>Sign-in timed out</H>
        <P>We didn't hear back from your browser within 5 minutes.</P>
        <Actions>
          <button className="btn btn-p btn-lg" onClick={start}>
            Try again
          </button>
          <button
            className="btn btn-q"
            onClick={() => {
              const code = newSignInCode()
              savePendingSignIn(code)
              setPending(loadPendingSignIn())
              void navigator.clipboard
                .writeText(linkFor(code))
                .then(() => setCopied(true))
                .catch(() => setCopied(false))
            }}
          >
            Copy sign-in link
          </button>
        </Actions>
      </Frame>
    )
  }

  if (pending) {
    return (
      <Frame>
        <MarkTile size={40} />
        <H>Finish signing in in your browser</H>
        <P>We opened gravitre.app. Check that it shows this code, then confirm there.</P>
        <span className="mono" style={{ fontSize: 26, fontWeight: 600, letterSpacing: ".12em", padding: "8px 14px", borderRadius: 10, border: "1px solid var(--bd)", background: "var(--s1)" }}>
          {formatCode(pending.code)}
        </span>
        {copied ? <span className="sub">Sign-in link copied. Paste it into the browser where you're signed in.</span> : null}
        {notice ? (
          <p role="alert" style={{ margin: 0, fontSize: 13, color: "var(--dgk)" }}>
            {notice}
          </p>
        ) : null}
        <Actions>
          <button className="btn btn-p btn-lg" onClick={() => void openWeb(APP_BASE, linkFor(pending.code))}>
            Open browser again
          </button>
          <button className="btn btn-q" onClick={cancel}>
            Cancel
          </button>
        </Actions>
      </Frame>
    )
  }

  return (
    <Frame>
      <MarkTile size={40} />
      <H>Sign in to Gravitre</H>
      <P>Sign-in happens on gravitre.app, so your company's single sign-on works as usual.</P>
      {notice ? (
        <p role="status" style={{ margin: 0, fontSize: 13, color: "var(--t2)" }}>
          {notice}
        </p>
      ) : null}
      <Actions>
        <button className="btn btn-p btn-lg" onClick={start}>
          Sign in with your browser
        </button>
      </Actions>
    </Frame>
  )
}

/** Shown once, right after the browser hands the session back. */
export function SignedIn({ onDone }: { onDone: () => void }) {
  const { me, session } = useStore()
  const ws = me?.organizations.find((o) => o.id === session.orgId)
  return (
    <Frame>
      <Badge icon="check" tone="ok" />
      <H>You're signed in</H>
      <P>Gravitre will open at login and keep your approvals one click away.</P>
      {me ? (
        <span className="chip" style={{ height: 34, padding: "0 10px 0 6px", borderRadius: 10, fontSize: 13 }}>
          <WorkspaceTile name={ws?.name || "Workspace"} size={22} />
          {[ws?.name, me.email].filter(Boolean).join(" · ")}
        </span>
      ) : null}
      <Actions>
        <button className="btn btn-p btn-lg" autoFocus onClick={onDone}>
          Get started
        </button>
      </Actions>
    </Frame>
  )
}

/** This build is older than the oldest version gravitre.app still supports. */
export function Unsupported({ release }: { release: DesktopRelease }) {
  const { web } = useStore()
  return (
    <Frame>
      <Badge icon="alert" tone="fail" />
      <H>This version is no longer supported</H>
      <P>Update to keep using Gravitre. Your conversations and approvals are safe on the server.</P>
      <Actions>
        <button className="btn btn-p btn-lg" onClick={() => web("/download")}>
          Update now
        </button>
        {release.notes ? (
          <button className="btn btn-q" onClick={() => web(release.notes!)}>
            What's new
          </button>
        ) : null}
      </Actions>
    </Frame>
  )
}
