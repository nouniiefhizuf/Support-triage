# Threat model: support ticket triage

## Assets and scope

The app stores support messages, analysis, draft replies, approval state, and email delivery state in a local SQLite database. The demo dataset is a public customer-support training corpus; it is used for retrieval examples only. No live customer system is connected.

## Untrusted input and threats

Ticket text and retrieved Hugging Face examples are untrusted. A message can contain instructions such as “ignore your rules,” request hidden data, or attempt to trigger an action. Ollama output is also untrusted. The model could hallucinate policy or return invalid tool choices.

## Controls

- Model only proposes category, intent, short summary, urgency, and a reply. It cannot select tools or access the network, browser, filesystem, credentials, or database.
- Ticket text and examples are marked as quoted data in the prompt; policy requires ignoring embedded instructions.
- Model output must parse as schema-constrained JSON, pass known-vocabulary and length checks, and be shown to a human.
- Only a human **Approve & email reply** click can change a reviewed draft to approved. After approval, the app sends only the approved reply text through Gmail SMTP to the fixed address `soltaniahmed3000@gmail.com`; the customer message and dataset examples are not included in the email.
- Gmail credentials are read from the ignored local `.env` file and are never returned by the API or written to logs. Use a Google App Password, not the account's regular password. The recipient is fixed in source so ticket text cannot choose an arbitrary destination.
- Delivery state is recorded in SQLite. Repeated approval of an already sent ticket does not send a duplicate. A failed or unconfigured send is visible in the UI and can be retried after correcting local settings.
- Parameterized SQL, state-transition checks, local-only HTTP binding, and a 6-call limit bound effects.
- All tools log timestamp, name, safe input summary, result, and duration.

## Residual risks

An inaccurate draft can still be approved by a careless operator. The local app has no authentication and should not be exposed on a public network. For real customer data, add access control, retention controls, consent and privacy review, and a separate approved integration before sending any message. The dataset contains synthetic examples and is not an authoritative company policy manual.
