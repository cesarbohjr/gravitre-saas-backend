# Emerald Intelligence Figma source

Read directly through Figma MCP on 2026-10-03, file `OsDKeRy9HwfSKR3e9YyOFM`.

The file has no local variable collections, variables, paint styles or text styles. These values are exact layer properties and written specifications, not a variable export.

Page `6:2`, implementation token frame `17:2`, motion frame `24:2`:

| Role | Value | Source |
| --- | --- | --- |
| Emerald | #00A878 | 17:18 |
| Deep emerald | #007F5F | 17:21 |
| Mint | #CFF7E8 | 6:51 |
| Pale | #EAF8F2 | 17:58 |
| Carbon | #101816 | 17:15 |
| Bone | #F5F3EC | 17:24 |
| Electric | #315CFF | 17:27 |
| Warmth | #FF654D | 17:30 |
| Muted text | #65716B | 17:5 |

Existing code hover #008F67 and muted #63D6B3 were not found among solid fills on page 03. They remain implementation-derived steps, not confirmed design swatches. Page 01's earlier Porcelain/Signal/Ion palette differs; it does not overwrite the explicit Emerald implementation frames.

Display: Space Grotesk Medium; body: Inter. Marketplace heading is 34px desktop (8:20), 30px phone (8:92), featured title 27px desktop (8:25), 21px phone (8:96). Compact type specimens in 17:2 are not universal page sizes.

Motion: connect 150–180ms; handoff 180–220ms; verify 160–200ms; inspect 180–220ms; orchestrate 240–320ms. Motion stops at a meaningful state; no ambient animation.

Responsive studies: desktop 1440, tablet 768–1024, phone 390. These are study dimensions, not automatically CSS breakpoints.

## First implementation pass

Marketplace 8:2 and 8:87 were read with high-fidelity design context and screenshots. Their emerald featured / carbon context composition is adapted to actual catalog data: titles, descriptions, included components and connector counts. No specimen plays, counts, claims, live labels, or execution actions were fabricated. The call to action opens the existing pack detail route.

Space Grotesk is self-hosted from the Google Fonts official `ofl/spacegrotesk` source, with its OFL license included. Marketplace uses this display face; body and unrelated surfaces retain their existing font roles.

Rendered component behavior is covered by marketplace-featured-outcome.test.tsx. Local full suite: 1142 tests / 187 files passed; TypeScript and changed-file ESLint passed. Browser service rejected the local fixture URL with ERR_BLOCKED_BY_CLIENT; desktop/mobile pixel verification and owner-live acceptance remain NOT_RUN. This pass does not complete Agents, Intelligence, Operate, Builder, Analytics, or the full design.
