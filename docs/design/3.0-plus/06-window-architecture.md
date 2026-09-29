# 06 — Window architecture

## Spec modes vs shipped

| Spec mode | Shipped today | Mapping |
|-----------|---------------|---------|
| Compact | `float` / canonical `compact` | Floating workspace ~500–600px |
| Floating | Same as compact in practice | Drag + resize |
| Docked | **Missing** | First-class gap |
| Expanded | `expanded` | Desktop multi-panel shell |
| Fullscreen | `fullscreen` + `/ai` | Same runtime |
| Minimized | `helper` / canonical `minimized` | Launcher orb |
| Restored | Implicit via last mode | Needs explicit restore memory |

Sources: `lib/gravitre-ai-presentation.ts`, `ai-workspace-provider.tsx`, `ai-floating-workspace.tsx`, `ai-workspace-shell.tsx`.

## Non-negotiables

Changing window mode **must not** reset or duplicate:

- Conversation id / transcript  
- Task state / pending approvals  
- Artifacts / work canvas selection  
- Voice session  
- Inspector selection  

Functional runtime remains authoritative for those domains.

## Composition rules (from master spec)

Do not scale the same layout. Each mode prioritizes differently:

| Mode | Prioritize | Hide / demote |
|------|------------|---------------|
| Compact | Conversation, task, one primary action, voice | Advanced inspector |
| Expanded | Conversation + artifact + task + approval | Full ops tables |
| Fullscreen | Artifact workspace + inspector + evidence | Launcher chrome |
| Docked (to design) | Persistent side dock without covering expert canvas | Floating drag chrome |

## Floating UI

Use only for anchored menus/tooltips/command surfaces (**Radix today**). **Not** the Window Manager.

## Implementation plan (frontend-owned, gated)

1. Document docked IA + wireframe in harness  
2. Unify restore persistence (mode + layout rect) without touching chat SoT  
3. Prove mode transitions with live conversation id continuity (journey test)  
4. Production only after Cesar structural approval
