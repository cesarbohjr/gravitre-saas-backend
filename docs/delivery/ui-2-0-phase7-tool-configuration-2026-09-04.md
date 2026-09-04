# GRAVITRE UI 2.0 — Phase 7 tool configuration

**Date:** 2026-09-04  
**Updated:** after Pro Nucleo install + MCP wiring + 21st/Aceternity config

---

## Status summary

| Tool | Status | Notes |
|------|--------|-------|
| **shadcn MCP** | Ready | `.cursor/mcp.json` → `npx shadcn@latest mcp --cwd apps/web` (monorepo: finds `components.json` + `@aceternity`) |
| **Nucleo Pro CLI** | Installed on disk | `~/.nucleo/skills/manifest.json` → `tier: pro+free`, families core/ui/sharp/micro/pixel + free sets |
| **Nucleo MCP** | Wired | `nucleo-icons` → `~/.nucleo/skills/mcp/dist/index.js` + `NUCLEO_SKILLS_ROOT` |
| **Nucleo MCP Pro visibility** | **PASS** (post-reload) | Live MCP: `product: nucleo-skills`, all 12 families licensed+installed; `core` search for `waveform` returns Pro icons |
| **21st.dev MCP** | **PASS** | Live: namespace ready; search returns voice components; `get_usage` → **Tier: paid** (unlimited search + code retrieval) |
| **Aceternity registry** | **PASS** | Root `package.json` + `apps/web/components.json` registries; MCP lists 278 `@aceternity` items |
| **API keys** | Local only | `backend/.env.operator.local` + `apps/web/.env.local` (gitignored) |

---

## Secrets (never commit)

| Variable | Where stored | Used for |
|----------|--------------|----------|
| `API_KEY_21ST` | gitignored env files | 21st MCP / CLI |
| `API_KEY_ACETERNITY_UI` | gitignored env files | Aceternity paid registry if required |
| `NUCLEO_LICENSE_KEY` | `backend/.env.operator.local` | Nucleo Pro CLI |

Password pasted in chat earlier was **not** persisted — rotate if still in use.

---

## Nucleo Windows note

`nucleo setup`’s bundled `npm install` fails when the path contains spaces (`C:\Program Files\...`). Fix already applied:

```text
cd ~/.nucleo/skills/mcp && npm install --omit=dev
```

MCP entry uses absolute path to `dist/index.js` (no space-in-path issue for node).

---

## Usage rules (UI program)

1. **Nucleo:** copy icons into the app; never import from `~/.nucleo/skills` at runtime.
2. **21st / Aceternity:** extract + restyle with DS 2.0 tokens — do not ship foreign brand chrome.
3. **shadcn:** discovery/examples; existing `components/ui` remains SOT.
4. **No invented customer surfaces** (prices, TRAINED badges, Enable toggles) from any registry.

---

## Operator checklist after this change

1. Reload Cursor MCP servers (or restart Cursor).
2. Confirm `nucleo_list_families` includes `core`, `ui`, `sharp`, `micro`, `pixel`.
3. Confirm 21st MCP authenticates (set `API_KEY_21ST` in environment Cursor can see).
4. Optional: `npx shadcn@latest add @aceternity/<name>` only when a pilot needs a specific effect.

---

## What is still not done

- Broad icon migration Lucide → Nucleo (Phase 9+ / pilot-scoped)
- Installing Aceternity/21st components into the tree (pilot-scoped only)
- Class B mutation-test of chat-surface-drift guard
