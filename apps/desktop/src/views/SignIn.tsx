import { useState } from "react"
import { openWeb } from "../lib/api"
import { clearPendingSignIn, formatCode, loadPendingSignIn, newSignInCode, savePendingSignIn } from "../lib/session"
import { Mark } from "../ui"

const APP_BASE = "https://gravitre.app"

export function SignIn({ notice }: { notice: string | null }) {
  const [code, setCode] = useState<string | null>(() => loadPendingSignIn())

  const start = () => {
    const next = newSignInCode()
    savePendingSignIn(next)
    setCode(next)
    void openWeb(APP_BASE, `/desktop/connect?code=${next}`)
  }

  return (
    <div className="shell" style={{ background: "var(--s3)", alignItems: "center", justifyContent: "center" }}>
      <div className="fade" style={{ width: 440, padding: 36, borderRadius: 20, background: "var(--s1)", border: "1px solid var(--bd)", boxShadow: "var(--el)", display: "flex", flexDirection: "column", gap: 14 }}>
        <Mark width={36} height={21} />
        <span className="eyebrow">Desktop · sign in</span>
        {code ? (
          <>
            <h1 className="h1" style={{ fontSize: 26 }}>
              Finish signing in in your browser
            </h1>
            <p className="lede" style={{ fontSize: 15 }}>
              We opened gravitre.app. Check that it shows this code, then click Authorize Desktop there.
            </p>
            <span className="mono" style={{ fontSize: 26, fontWeight: 600, letterSpacing: ".14em", padding: "10px 16px", borderRadius: 12, background: "var(--s2)", alignSelf: "flex-start" }}>
              {formatCode(code)}
            </span>
            {notice ? (
              <p role="alert" style={{ margin: 0, fontSize: 13, color: "var(--dgk)" }}>
                {notice}
              </p>
            ) : null}
            <button className="btn btn-k" onClick={() => void openWeb(APP_BASE, `/desktop/connect?code=${code}`)}>
              Open the browser again
            </button>
            <button
              className="btn btn-q"
              onClick={() => {
                clearPendingSignIn()
                setCode(null)
              }}
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <h1 className="h1" style={{ fontSize: 26 }}>
              Sign in to Gravitre
            </h1>
            <p className="lede" style={{ fontSize: 15 }}>
              Sign-in happens on gravitre.app, so your company's single sign-on works as usual.
            </p>
            {notice ? (
              <p role="status" style={{ margin: 0, fontSize: 13, color: "var(--t2)" }}>
                {notice}
              </p>
            ) : null}
            <button className="btn btn-k" onClick={start}>
              Sign in with your browser
            </button>
          </>
        )}
      </div>
    </div>
  )
}
