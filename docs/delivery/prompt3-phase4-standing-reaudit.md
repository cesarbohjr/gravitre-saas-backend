# Prompt 3 Phase 4 — Fresh standing re-audit (bounded)

**Purpose:** Confirm Prompts 1–2 + F1–F10 + RLS + Phase 1–3 of this prompt have not drifted on the **current live tip**. Fresh evidence only.

**Live tip (`GET https://api.gravitre.app/health` @ 2026-08-06T19:55:13Z):** `26c32007151a5e17370d9c9e2105e44ed0e97562`  
**Artifact:** `docs/delivery/prompt3-phase4-standing-reaudit-live.json`

## Deploy / tip context

| Run | Title | headSha | Status | Note |
|-----|-------|---------|--------|------|
| [31126500276](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31126500276) | Railway backend production | `3e7c90fe…` | **pending** (empty jobs; updated 18:55Z) | Stuck — not advancing |
| [31126385881](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31126385881) | feat(voice): Tier 1 ElevenLabs TTS + Deepgram STT… | `3e7c90fe…` | **queued** (Detect backend changes; ~1h+) | Stuck — tip still on older SHA |

Live `/health` **does not** match queued voice tip `3e7c90fe` — remaining on `26c32007…`.

## Checklist (run against tip `git_sha`)

| # | Item | How | Result |
|---|------|-----|--------|
| 1 | Prompt 1 TTFT band | `TTFT_LABEL=prompt3-p4 python scripts/verify-unified-turn-task-ttft-live.py` | **PARTIAL** — tip `26c32007…`; `wall_p50=707ms`, `wall_max=2008ms`, `model_p50=560ms`; functional **4/5** (`ok=false`); stamped `unified-turn-task-ttft-prompt3-p4.json` @ 2026-08-06T20:01:30Z |
| 2 | Prompt 2 enrichment | tip `catalog-enrichment-nl-variance-live.json` or re-probe | **TIP DRIFT** — artifact still `api_git_sha=45ae7d052d1f88236d2aacb675b84cece751d825` (`overall_pass=true`); live tip now `26c32007…` (not tip-matched) |
| 3 | G.5.9 Apollo settle | `python scripts/live-f6-collection-population-verify.py` | **PASS** — Apollo+HubSpot `follow_up_membership_confirmed`; Marketo **NOT_RUN** (`no_active_marketo_connector`). Apollo list `6a74e705ae28c7001c69630d`; HubSpot list `46`. Tip `26c32007…` @ 2026-08-06T19:57:58Z |
| 4 | Click-audit standing | nightly workflow + `prompt3-phase2-click-audit-live.json` | **PASS (prior)** — verdict PASS, 11/11 surfaces @ `2026-08-06T17:10:00Z` (not re-probed this pass; tip not stamped in artifact) |
| 5 | Voice status | `python scripts/probe-tier1-voice-live.py` | **FAIL** — tip `26c32007…`; status HTTP **404** (voice routes absent); TTS skipped (`ELEVENLABS_API_KEY not configured on tip`); expected until `3e7c90fe` deploy unsticks |
| 6 | F1–F10 / routing | spot `docs/delivery/gravitre-routing-decision-map.md` A–G.5 + G.1 probe if time | **NOT_RUN** this bounded pass (F6 G.5.9 covered in #3) |
| 7 | RLS / perf | note from prior audit; no schema change in this prompt | **ASSUMED HOLD** — no schema change this pass; no fresh RLS probe |

## Named gaps found this pass

1. **Deploy stuck:** GH runs `31126500276` (pending) and `31126385881` (queued) on `3e7c90fe` not landing; live tip remains `26c32007…`.
2. **Voice not on tip:** Tier-1 voice probe **FAIL** (404 + no ElevenLabs key on tip) — blocked by gap #1.
3. **Catalog enrichment tip drift:** NL-variance / full-build evidence pinned to `45ae7d05…`; live tip advanced to `26c32007…` without re-probe.
4. **TTFT gate not green:** `ok=false` / functional 4/5 (`apollo_list_write` functional_ok=false; notes cite classical fallthrough / probe capture race — not vendor rate limit). Wall band still sub-2.1s max.
5. **Marketo F6:** intentionally **NOT_RUN** (no active connector) — acceptable per standing decision `a`.
6. **Click-audit / F1–F10 / RLS:** not freshly tip-stamped this bounded pass.

## Vendor pass + list ids (F6)

| Vendor | Pass | List id | Notes |
|--------|------|---------|-------|
| Apollo | true | `6a74e705ae28c7001c69630d` | membership after=1; `F6-FollowUp-46fa83d4` |
| HubSpot | true | `46` | membership after=1; `F6-HS-46fa83d4`; contact `270287894506` |
| Marketo | NOT_RUN | — | `no_active_marketo_connector` |

**Overall F6 verdict:** `VERIFIED — Apollo+HubSpot follow_up_membership_confirmed; Marketo NOT_RUN (no connector)`
