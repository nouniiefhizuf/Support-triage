# Project 3 report: Support Desk Operator

## Task and tools

The app takes a customer-support message, finds similar examples in a Hugging Face dataset, asks a local Ollama model to classify the request and draft a response, and lets an operator approve the saved draft. The five agent tools are `get_ticket`, `search_huggingface_examples`, `ask_local_ollama`, `guard_triage_output`, and `save_draft`. After the human approval action, the separate email service sends the approved reply text through Gmail SMTP to the fixed demo-client inbox `soltaniahmed3000@gmail.com` when configured.

## Database, loop, and stopping proof

The app imports the 26,872-row Bitext customer-support dataset from Hugging Face into local SQLite tables. An FTS5 index makes retrieval searchable. Agent order: load ticket, retrieve top examples, call Ollama, apply deterministic safety checks, save a pending draft. The loop is capped at 6 tool calls; a successful analysis uses five. The 35-scenario eval asserts the cap for all agent traces and checks expected ordered tools and outcomes.

## Web app and human checkpoint

`run.bat` starts the local website at `http://127.0.0.1:8787`. Users submit or select a request, inspect classification and reply, edit the draft, and approve it. Approval is saved in SQLite and triggers email of the final reply text to the fixed recipient. Email status and errors are stored for review; failed sends can be retried after fixing SMTP settings. Gmail App Passwords are held in local `.env` configuration and excluded from the archive.

## Evaluation

Run `python eval/run.py` for the 35 agent trajectory scenarios and `python eval/test_email.py` for mocked SMTP behavior. These cover normal analysis, writes, invalid input, model/tool failure, duplicate approval, state-transition enforcement, injection attempts, credential-missing email behavior, and no duplicate on repeat send. The agent does not automatically retry failed model requests; email delivery can be retried after the operator fixes SMTP settings.

## Threat model and cost

See `threat_model.md` and `errors.md`. Ticket and retrieved text are untrusted data. The local model has no tools; schema validation and the human approval gate precede saving and emailing. The corpus and model run locally after setup. Gmail SMTP is used only to transmit an approved reply, with credentials stored in local `.env`; there is no AI API bill. Compute cost is local CPU/GPU and model memory. Per-run latency can be measured from logs; p50/p95 should be reported from the demo machine. The dataset provides examples, not authoritative company policy.
