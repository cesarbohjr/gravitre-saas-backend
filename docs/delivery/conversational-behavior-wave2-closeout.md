# Conversational behavior wave 2 (rules 6–10) — closeout (2026-08-12)

## Added instructions (shared layer)

In `conversational_behavior.py`, alongside 1–5:

6. Corrections persist  
7. Push back when warranted  
8. Avoid scripted-assistant patterns  
9. Default to brief  
10. Meet the human moment first when warranted  

## Before (`041c91a7`, rules 1–5 only)

| Suite | Key failure |
| -- | -- |
| marketing_correction_brief | Late reply: “You haven’t picked a specific market…” after US correction — **corrections_persist=false**; meta title 62w |
| marketing_pushback_empathy | Already pass (Module D + 1–5) |
| sales_wave2 | Pushback present but scorer miss; mixed |

Artifact: `conversational-behavior-wave2-before-transcript.json`

## After (`57cccaf1`)

| Suite | Result |
| -- | -- |
| marketing_correction_brief | **corrections_persist=true** — “US — you corrected that earlier.”; meta title 53w; no scripted open — **pass** |
| marketing_pushback_empathy | Empathy + “I wouldn’t” on link farm + brief first check — **pass** |
| sales_wave2 | SMB correction held; empathy; pushback on mass discount blast; brief SDR line — **pass** |

Artifact: `conversational-behavior-wave2-after-transcript.json` · `verdict=PASS`

## Deploy

`GET https://api.gravitre.app/health` → `git_sha=57cccaf16cb518a8a2e36b92f4be0aa07aed70fc` `status=ok`
