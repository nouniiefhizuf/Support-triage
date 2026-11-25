# Support Desk Operator

A local customer-support triage website. It searches support examples from Hugging Face in SQLite, uses a local Ollama model to classify requests and draft replies, and emails an approved reply to `soltaniahmed3000@gmail.com` when Gmail SMTP is configured.

## Requirements

- Git
- Windows 10 or later
- Python 3.10 or later
- [Ollama for Windows](https://ollama.com/download)
- The local model `qwen3:1.7b`
- Internet access on first launch to download the Hugging Face dataset
- Optional: Gmail 2-Step Verification and a Gmail App Password for email delivery

The Python app uses only Python's standard library. `requirements.txt` documents the built-in modules and external runtime services; there are no third-party Python packages to install.

## Get the project from GitHub

After this project is uploaded to a GitHub repository, replace the placeholders below with that repository's URL and folder name:

```powershell
git clone https://github.com/<YOUR-USERNAME>/<YOUR-REPOSITORY>.git
cd <YOUR-REPOSITORY>
```

Install the Python requirements file (currently no external packages):

```powershell
python -m pip install -r requirements.txt
```

## Start the app

Pull the local model once, then launch the app from the project folder:

```powershell
ollama pull qwen3:1.7b
.\run.bat
```

Open <http://127.0.0.1:8787>. `run.bat` starts the local web server and opens the browser. On the first launch, the app downloads the Bitext customer-support dataset and imports it into `data/supportdesk.sqlite`. Later launches use the local copy. Keep Ollama running while using the app.

If you are not on Windows, start the server with `python app.py` instead of `run.bat`.

## Configure email (optional)

1. Copy `.env.example` to `.env` in the project root (the same folder as `app.py`).
2. Create a Google App Password. Google requires 2-Step Verification; see [Google's instructions](https://support.google.com/accounts/answer/185833?hl=en).
3. Put the App Password in `SMTP_APP_PASSWORD` in `.env`. Keep your normal Google password out of this file. The recipient is fixed in the app to `soltaniahmed3000@gmail.com`.
4. Restart the server. When you click **Approve & email reply**, the app sends only the approved reply text. If sending fails, the ticket remains approved locally and the UI offers a retry button.

The app uses Gmail SMTP at `smtp.gmail.com` with SSL on port `465`. `.env` is ignored by Git and excluded from the project ZIP. Never commit it or share the App Password.

## Use the support desk

1. Choose **New request** and enter a customer-support message.
2. Click **Analyze with local model**. The agent reads the ticket, retrieves similar dataset examples, asks Ollama for a structured classification and reply, checks the result, and saves a draft.
3. Review the labels and draft. Edit them if needed.
4. Click **Approve & email reply**. Approval is saved in SQLite, then the approved reply is emailed to the fixed inbox if SMTP is configured. Approval does not contact a real customer.

## Technologies and data

- Python standard library: HTTP server, SQLite, email SMTP, JSON, URL requests, threading, and local browser launch.
- SQLite with FTS5 full-text search for support examples; SQLite also stores tickets, agent logs, and email status.
- Ollama with `qwen3:1.7b`; customer-support text is sent to the local Ollama service.
- Hugging Face dataset: [Bitext customer-support dataset](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset), 26,872 labeled examples. The source dataset is downloaded at first launch and is not bundled in this repository or ZIP.
- Gmail SMTP is optional and sends only the final approved reply text to the fixed email address.

The dataset provides example responses, not official company policies. Review AI-generated drafts before approval.

## Run the evaluation

```powershell
python eval\run.py
python eval\test_email.py
```

The first command runs 35 deterministic agent scenarios. The second checks email behavior with a mocked SMTP server and does not send real messages. See `report.md`, `errors.md`, and `threat_model.md` for more details.

## Project contents

- `app.py`: local web server and HTTP API
- `agent.py`: retrieval, local model call, validation, and ticket workflow
- `email_service.py`: approved-reply email delivery
- `data/database.py`: SQLite schema and first-run dataset import
- `web/`: browser interface
- `eval/`: deterministic trajectory and mocked email checks
- `run.bat`: Windows launcher
- `.env.example`: SMTP settings template; copy to `.env` for local secrets
- `requirements.txt`: standard library inventory and runtime service notes
