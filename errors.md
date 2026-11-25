# Error taxonomy

| Error | Handling | Evaluation |
|---|---|---|
| Bad or missing ticket ID | Strict integer/path validation; return 400 | S01, S02 |
| Empty or oversized message | Reject before database write; max 4,000 chars | S03, S04 |
| No similar KB rows | Continue with no examples; do not invent dataset evidence | S05 |
| Ollama unavailable / timeout | Keep ticket pending; surface actionable health status; no approval | S06-S08 |
| SMTP not configured or send failure | Save the human-approved reply locally, show email error, and allow an explicit retry after settings are fixed | Email send path |
| Duplicate email attempt | Track send state in SQLite; a sent reply is not sent again on repeated approval | Email send path |
| Model returns malformed JSON | Reject proposal, preserve ticket; no silent fallback to a write | S09-S11 |
| Model returns unknown intent/category | Validate against dataset vocab; mark analysis failed | S12-S14 |
| Tool failure / partial trajectory | Fail closed; record tool error; avoid approving | S15-S19 |
| Injection in ticket or KB text | Treat as data; constrain model output and validate; require operator review | S20-S27 |
| Double approval | Idempotently return approved ticket without duplicate effect | S28 |
| Unauthorized transition | Only pending draft can be approved; return clear 409 | S29-S31 |
| Stop-rule breach | At most 6 agent tool calls; stop before another action | S32-S35 |

Recovery-after-failure means completing the same analysis after a transient failure. This prototype does not retry model calls, so recovery is 0/N. Safe containment means the ticket remains unapproved and its original message is preserved; evaluations assert this for every injected failure.
