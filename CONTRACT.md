# CONTRACT — backend <-> frontend data shapes (orchestrator-owned; change only via `reviews/developer.md` + orchestrator OK)

All JSON, snake_case. Fields (canonical names): `shipper, consignee, notify_party, port_of_loading, port_of_discharge, container_count, gross_weight_kg`.

## Node ids (graph)
`inbox`, `classifier`, `field:shipper`, `field:consignee`, `field:notify_party`, `field:port_of_loading`,
`field:port_of_discharge`, `field:container_count`, `field:gross_weight_kg`, `aggregator`, `gate`, `report`
(`compare` is a pure function inside the aggregator step; it emits its own event with node `compare` between aggregator and gate. Non-comparison emails stop after `classifier` -> `report`.)

## Trace event
```json
{"seq": 0, "t_ms": 0, "node": "classifier", "state": "start|done|error|skipped",
 "engine": "gemini|rules|pure|flynet", "duration_ms": 12, "summary": "short human string", "payload": {}}
```
`payload` per node: classifier -> `{category, confidence, reasons[]}`; field:* -> `{field, si_value, bl_value, si_evidence, bl_evidence, confidence}`;
compare -> `{fields:[FieldResult]}`; gate -> `{suspicion, threshold, escalate, input_vector[], kc_active[], winner_kc, reason}`; report -> the Result below.

## Result (one per email)
```json
{"email_id":"email_004","from":"..","subject":"..","received_at":"..",
 "category":"BL_COMPARISON|SI_REQUEST|INVOICE_QUERY|GENERAL|SPAM",
 "status":"OK|MISMATCH|NEEDS_REVIEW|null",   // null for non-comparison categories
 "review_reason":"wrong_doc_type|missing_attachment|unreadable|missing_value|null",
 "has_defect":false,"defect_fields":[],
 "headline":"No mismatch detected | container_count: SI 3 / BL 4 | Needs review: unreadable",
 "fields":[{"field":"container_count","si_value":"3","bl_value":"4","si_norm":3,"bl_norm":4,"match":false,
            "confidence":0.93,"si_evidence":"Total Containers: 3","bl_evidence":"No. of Containers 4","note":null}],
 "gate":{"suspicion":0.12,"threshold":0.5,"escalate":false,"reason":"...","input_vector":[..],"kc_active":[..],"winner_kc":17},
 "escalation":null,   // or {"open":true,"reason":"...","evidence":[{"doc":"SI","field":"..","text":".."}],"resolved":false}
 "engine":{"classifier":"rules","fields":"rules"}, "errors":[], "events":[/* Trace events */]}
```

## HTTP API (FastAPI, prefix `/api`, CORS open for dev)
- `GET /api/health` -> `{ok, engine:"gemini|rules", n_emails}`
- `GET /api/emails` -> `[{email_id, from, subject, received_at, has_attachments, result_summary|null}]`
- `POST /api/process/{email_id}` -> `text/event-stream` of Trace events, final event node `report` carries Result. `?force_engine=rules|gemini`.
- `GET /api/result/{email_id}` -> Result (404 if not processed). `POST /api/retry/{email_id}` re-runs failed/errored nodes, streams like process.
- `POST /api/process_all` -> SSE batch progress (for stats), also writes `backend/out/submission.json`.
- `POST /api/review/{email_id}` body `{"decision":"confirm_mismatch|confirm_ok|correct_field","field":"consignee","corrected_si":null,"corrected_bl":null,"escalation_verdict":"escalation_correct|escalation_unneeded"}`
  -> updated Result; also applies a Hebbian update to the fly net.
- `GET /api/flybrain` -> `{n_inputs, n_kc, kc_sparsity, threshold, projection:[[input_idx..] per kc], weights:[..], history:[{ts, before, after, verdict}]}`
- `GET /api/stats` -> `{emails_total, processed, classified:{cat:count}, comparisons, mismatches, needs_review, discrepancies_found, accuracy_vs_labels|null, top_issues:[{label,count}]}`

## Replay artifacts (written by `python -m sdoc.export_replay`, served static by the frontend)
`frontend/public/replay/index.json` = list of email summaries + Results (without `events`), `frontend/public/replay/traces/<email_id>.json` = full Result incl. events,
`frontend/public/replay/stats.json`, `frontend/public/replay/flybrain.json`, `frontend/public/replay/submission.json`.
NEVER include ground-truth labels in replay artifacts (accuracy may be a single number computed offline; label `accuracy_vs_labels` only).
