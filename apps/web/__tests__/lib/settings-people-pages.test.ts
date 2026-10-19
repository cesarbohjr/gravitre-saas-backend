// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest"

vi.mock("@/lib/fetcher", () => ({ apiFetch: vi.fn(), fetcher: vi.fn() }))

import {
  applyCompactTables,
  describeUserAgent,
  formFromUser,
  initialForm,
  isFormDirty,
  timeZoneLabel,
  updateFromForm,
} from "@/lib/settings-api/profile"
import { countLabel, createdLabel, filterOrgs, planLabel, sortOrgs, type OrgListItem } from "@/lib/settings-api/orgs"
import { buildTeamRows, filterTeamRows, teamCounts, type TeamApiMember } from "@/lib/settings-api/team"
import { buildRoleCards, peopleLabel, type RolePermissionsResponse } from "@/lib/settings-api/roles"

describe("profile helpers", () => {
  it("formats sessions as browser on OS without inventing a place", () => {
    expect(
      describeUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36 Edg/129.0",
      ),
    ).toBe("Edge on Windows")
    expect(
      describeUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"),
    ).toBe("Safari on macOS")
    expect(describeUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) CriOS/129.0 Mobile Safari/604.1")).toBe(
      "Chrome on iOS",
    )
    expect(describeUserAgent("")).toBe("Unknown device")
    expect(describeUserAgent("curl/8.0")).toBe("Unknown device")
  })

  it("seeds the form from the server and only fills gaps from browser-only values", () => {
    const saved = formFromUser({ id: "u", full_name: "Ada Lovelace King", phone: "+1 555", timezone: null })
    expect(saved.firstName).toBe("Ada")
    expect(saved.lastName).toBe("Lovelace King")
    const form = initialForm(saved, { phone: "+44 old", timezone: "Europe/London", bio: "" })
    expect(form.phone).toBe("+1 555")
    expect(form.timezone).toBe("Europe/London")
    expect(isFormDirty(form, saved)).toBe(true)
    expect(isFormDirty(saved, saved)).toBe(false)
    expect(updateFromForm({ ...form, location: "  Austin  " })).toMatchObject({
      full_name: "Ada Lovelace King",
      location: "Austin",
      timezone: "Europe/London",
    })
  })

  it("labels time zones and toggles compact tables on the html element", () => {
    expect(timeZoneLabel("America/Chicago")).toBe("Central Time")
    expect(timeZoneLabel("Australia/Sydney")).toBe("Australia/Sydney")
    expect(timeZoneLabel("")).toBeNull()
    applyCompactTables(true)
    expect(document.documentElement.dataset.compactTables).toBe("true")
    applyCompactTables(false)
    expect(document.documentElement.dataset.compactTables).toBeUndefined()
  })
})

describe("organization helpers", () => {
  const orgs: OrgListItem[] = [
    { id: "b", name: "Beta", slug: "beta", plan_name: "Command", plan_status: "trialing", agent_count: 3 },
    { id: "a", name: "Acme", slug: "acme-co", plan_name: null, agent_count: null },
  ]
  it("searches by name or slug and keeps the current org first", () => {
    expect(filterOrgs(orgs, "co").map((o) => o.id)).toEqual(["a"])
    expect(sortOrgs(orgs, "b").map((o) => o.id)).toEqual(["b", "a"])
    expect(sortOrgs(orgs, null).map((o) => o.id)).toEqual(["a", "b"])
  })
  it("never turns a missing count or plan into a number or a fake plan", () => {
    expect(countLabel(orgs[1].agent_count)).toBe("n/a")
    expect(countLabel(0)).toBe("0")
    expect(planLabel(orgs[0])).toBe("Command (trial)")
    expect(planLabel(orgs[1])).toBeNull()
    expect(createdLabel(undefined)).toBeNull()
  })
})

describe("team helpers", () => {
  const members: TeamApiMember[] = [
    { id: "p1", email: "owner@x.com", full_name: "Olive Owner", role: "owner", userId: "u1", orgId: "o1" },
    { id: "p2", email: "new@x.com", full_name: "", role: "viewer", userId: "u2", orgId: "o1" },
    { id: "p3", email: "mem@x.com", full_name: "Max", role: "member", userId: "u3", orgId: "o1" },
  ]
  it("marks invited members pending and keeps invites without a member row", () => {
    const rows = buildTeamRows(members, [
      { user_id: "u2", email: "new@x.com", role: "viewer", invited_at: "2026-10-01" },
      { user_id: "u9", email: "ghost@x.com", role: "member", invited_at: null },
    ])
    expect(rows.map((r) => [r.userId, r.status])).toEqual([
      ["u1", "active"],
      ["u2", "pending"],
      ["u3", "active"],
      ["u9", "pending"],
    ])
    expect(rows[1].name).toBe("new")
    expect(teamCounts(rows)).toEqual({ all: 4, active: 2, pending: 2, fullSeats: 2 })
    expect(filterTeamRows(rows, "pending", "ghost").map((r) => r.userId)).toEqual(["u9"])
    expect(filterTeamRows(rows, "active", "").length).toBe(2)
  })
  it("treats everyone as active when invites are unknown", () => {
    expect(teamCounts(buildTeamRows(members, undefined)).pending).toBe(0)
  })
})

describe("role helpers", () => {
  const matrix: RolePermissionsResponse = {
    roles: ["admin", "member", "viewer"],
    role_descriptions: { admin: "Full control" },
    capabilities: [
      { key: "a", capability: "View", area: "Insights", access: { admin: true, member: true, viewer: true } },
      { key: "b", capability: "Build", area: "Build", access: { admin: true, member: true, viewer: false } },
      { key: "c", capability: "Billing", area: "Govern", access: { admin: true, member: false, viewer: false } },
    ],
    member_counts: { owner: 1, admin: 0, member: 2, viewer: 0 },
  }
  it("builds coverage and people per role, counting owners with admins", () => {
    const [admin, member, viewer] = buildRoleCards(matrix)
    expect(admin).toMatchObject({ allowed: 3, total: 3, people: 1, peopleLabel: "1 person, the owner", cannot: [] })
    expect(member).toMatchObject({ allowed: 2, people: 2, peopleLabel: "2 people", cannot: ["Billing"] })
    expect(viewer).toMatchObject({ allowed: 1, peopleLabel: "No one yet", bar: [true, false, false], description: null })
  })
  it("says so when people cannot be counted", () => {
    expect(buildRoleCards({ ...matrix, member_counts: null })[0].peopleLabel).toBe("People count not available")
    expect(peopleLabel(3, 1)).toBe("3 people, including 1 owner")
  })
})
