# UI 3.0 — Phase 12b (logo optical weight + benefits bars)

**Date:** 2026-09-07  
**Status:** Shipping on `main`

## Why

Live check after Phase 12 showed Gravitre marks still reading lighter than the Nodus geometric fill (hub tile whitespace + thin chat avatars). Benefits mini-dashboard bars were still neutral gray.

## Changes

1. **LogoSVG** — thicker bars (~85% viewBox fill), tighter gap.
2. **Hubs** — `p-1` + `size-[52px]` in benefits + native-tools hubs; how-it-works / contact upsized.
3. **Chat** — homepage skeleton `h-9` disc + `size-7` mark; in-app avatar `h-10` + `size-[28px]`.
4. **Nav logo** — marketing `Logo` `h-9` / `sm:h-10`.
5. **Benefits bars** — fill `var(--brand)`.
6. **Hero dashboard PNGs** — larger Gravitre lockup in sidebar chrome (coral→green already from 12).
7. **Drift check** — accepts `LogoSVG` as the chat mark.

## Scaffold honesty

**(a)** Explicitly requested larger marks + Nodus parity. No new prices/claims/Enable toggles.
