"use client"

/**
 * Lite seats (design p15): stat tiles, departments as cards or a table with a
 * 10-per-page pager, and a side panel to manage the selected department.
 * Rendered by app/(app)/settings/page.tsx for ?section=lite-seats with the
 * shell header hidden, so it draws its own SetHeader.
 */
import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { Armchair, Building2, LayoutGrid, Loader2, Plus, Search, Table2, UserCheck } from "lucide-react"
import { toast } from "@/components/agents/overlays/toast"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { settingsApi } from "@/lib/api"
import { useOrgAdmin } from "@/lib/use-org-admin"
import {
  LITE_SEATS_KEY,
  filterDepartments,
  liteTotals,
  pageSlice,
  seatBarWidth,
  type LiteDepartment,
  type LiteSeatsPayload,
} from "@/lib/settings-api/lite"
import { SetError, SetHeader, SetNote, SetPager, SetSkeleton, SetStat, SetTabs } from "./settings-kit"
import { LiteSeatsPanel } from "./lite-seats-panel"
import "./lite-seats.css"

const HEADER = {
  crumb: "Settings / People and plan",
  title: "Lite seats",
  description:
    "Give approvers and occasional users a Lite seat by department. Lite users can run assigned workflows and approve work, but building still needs a full seat.",
}

type View = "cards" | "table"

export function LiteSeatsSettings({ isAdmin }: { isAdmin: boolean }) {
  const { pending: adminPending, showAdmin } = useOrgAdmin()
  const { data, error, isLoading, mutate } = useSWR<LiteSeatsPayload>(isAdmin ? LITE_SEATS_KEY : null, apiFetcher, {
    revalidateOnFocus: false,
  })
  const [adding, setAdding] = useState(false)

  if (!isAdmin) {
    return (
      <>
        <SetHeader {...HEADER} />
        {adminPending || showAdmin ? (
          <p role="status" className="gs-sub">
            Checking admin access…
          </p>
        ) : (
          <SetNote>Admin or owner permission is required to manage Lite seats.</SetNote>
        )}
      </>
    )
  }

  return (
    <>
      <SetHeader
        {...HEADER}
        actions={
          <button
            type="button"
            className="gs-btn dark"
            aria-expanded={adding}
            onClick={() => setAdding((open) => !open)}
          >
            <Plus size={16} aria-hidden />
            Add department
          </button>
        }
      />
      {adding ? <AddDepartmentForm onDone={() => setAdding(false)} onAdded={() => mutate()} /> : null}
      {isLoading && !data ? (
        <section className="gs-card">
          <SetSkeleton rows={4} label="Loading Lite seats" />
        </section>
      ) : error && !data ? (
        <section className="gs-card">
          <SetError message="Could not load Lite seats." onRetry={() => void mutate()} />
        </section>
      ) : (
        <LiteSeatsBody payload={data} onChanged={() => mutate()} onAdd={() => setAdding(true)} />
      )}
    </>
  )
}

function AddDepartmentForm({ onDone, onAdded }: { onDone: () => void; onAdded: () => Promise<unknown> }) {
  const [name, setName] = useState("")
  const [seats, setSeats] = useState("1")
  const [saving, setSaving] = useState(false)
  const submit = async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    setSaving(true)
    try {
      await settingsApi.createDepartment({
        name: trimmed,
        lite_seat_allocation: Math.max(0, Number.parseInt(seats || "0", 10) || 0),
      })
      toast.success("Department added")
      await onAdded()
      onDone()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add department")
    } finally {
      setSaving(false)
    }
  }
  return (
    <section className="gs-card gs-rise" aria-label="Add department">
      <form
        className="ls-add"
        onSubmit={(event) => {
          event.preventDefault()
          void submit()
        }}
      >
        <label className="gs-field">
          Department name
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Sales" autoFocus disabled={saving} />
        </label>
        <label className="gs-field seats">
          Seats
          <input
            type="number"
            inputMode="numeric"
            min={0}
            value={seats}
            onChange={(e) => setSeats(e.target.value)}
            disabled={saving}
          />
        </label>
        <div className="ls-row">
          <button type="submit" className="gs-btn dark" disabled={saving || !name.trim()}>
            {saving ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Plus size={16} aria-hidden />}
            Add department
          </button>
          <button type="button" className="gs-btn line" onClick={onDone} disabled={saving}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  )
}

