# “Show the work” — Phase 0–7 placement (no implementation)

Claude’s separate **show the work** specification remains agreed product direction. **Do not implement** the live checklist or backend event integration in Phases 0–7. Visible browser/computer execution is a separate capability — never simulated.

## Account for future placement in

| Area | Placement note |
|------|----------------|
| AI workspace composition | Work canvas / side rail slot for authentic step evidence when runtime emits it |
| Window modes | Compact: minimal progress; Expanded/Fullscreen: richer work surface — same taskState |
| Task / execution presentation | Bind to functional Observations / execution events — no parallel fake timeline |
| Voice + text continuity | Same task vocabulary across modalities |
| Shared AI state vocabulary | Align labels with functional task phases (WAITING_*, COMPLETED, etc.) |
| Motion rules | State communication only; no decorative “busy” theater |
| Component registry | Reserve `ShowWork*` presentation components in design registry — stub names only until scheduled |

## Explicit defer

- Live checklist UI  
- Backend event subscription for show-the-work  
- Computer-use / watch-Gravitre-work surfaces  

Scheduled after core product completion per Cesar.
