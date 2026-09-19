# Creative Experience System — Connector Fabric (Phase 7)

**Status:** IMPLEMENTING  
**Upstream:** Pilots 1–3 shipped. Do not reopen `/about`, Technology pilots, or Pilot 3 KF.  
**Bible:** [`gravitre-creative-experience-system.md`](gravitre-creative-experience-system.md) §P Connector Fabric + §V Connectors P1  
**Engine:** SVG + DOM. No Three/R3F.

## Product-truth

**Safe:** Capability ports (READ / WRITE / SEARCH / …); auth/scopes before act; governed WRITE pause; evidence after act.  
**Must not:** Logo wall of “50+ always live”; imply every connector is connected; silent auto-writes.

**Label:** “Illustrative connector fabric — capability ports and governed writes. Not a live inventory of your stack.”

## Spatial model

```
[Capability ports]  →  [Auth / scopes]  →  [READ act]  →  [WRITE WAITING]  →  [Approve]  →  [Evidence]
     CRM · Comms · Finance   (words + Nucleo — not brand logos)
```

## Mount

`/docs/integrations` — replace hub motif with Connector Fabric field (docs remain the connectors marketing surface; `/features/integrations` permanently redirects to `/features`).

## Checklist

1. ✅ Design + honesty (this doc)  
2. ✅ SVG scene + reduced + mobile  
3. ✅ Mount on docs integrations  
4. ✅ Vitest + Playwright smoke  