function LiteSeatsBody({
  payload,
  onChanged,
  onAdd,
}: {
  payload: LiteSeatsPayload | undefined
  onChanged: () => Promise<unknown>
  onAdd: () => void
}) {
  const departments = useMemo(() => payload?.departments ?? [], [payload])
  const totals = liteTotals(payload)
  const [query, setQuery] = useState("")
  const [view, setView] = useState<View>("cards")
  const [page, setPage] = useState(1)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  /** Unsaved +/- clicks per department, shown immediately and rolled back on error. */
  const [draftAlloc, setDraftAlloc] = useState<Record<string, number>>({})

  const filtered = filterDepartments(departments, query)
  const slice = pageSlice(filtered, page)
  const selected = departments.find((d) => d.id === selectedId) ?? departments[0] ?? null

  useEffect(() => {
    if (selectedId && !departments.some((d) => d.id === selectedId)) setSelectedId(null)
  }, [departments, selectedId])

  const allocOf = (d: LiteDepartment) => draftAlloc[d.id] ?? Number(d.lite_seat_allocation || 0)
  const allocatedTotal = departments.reduce((sum, d) => sum + allocOf(d), 0)

  return (
    <>
      <div className="gs-stats">
        <SetStat icon={Armchair} tone="green" label="Included" value={totals.includedLabel} hint={totals.planLabel ?? "Your plan"} />
        <SetStat
          icon={Building2}
          label="Allocated"
          value={departments.length ? allocatedTotal : totals.allocated}
          hint={`Across ${totals.departments} department${totals.departments === 1 ? "" : "s"}`}
        />
        <SetStat icon={UserCheck} label="In use" value={totals.used} hint="Assigned Lite users" />
      </div>

      <section className="gs-card clip" aria-label="Departments">
        <div className="gs-toolbar">
          <label className="gs-input">
            <Search size={16} aria-hidden />
            <input
              aria-label="Search departments"
              placeholder="Search departments"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setPage(1)
              }}
            />
          </label>
          <SetTabs<View>
            label="View"
            value={view}
            onChange={setView}
            options={[
              { id: "cards", label: "Cards", icon: LayoutGrid },
              { id: "table", label: "Table", icon: Table2 },
            ]}
          />
        </div>
        <div className="gs-split">
          <div className="gs-split-main">
            {departments.length === 0 ? (
              <div className="gs-empty">
                <b>No departments yet</b>
                <p>Add a department, give it Lite seats, then assign the people and workflows it needs.</p>
                <button type="button" className="gs-btn dark sm" onClick={onAdd}>
                  <Plus size={15} aria-hidden />
                  Add department
                </button>
              </div>
            ) : filtered.length === 0 ? (
              <div className="gs-empty" role="status">
                <b>No departments match “{query.trim()}”</b>
                <button type="button" className="gs-btn line sm" onClick={() => setQuery("")}>
                  Clear search
                </button>
              </div>
            ) : view === "cards" ? (
              <div className="gs-cards" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))" }}>
                {slice.rows.map((d) => {
                  const alloc = allocOf(d)
                  const used = Number(d.used_seats || 0)
                  return (
                    <button
                      key={d.id}
                      type="button"
                      className="gs-wcard"
                      aria-pressed={selected?.id === d.id}
                      onClick={() => setSelectedId(d.id)}
                    >
                      <div className="ls-card-top">
                        <span className="n">{d.name || "Untitled department"}</span>
                        <span className="gs-count">
                          {used} / {alloc}
                        </span>
                      </div>
                      <div className="gs-track" aria-hidden>
                        <span style={{ width: seatBarWidth(used, alloc) }} />
                      </div>
                      <div className="ls-card-foot">
                        <span>
                          {d.resource_count ?? 0} resource{(d.resource_count ?? 0) === 1 ? "" : "s"}
                        </span>
                        <span>{Math.max(alloc - used, 0)} free</span>
                      </div>
                    </button>
                  )
                })}
              </div>
            ) : (
              <div className="gs-tbl stack" style={{ ["--cols" as string]: "minmax(0,1fr) 110px 110px 110px" }}>
                <div className="gs-tr head" aria-hidden>
                  <div className="gs-th">Department</div>
                  <div className="gs-th">Used</div>
                  <div className="gs-th">Allocated</div>
                  <div className="gs-th">Resources</div>
                </div>
                {slice.rows.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    className="gs-row"
                    aria-pressed={selected?.id === d.id}
                    aria-label={`${d.name || "Untitled department"}: ${d.used_seats ?? 0} used of ${allocOf(d)} allocated, ${d.resource_count ?? 0} resources`}
                    onClick={() => setSelectedId(d.id)}
                  >
                    <span className="gs-td">
                      <span className="t">{d.name || "Untitled department"}</span>
                    </span>
                    <span className="gs-td gs-mono">
                      {d.used_seats ?? 0}
                    </span>
                    <span className="gs-td gs-mono">
                      {allocOf(d)}
                    </span>
                    <span className="gs-td gs-mono">
                      {d.resource_count ?? 0}
                    </span>
                  </button>
                ))}
              </div>
            )}
            {filtered.length > 0 ? (
              <SetPager
                page={slice.page}
                pageCount={slice.pageCount}
                from={slice.from}
                to={slice.to}
                total={slice.total}
                onPage={setPage}
              />
            ) : null}
          </div>
          <aside className="gs-split-side" aria-label="Department">
            {selected ? (
              <LiteSeatsPanel
                key={selected.id}
                department={selected}
                allocation={allocOf(selected)}
                onDraftAllocation={(value) =>
                  setDraftAlloc((prev) => {
                    const next = { ...prev }
                    if (value === null) delete next[selected.id]
                    else next[selected.id] = value
                    return next
                  })
                }
                onChanged={onChanged}
                onDeleted={() => setSelectedId(null)}
              />
            ) : (
              <div className="gs-empty">
                <b>No department selected</b>
                <p>Add a department to manage its Lite seats, users and resources here.</p>
              </div>
            )}
          </aside>
        </div>
      </section>
    </>
  )
}
