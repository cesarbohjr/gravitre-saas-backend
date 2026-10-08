"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { List, Plus } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { type DemoAssignment } from "@/lib/demo-assignments"
import { ASSIGNMENTS_REFRESH_KEY, fetchAssignmentList } from "@/lib/assignments-list"
import { useWorkPageShortcut } from "@/hooks/use-work-page-shortcut"
import { useAuth } from "@/lib/auth-context"
import { SURFACE_COPY } from "@/lib/surface-copy"
import {
  AssignComposer,
  AssignmentListView,
  BoardLanes,
  LANES,
  laneOf,
  type LaneId,
} from "@/components/assignments/assignments-board"
import "@/components/assignments/assignments-workspace.css"

const ASSIGNMENTS_REFRESH_MS = 15_000
const VIEW_KEY = "gravitre.assignments.view"

type ViewMode = "board" | "list"

function BoardIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <rect x="3.5" y="4" width="5" height="16" rx="1" />
      <rect x="10.5" y="4" width="5" height="11" rx="1" />
      <rect x="17.5" y="4" width="3" height="7" rx="1" />
    </svg>
  )
}

function readStoredView(): ViewMode {
  try {
    return window.localStorage.getItem(VIEW_KEY) === "list" ? "list" : "board"
  } catch {
    return "board"
  }
}

export default function AssignmentsPage() {
  const { user } = useAuth()
  const composerRef = useRef<HTMLInputElement | null>(null)
  const [localAssignments, setLocalAssignments] = useState<DemoAssignment[]>([])
  const [view, setView] = useState<ViewMode>("board")

  useEffect(() => {
    setView(readStoredView())
  }, [])

  const chooseView = (next: ViewMode) => {
    setView(next)
    try {
      window.localStorage.setItem(VIEW_KEY, next)
    } catch {
      // Remembering the view is a convenience only.
    }
  }

  const {
    data: fetchedAssignments,
    error: assignmentsError,
    isLoading: assignmentsLoading,
    mutate: refreshAssignments,
  } = useSWR<DemoAssignment[]>(user ? ASSIGNMENTS_REFRESH_KEY : null, fetchAssignmentList, {
    revalidateOnFocus: true,
    refreshInterval: ASSIGNMENTS_REFRESH_MS,
  })

  const assignmentList = useMemo(() => {
    const base = fetchedAssignments ?? []
    const seen = new Set(base.map((item) => item.id))
    const locals = localAssignments.filter((item) => !seen.has(item.id))
    return [...locals, ...base]
  }, [fetchedAssignments, localAssignments])

  const byLane = useMemo(() => {
    const groups = new Map<LaneId, DemoAssignment[]>(LANES.map((lane) => [lane.id, []]))
    for (const assignment of assignmentList) groups.get(laneOf(assignment))?.push(assignment)
    return groups
  }, [assignmentList])

  const focusComposer = useCallback(() => {
    const input = composerRef.current
    if (!input) return
    input.scrollIntoView({ behavior: "smooth", block: "center" })
    input.focus({ preventScroll: true })
  }, [])
  useWorkPageShortcut("new", focusComposer)

  const handleCreated = (assignment: DemoAssignment) => {
    setLocalAssignments((current) => [assignment, ...current.filter((item) => item.id !== assignment.id)])
    void refreshAssignments()
  }

  const loading = Boolean(user) && assignmentsLoading && !fetchedAssignments
  const executing = byLane.get("running")?.length ?? 0
  const waiting = byLane.get("waiting")?.length ?? 0
  const needsLook = (byLane.get("delivered") ?? []).filter((item) => item.flag?.needsLook).length

  return (
    <AppShell title={SURFACE_COPY.pages.assignments.title}>
      <WsPage>
        <div className="asg-head">
          <div className="asg-head-main">
            <div className="gv-eyebrow">One off work for your agents</div>
            <h1 className="asg-title">{SURFACE_COPY.pages.assignments.title}</h1>
            <div className="asg-counts" aria-live="polite">
              {loading ? (
                <span>Loading assignments</span>
              ) : (
                <>
                  <span className="asg-count">
                    <span className="asg-dot running" aria-hidden />
                    <strong>{executing}</strong> executing
                  </span>
                  <span className="asg-count">
                    <span className="asg-dot waiting" aria-hidden />
                    <strong>{waiting}</strong> waiting on you
                  </span>
                  <span className="asg-count">
                    <span className="asg-dot delivered" aria-hidden />
                    <strong>{needsLook}</strong> delivered, needs a look
                  </span>
                </>
              )}
            </div>
          </div>
          <div className="asg-head-actions">
            <div role="group" aria-label="View" className="asg-viewtoggle">
              <button
                type="button"
                className={`asg-viewbtn${view === "board" ? " on" : ""}`}
                aria-label="Board view"
                aria-pressed={view === "board"}
                onClick={() => chooseView("board")}
              >
                <BoardIcon />
              </button>
              <button
                type="button"
                className={`asg-viewbtn${view === "list" ? " on" : ""}`}
                aria-label="List view"
                aria-pressed={view === "list"}
                onClick={() => chooseView("list")}
              >
                <List size={18} aria-hidden />
              </button>
            </div>
            <Link href="/assignments/new" className="gv-btn primary">
              <Plus size={18} aria-hidden />
              New assignment
            </Link>
          </div>
        </div>

        <AssignComposer inputRef={composerRef} onCreated={handleCreated} />

        {assignmentsError ? (
          <div role="alert" className="gv-card asg-alert">
            <span>Could not refresh assignments. Showing the last loaded data.</span>
            <button type="button" className="gv-btn outline sm" onClick={() => void refreshAssignments()}>
              Retry
            </button>
          </div>
        ) : null}

        {loading ? (
          <div className="asg-board" aria-busy="true" aria-label="Loading assignments">
            {LANES.map((lane) => (
              <div key={lane.id} className={`asg-lane ${lane.id}`}>
                <div className="gv-skel" style={{ width: "50%" }} />
                <div className="gv-skel" style={{ height: 96, borderRadius: 12 }} />
              </div>
            ))}
          </div>
        ) : view === "board" ? (
          <BoardLanes byLane={byLane} />
        ) : (
          <AssignmentListView byLane={byLane} />
        )}

        <section className="gv-card asg-feature" aria-labelledby="asg-feature-title">
          {/* eslint-disable-next-line @next/next/no-img-element -- static library illustration */}
          <img src="/illustrations/feature-assignment-workflow.svg" alt="" data-illustration="feature-assignment-workflow" />
          <div className="asg-feature-body">
            <div className="gv-eyebrow">Doing this again?</div>
            <h2 id="asg-feature-title">Turn an assignment into a workflow</h2>
            <p>
              Assignments run once. When the same job comes back every week, save it as a workflow with a schedule and the
              same approval gates.
            </p>
            <div className="asg-feature-actions">
              <Link href="/marketplace/assets?type=workflow" className="gv-btn outline">
                Browse workflow templates
              </Link>
            </div>
          </div>
        </section>
      </WsPage>
    </AppShell>
  )
}
