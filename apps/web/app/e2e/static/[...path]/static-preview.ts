import { existsSync } from "node:fs"
import { readFile } from "node:fs/promises"
import path from "node:path"

/**
 * Dev-only preview of the companion apps (desktop build, browser extension)
 * through the web dev server. The preview sandbox only bridges the web app's
 * port, so these static bundles are otherwise impossible to see in a browser.
 * 404s in production, same gate as /e2e/shots.
 */

const allowed =
  process.env.NODE_ENV !== "production" ||
  process.env.NEXT_PUBLIC_PLAYWRIGHT_E2E === "1" ||
  process.env.PLAYWRIGHT_E2E === "1"

function appsDir() {
  const candidates = [path.resolve(process.cwd(), ".."), path.resolve(process.cwd(), "apps")]
  return candidates.find((dir) => existsSync(path.join(dir, "extension", "manifest.json"))) ?? candidates[0]
}

const ROOTS: Record<string, string> = {
  desktop: path.join("desktop", "dist"),
  extension: "extension",
}

const TYPES: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".json": "application/json",
}

// Signed-in stand-in for the chrome.* APIs popup.js calls, so the popup and
// side panel render their real connected state instead of crashing.
const CHROME_STUB = `<script>
(function () {
  var signedIn = new URLSearchParams(location.search).get("state") !== "signed-out";
  function respond(msg, cb) {
    var res = { ok: true };
    if (msg && msg.type === "GET_SESSION") {
      res = signedIn
        ? { ok: true, signedIn: true, session: { connectedIntegrations: ["HubSpot", "Gmail", "Slack"] } }
        : { ok: true, signedIn: false };
    }
    if (msg && msg.type === "SIGN_OUT") signedIn = false;
    if (typeof cb === "function") setTimeout(function () { cb(res); }, 0);
    return Promise.resolve(res);
  }
  var tabs = [{ id: 1, windowId: 1, url: "https://mail.google.com/mail/u/0/" }];
  window.chrome = {
    runtime: { sendMessage: respond },
    tabs: {
      query: function (_q, cb) { if (cb) cb(tabs); return Promise.resolve(tabs); },
      sendMessage: function (_id, msg, cb) { return respond(msg, cb); },
    },
    sidePanel: { open: function () { return Promise.resolve(); } },
  };
  window.close = function () {};
})();
</script>`

export async function GET(_req: Request, { params }: { params: Promise<{ path: string[] }> }) {
  if (!allowed) return new Response("Not found", { status: 404 })

  const [app, ...rest] = (await params).path
  const relRoot = ROOTS[app]
  if (!relRoot) return new Response("Not found", { status: 404 })

  const root = path.join(appsDir(), relRoot)
  const file = path.resolve(root, rest.length ? rest.join("/") : "index.html")
  if (!file.startsWith(root + path.sep)) return new Response("Not found", { status: 404 })

  let body: Buffer
  try {
    body = await readFile(file)
  } catch {
    return new Response("Not found", { status: 404 })
  }

  const ext = path.extname(file)
  const headers = { "Content-Type": TYPES[ext] ?? "application/octet-stream", "Cache-Control": "no-store" }

  if (ext !== ".html") return new Response(new Uint8Array(body), { headers })

  let html = body.toString("utf8")
  if (app === "desktop") {
    html = html.replaceAll('"/assets/', '"/e2e/static/desktop/assets/')
  } else {
    html = html.replace("<head>", `<head>${CHROME_STUB}`)
  }
  return new Response(html, { headers })
}
