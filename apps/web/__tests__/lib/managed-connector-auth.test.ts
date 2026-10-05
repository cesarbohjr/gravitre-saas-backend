import { beforeEach, afterEach, describe, expect, it, vi } from "vitest"
import { waitForManagedConnection, openManagedConnector } from "@/lib/managed-connector-auth"
import { connectorsApi } from "@/lib/api"
import { CONNECTOR_CATALOG, connectorVendorKey, isManagedConnectorVendor, isOAuthVendorKey } from "@/lib/connectors"

const ui = vi.hoisted(() => ({ close: vi.fn(), onEvent: undefined as ((event: { type: string }) => void) | undefined }))
vi.mock("@/lib/api", () => ({ connectorsApi: { managedCatalog: vi.fn(), startManagedAuth: vi.fn(), managedAuthStatus: vi.fn() } }))
vi.mock("@nangohq/frontend", () => ({ default: class { openConnectUI(props: { onEvent: (event: { type: string }) => void }) { ui.onEvent = props.onEvent; return { close: ui.close } } } }))

beforeEach(() => { vi.clearAllMocks(); ui.onEvent = undefined })
afterEach(() => { vi.useRealTimers() })

it("maps every managed display name without changing native auth", () => {
  const managed = CONNECTOR_CATALOG.filter((c) => isManagedConnectorVendor(c.vendorKey))
  expect(managed).toHaveLength(47)
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

describe("Connect UI", () => {
  beforeEach(() => {
    vi.mocked(connectorsApi.managedCatalog).mockResolvedValue({configured:true,connectors:[]})
    vi.mocked(connectorsApi.startManagedAuth).mockResolvedValue({connectorId:"c1",sessionToken:"session",attemptId:"attempt"})
  })
  async function start() {
    const promise = openManagedConnector("freshservice",{name:"desk"})
    await vi.waitFor(() => expect(ui.onEvent).toBeTypeOf("function"))
    return { promise }
  }
  it("cancel closes UI without activating", async () => {
    const {promise} = await start(); ui.onEvent?.({type:"close"})
    expect(await promise).toBe(false)
    expect(ui.close).toHaveBeenCalledOnce()
    expect(connectorsApi.managedAuthStatus).not.toHaveBeenCalled()
  })
  it("confirms activation through backend before reporting success", async () => {
    vi.mocked(connectorsApi.managedAuthStatus).mockResolvedValue({connected:true,status:"active",confirmedAttemptId:"attempt"})
    const {promise} = await start(); ui.onEvent?.({type:"connect"})
    expect(await promise).toBe(true)
    expect(ui.close).toHaveBeenCalledOnce()
  })
  it("cleans up on provider error", async () => {
    const {promise} = await start()
    const assertion = expect(promise).rejects.toThrow("Account authorization failed")
    ui.onEvent?.({type:"error"}); await assertion
    expect(ui.close).toHaveBeenCalledOnce()
  })
})
