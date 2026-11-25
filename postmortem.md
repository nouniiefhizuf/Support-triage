# Postmortem

The first version was a terminal-only inventory demo and did not meet the request for an actual dataset, local model, or usable website. We replaced it with a browser-based support desk, an SQLite knowledge base seeded from the full Hugging Face Bitext dataset, and a real Ollama connection. Ollama was installed and already had `qwen3:1.7b`; the local service was verified through `/api/tags`.

The initial attempt to fetch the Hugging Face data with Windows PowerShell and curl failed because their TLS configuration could not negotiate the connection. Python's bundled runtime succeeded, so the dataset import now uses Python's standard HTTPS client. The result is cached as CSV and SQLite so later starts work offline.

The key design lesson is to keep model generation separate from effects. The model drafts; fixed tools validate; an operator approves. This prevents the model from sending messages or mutating arbitrary records. The app still is a local prototype, not a deployed customer-support service. Next steps would be calibrated confidence, review analytics, role-based access, concurrency handling, and a separate integration with a real test support account.
