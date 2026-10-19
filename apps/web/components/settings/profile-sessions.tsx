"use client"

import { useState } from "react"
import useSWR from "swr"
import { Laptop, Loader2, Smartphone } from "lucide-react"
import { toast } from "sonner"
import { authApi } from "@/lib/api"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { SetError, SetIco, SetPill, SetSkeleton, formatAgo } from "@/components/settings/settings-kit"
import { describeUserAgent, SESSIONS_KEY, type AuthSession } from "@/lib/settings-api/profile"

function sessionDevice(session: AuthSession): string {
  return describeUserAgent(session.user_agent ?? session.device)
}

/** "Active sessions" card: GET /api/auth/sessions with revoke and sign out everywhere else. */
export function ProfileSessions({ enabled }: { enabled: boolean }) {
  const { data, error, isLoading, mutate } = useSWR<{ sessions: AuthSession[] }>(
    enabled ? SESSIONS_KEY : null,
    apiFetcher,
  )
  const [revoking, setRevoking] = useState<string | null>(null)
  const [confirmAll, setConfirmAll] = useState(false)
  const [isRevokingAll, setIsRevokingAll] = useState(false)
  const sessions = Array.isArray(data?.sessions) ? data.sessions : []
  const others = sessions.filter((session) => !session.current)

  const handleRevokeSession = async (session: AuthSession) => {
    setRevoking(session.id)
    try {
      await authApi.revokeSession(session.id)
      toast.success(`Signed out ${sessionDevice(session)}`)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not sign out that session")
    } finally {
      setRevoking(null)
    }
  }

  const handleRevokeAllSessions = async () => {
    setIsRevokingAll(true)
    try {
      await authApi.revokeAllSessions()
      toast.success("Signed out your other sessions")
      setConfirmAll(false)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not sign out your other sessions")
    } finally {
      setIsRevokingAll(false)
    }
  }

  return (
    <section className="gs-card pad" aria-labelledby="profile-sessions">
      <div className="profile-side-head">
        <h3 id="profile-sessions">Active sessions</h3>
        {sessions.length > 0 ? (
          <SetPill tone="green" live>
            {sessions.length} active
          </SetPill>
        ) : null}
      </div>

      {error ? (
        <SetError message="Could not load your sessions." onRetry={() => void mutate()} />
      ) : isLoading && !data ? (
        <SetSkeleton rows={2} label="Loading sessions" />
      ) : sessions.length === 0 ? (
        <p className="gs-sub" style={{ marginTop: 12 }}>
          No active sessions found.
        </p>
      ) : (
        <ul className="profile-sessions-list" style={{ listStyle: "none", padding: 0, margin: "14px 0 0" }}>
          {sessions.map((session) => {
            const device = sessionDevice(session)
            const mobile = /iOS|Android/.test(device)
            const seen = formatAgo(session.last_active)
            return (
              <li key={session.id} className="profile-session">
                <SetIco icon={mobile ? Smartphone : Laptop} tone="mute" size="sm" />
                <div className="profile-session-body">
                  <b>{device}</b>
                  <span>
                    {[session.ip, session.current ? "This device" : seen ? `Active ${seen}` : null]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </div>
                {session.current ? null : (
                  <button
                    type="button"
                    className="gs-btn text sm"
                    disabled={revoking === session.id}
                    onClick={() => void handleRevokeSession(session)}
                    aria-label={`Sign out ${device}`}
                  >
                    {revoking === session.id ? <Loader2 size={14} className="animate-spin" aria-hidden /> : null}
                    Revoke
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {others.length > 0 ? (
        <button
          type="button"
          className="gs-btn line sm"
          style={{ marginTop: 12 }}
          onClick={() => setConfirmAll(true)}
          disabled={isRevokingAll}
        >
          Sign out all other sessions
        </button>
      ) : null}

      <AlertDialog open={confirmAll} onOpenChange={setConfirmAll}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sign out all other sessions?</AlertDialogTitle>
            <AlertDialogDescription>
              Every other browser and device signed in to your account is signed out. This device stays signed in.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isRevokingAll}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={isRevokingAll}
              onClick={(event) => {
                event.preventDefault()
                void handleRevokeAllSessions()
              }}
            >
              {isRevokingAll ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
              Sign out others
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  )
}
