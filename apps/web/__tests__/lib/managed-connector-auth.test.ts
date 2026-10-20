import { beforeEach, afterEach, describe, expect, it, vi } from "vitest"
import { waitForManagedConnection, openManagedConnector } from "@/lib/managed-connector-auth"
import { connectorsApi } from "@/lib/api"
import { CONNECTOR_CATALOG, connectorVendorKey, isManagedConnectorVendor, isOAuthVendorKey } from "@/lib/connectors"

const ui = vi.hoisted(() => ({ auth: vi.fn(), reconnect: vi.fn(), show: vi.fn(), options: vi.fn() }))
vi.mock("@/lib/api", () => ({ connectorsApi: { managedCatalog: vi.fn(), startManagedAuth: vi.fn(), managedAuthStatus: vi.fn() } }))
vi.mock("@nangohq/frontend", () => ({ default: class {
  constructor(options: unknown) { ui.options(options) }
  auth = ui.auth
  reconnect = ui.reconnect
} }))
vi.mock("@/lib/managed-oauth-dialog", () => ({ showManagedOAuthDialog: ui.show }))

beforeEach(() => { vi.clearAllMocks(); ui.auth.mockResolvedValue({}); ui.reconnect.mockResolvedValue({}) })
afterEach(() => { vi.useRealTimers() })

it("maps every managed display name without changing native auth", () => {
  const managed = CONNECTOR_CATALOG.filter((c) => isManagedConnectorVendor(c.vendorKey))
  expect(managed).toHaveLength(77)
  for (const c of managed) { expect(connectorVendorKey(c.type)).toBe(c.vendorKey); expect(isOAuthVendorKey(c.vendorKey)).toBe(true) }
  expect(isManagedConnectorVendor("HubSpot")).toBe(false)
})

it("does not treat an old active connection as successful reconnect", async () => {
  vi.useFakeTimers()
  vi.mocked(connectorsApi.managedAuthStatus).mockResolvedValueOnce({connected:true,status:"active",confirmedAttemptId:"old"})
    .mockResolvedValueOnce({connected:true,status:"active",confirmedAttemptId:"current"})
  const promise = waitForManagedConnection("c1","current")
  await vi.advanceTimersByTimeAsync(1000)
  await promise
  expect(connectorsApi.managedAuthStatus).toHaveBeenCalledTimes(2)
})

it("times out without claiming activation", async () => {
  vi.useFakeTimers()
  vi.mocked(connectorsApi.managedAuthStatus).mockResolvedValue({connected:false,status:"pending_auth"})
  const assertion = expect(waitForManagedConnection("c1","attempt")).rejects.toThrow("activation is still pending")
  await vi.advanceTimersByTimeAsync(30_000)
  await assertion
})

it("blocks before creating a session when server setup is missing", async () => {
  vi.mocked(connectorsApi.managedCatalog).mockResolvedValue({configured:false,connectors:[]})
  await expect(openManagedConnector("freshservice",{name:"desk"})).rejects.toThrow("administrator setup")
  expect(connectorsApi.startManagedAuth).not.toHaveBeenCalled()
})

describe("Gravitre headless OAuth", () => {
  beforeEach(() => {
    vi.mocked(connectorsApi.managedCatalog).mockResolvedValue({configured:true,connectors:[{vendor:"front",authMode:"OAUTH2",available:true,actions:[],support:"authorization_only"}]})
    vi.mocked(connectorsApi.startManagedAuth).mockResolvedValue({connectorId:"c1",sessionToken:"session",attemptId:"attempt",integrationId:"front",reconnect:false,connectionConfig:{}})
  })
  it("cancels without activating", async () => {
    ui.show.mockResolvedValue(false)
    expect(await openManagedConnector("front",{name:"inbox"})).toBe(false)
    expect(ui.auth).not.toHaveBeenCalled()
    expect(connectorsApi.managedAuthStatus).not.toHaveBeenCalled()
  })
  it("uses the scoped session and waits for the exact webhook attempt", async () => {
    vi.mocked(connectorsApi.managedAuthStatus).mockResolvedValue({connected:true,status:"active",confirmedAttemptId:"attempt"})
    ui.show.mockImplementation(async ({initialSession,authorize}) => { await authorize(initialSession); return true })
    expect(await openManagedConnector("front",{name:"inbox"})).toBe(true)
    expect(ui.options).toHaveBeenCalledWith({connectSessionToken:"session"})
    expect(ui.auth).toHaveBeenCalledWith("front",{params:{},detectClosedAuthWindow:true})
    expect(connectorsApi.managedAuthStatus).toHaveBeenCalledWith("c1")
  })
  it("uses reconnect instead of creating another grant", async () => {
    vi.mocked(connectorsApi.startManagedAuth).mockResolvedValue({connectorId:"c1",sessionToken:"session",attemptId:"attempt",integrationId:"front",reconnect:true,connectionConfig:{}})
    vi.mocked(connectorsApi.managedAuthStatus).mockResolvedValue({connected:true,status:"active",confirmedAttemptId:"attempt"})
    ui.show.mockImplementation(async ({initialSession,authorize}) => { await authorize(initialSession); return true })
    await openManagedConnector("front",{name:"inbox",connectorId:"c1"})
    expect(ui.reconnect).toHaveBeenCalledOnce()
    expect(ui.auth).not.toHaveBeenCalled()
  })
  it("never opens a credentials form for non-interactive auth", async () => {
    vi.mocked(connectorsApi.managedCatalog).mockResolvedValue({configured:true,connectors:[{vendor:"freshservice",authMode:"BASIC",available:true,actions:[],support:"actions_supported"}]})
    await expect(openManagedConnector("freshservice",{name:"desk"})).rejects.toThrow("Sign-in authorization is not available")
    expect(ui.show).not.toHaveBeenCalled()
    expect(connectorsApi.startManagedAuth).not.toHaveBeenCalled()
  })
})

it("blocks a provider with missing app setup even when the platform key is configured", async () => {
  vi.mocked(connectorsApi.managedCatalog).mockResolvedValue({configured:true,connectors:[
    {vendor:"freshservice",available:true,actions:[],support:"authorization_only"},
    {vendor:"okta",available:false,setupReason:"provider_credentials_required",actions:[],support:"actions_supported"},
  ]})
  await expect(openManagedConnector("okta",{name:"identity"})).rejects.toThrow("administrator setup")
  expect(connectorsApi.startManagedAuth).not.toHaveBeenCalled()
})
