# RAG cross-encoder ops monitoring

**Scope:** Production health for STA-150 hybrid rerank (`cross-encoder/ms-marco-MiniLM-L-6-v2`).  
**Latest report:** [`rag-cross-encoder-prod-latest.json`](rag-cross-encoder-prod-latest.json)

---

## What to watch

| Log pattern | Level | Meaning |
|-------------|-------|---------|
| `rag_cross_encoder_loading model=` | INFO | Model download/load started (first use per process) |
| `rag_rerank org_id=… method=cross_encoder` | INFO | Healthy rerank path |
| `rag_rerank org_id=… method=lexical_overlap` | INFO | Fallback rerank (no cross-encoder scores) |
| `cross_encoder_load_failed error=` | WARNING | Model load failed — check memory, HF hub, disk |
| `cross_encoder_predict_failed error=` | WARNING | Scoring failed after load |
| `sentence_transformers unavailable` | WARNING | Package missing or import error |

Fallback behavior is safe: RAG continues with lexical overlap rerank (`hybrid_rerank.py`).

---

## Automated check

```bash
npm run rag:cross-encoder:report
```

Steps:

1. **Live probe** — `POST /api/rag-enhanced/query` with admin JWT; reads `metrics.rerank_method` and `cross_encoder_enabled`.
2. **Log scan** — when `RAILWAY_TOKEN` is set, runs `railway logs --service gravitre-saas-backend --lines 1500` and counts failure patterns.

Exit codes: `0` pass/warn, `1` fail (probe HTTP error).

---

## Manual Railway log grep

```bash
railway logs --service gravitre-saas-backend --lines 2000 | rg "cross_encoder|rag_rerank|sentence_transformers"
```

Or in Railway dashboard → **gravitre-saas-backend** → **Logs** → filter `cross_encoder`.

---

## Triage

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| `cross_encoder_unavailable` | `sentence-transformers` not installed | Verify `backend/requirements.txt` on deploy; redeploy |
| `cross_encoder_load_failed` OOM | Model too heavy for Railway plan | Set `RAG_DISABLE_CROSS_ENCODER=true` or upgrade memory |
| `cross_encoder_load_failed` network | HuggingFace download blocked | Pre-bake model in image or set `HF_HOME` cache |
| Probe `lexical_overlap`, no log failures | No chunks indexed | Ingest docs; probe query needs RAG corpus |
| Probe OK, log failures in window | Transient load errors | Watch recurrence; check deploy restarts |

---

## Env knobs

| Variable | Default | Effect |
|----------|---------|--------|
| `RAG_CROSS_ENCODER_ENABLED` | `true` | Master toggle |
| `RAG_DISABLE_CROSS_ENCODER` | `false` | Force lexical fallback |
| `RAG_CROSS_ENCODER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | HF model id |

---

## Cadence

- After backend deploys that touch `rag/` or Python deps.
- Monthly ops review alongside `npm run smoke:ai-production:report`.

---

## Latest run (2026-06-16)

Report: [`rag-cross-encoder-prod-latest.json`](rag-cross-encoder-prod-latest.json) · **status: pass**

| Check | Result |
|-------|--------|
| `/api/rag-enhanced/query` reachable | ✅ |
| `cross_encoder_enabled` in prod | `true` |
| `cross_encoder_load_failed` (1500 log lines) | **0** |
| `cross_encoder_predict_failed` | **0** |
| `sentence_transformers unavailable` | **0** |
| `rerank_method` on probe | `none` — no indexed chunks in smoke org; encoder not exercised |

**Takeaway:** No load failures in recent prod logs. Cross-encoder is enabled but idle until RAG corpus traffic hits the rerank path. After ingest, expect `rag_cross_encoder_loading` / `rag_rerank … method=cross_encoder` in logs.
