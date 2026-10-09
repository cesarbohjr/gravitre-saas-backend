# Voice dialogue library

Curated spoken-dialogue material for the three voice tiers: light (social), medium (thinking together) and deep (business work with tools and approvals).

## Files

| File | Used at runtime? | What it's for |
| --- | --- | --- |
| `runtime_fewshots.json` | Yes, through `select_fewshots()` only | A hand-picked set of short exchanges per tier (about 48 light, 47 medium and 42 deep), used by voice and typed chat alike. Deep examples include narrative result answers: what I did, what I found, what it means, then the next step. `select_fewshots(tier, message, history, k)` returns at most `k` of them (at most 1 for deep) as a block of 700 characters or less, headed "Style examples (do not repeat verbatim; match tone, not content):". They are tone references. They are never spoken as-is and they are never a source of facts. |
| `eval_conversations.json` | No | The offline evaluation set: about 160 multi-turn reference conversations with `tier_path`, `traits`, optional per-turn `expect` notes and `tool` turns. A `tool` turn stands for what an authorized connector returned. Tests and graders use the set. Nothing loads it into a prompt. |
| `rubric.py` | No (offline) | Deterministic checks for any spoken reply: no markdown, URLs, ids or stacked questions; a length budget per tier; no unprompted business data in the light tier; no completed write without an approval earlier in the history; deep-tier numbers must come from the user or a tool; a follow-up-question rate; and repeated openers across a conversation. |
| `__init__.py` | Yes | `select_fewshots`. It reads the JSON once (`lru_cache`), scores the examples lexically, and is deterministic, network-free and well under 1 ms. It returns `""` for an unknown tier or on any error. |

## What this is not

- **Not training or fine-tuning data.** Nothing here is used to train or fine-tune a model. Don't describe the assistant as having been trained on it.
- **Not a response bank.** The runtime never samples a reference reply and speaks it.
- If a fine-tuning export is ever needed, it has to be a **separate, clearly labelled file** with its own review. Don't repurpose `eval_conversations.json` or `runtime_fewshots.json` for it.

## Authoring rules

- Write for the ear. Use short sentences and contractions. No markdown and no lists read aloud (three items at most, said as one sentence). Vary how replies open.
- Light tier: don't bring up business data unless the user asks. Sarcasm is fine about situations, never aimed at the user, and is dropped when the user is upset.
- Deep tier: state the effect of a write and ask before doing it. Report a write only after the user said yes and a tool turn confirms it. Keep what was checked separate from what is inferred. Never invent numbers: use a `tool` turn or a placeholder such as `<monthly quota>`.
- Use fictional companies and people only (Northwind Supply, Brightline Dental and so on). Email addresses in tool turns use the `.example` domain.
- Run `tests/services/pipecat_voice/test_dialogue_library.py` after any edit. It checks schema, uniqueness, opener diversity, trait and tier-transition coverage, and the rubric.
