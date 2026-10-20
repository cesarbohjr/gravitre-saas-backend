// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { ManagedOAuthDialog } from "@/lib/managed-oauth-dialog"

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })

let root: Root
let container: HTMLDivElement
afterEach(async () => { if (root) await act(async () => root.unmount()); container?.remove() })
const session = {connectorId:"c1",sessionToken:"scoped",attemptId:"a1",integrationId:"okta",reconnect:false,connectionConfig:{subdomain:"acme"}}
async function renderDialog(props: React.ComponentProps<typeof ManagedOAuthDialog>) {
  container = document.createElement("div"); document.body.append(container); root = createRoot(container)
  await act(async () => root.render(<ManagedOAuthDialog {...props} />))
}
async function click(label: string) {
  const button = Array.from(document.querySelectorAll("button")).find((b) => b.textContent === label)!
  expect(button).toBeTruthy()
  await act(async () => button.click())
}

it("collects account settings in Gravitre and requires a fresh click to open provider sign-in", async () => {
  const prepare = vi.fn().mockResolvedValue(session)
  const authorize = vi.fn().mockResolvedValue(undefined)
  const finish = vi.fn()
  await renderDialog({name:"Okta",fields:[{key:"subdomain",label:"Okta domain",required:true}],prepare,authorize,finish})
  const input = document.querySelector<HTMLInputElement>("#oauth-subdomain")!
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value")!.set!.call(input,"acme")
    input.dispatchEvent(new Event("input",{bubbles:true}))
  })
  await click("Continue")
  expect(prepare).toHaveBeenCalledWith({subdomain:"acme"})
  expect(authorize).not.toHaveBeenCalled()
  await click("Sign in with provider")
  expect(authorize).toHaveBeenCalledWith(session)
  expect(finish).toHaveBeenCalledWith(true)
})

it("keeps SDK errors out of customer copy and explains blocked popups", async () => {
  await renderDialog({name:"Okta",fields:[],initialSession:session,prepare:vi.fn(),finish:vi.fn(),
    authorize:vi.fn().mockRejectedValue({type:"blocked_by_browser",message:"Nango private details"})})
  await click("Sign in with provider")
  expect(document.querySelector('[role="alert"]')?.textContent).toContain("Allow popups for Gravitre")
  expect(document.body.textContent).not.toContain("Nango")
})

it("closing provider sign-in cancels without success", async () => {
  const finish = vi.fn()
  await renderDialog({name:"Okta",fields:[],initialSession:session,prepare:vi.fn(),finish,
    authorize:vi.fn().mockRejectedValue({type:"window_closed"})})
  await click("Sign in with provider")
  expect(finish).toHaveBeenCalledWith(false)
})
