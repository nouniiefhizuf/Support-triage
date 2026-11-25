"""Send approved replies to the fixed demo-client inbox using local Gmail SMTP settings."""
import os
import smtplib
import ssl
from datetime import timedelta
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

RECIPIENT = "soltaniahmed3000@gmail.com"
ROOT = Path(__file__).resolve().parent


def _load_local_env():
    env_file = ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key in {"SMTP_USER", "SMTP_APP_PASSWORD", "SMTP_HOST", "SMTP_PORT"}:
            os.environ.setdefault(key, value)


def email_settings():
    _load_local_env()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_APP_PASSWORD", "").replace(" ", "").strip()
    return {
        "recipient": RECIPIENT,
        "configured": bool(user and password),
        "user": user,
        "password": password,
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com").strip(),
        "port": int(os.environ.get("SMTP_PORT", "465")),
    }


def send_approved_reply(db, ticket_id):
    row = db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not row:
        return {"sent": False, "error": "Ticket not found."}
    ticket = dict(row)
    if ticket["status"] != "approved":
        return {"sent": False, "error": "Approve the reply before emailing it."}
    if ticket.get("email_status") == "sent":
        return {"sent": True, "already_sent": True, "ticket": ticket}
    if ticket.get("email_status") == "sending" and ticket.get("email_attempted_at"):
        try:
            attempted=datetime.fromisoformat(ticket["email_attempted_at"])
            if datetime.now(timezone.utc)-attempted < timedelta(minutes=2):
                return {"sent": False, "error": "An email attempt is already in progress. Wait a moment before retrying.", "ticket": ticket}
        except ValueError:
            pass

    settings = email_settings()
    now = datetime.now(timezone.utc).isoformat()
    if not settings["configured"]:
        message = "Email is not configured. Add SMTP_USER and SMTP_APP_PASSWORD to the local .env file."
        db.execute("UPDATE tickets SET email_status='not_configured',email_error=? WHERE id=?", (message, ticket_id))
        db.commit()
        ticket = dict(db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone())
        return {"sent": False, "error": message, "ticket": ticket}

    claim = db.execute("UPDATE tickets SET email_status='sending',email_attempted_at=?,email_error=NULL WHERE id=? AND email_status=?", (now,ticket_id,ticket.get("email_status","not_sent")))
    db.commit()
    if claim.rowcount != 1:
        latest=dict(db.execute("SELECT * FROM tickets WHERE id=?",(ticket_id,)).fetchone())
        return {"sent":latest.get("email_status")=="sent","already_sent":latest.get("email_status")=="sent","error":"Another email attempt changed this ticket. Refresh before retrying.","ticket":latest}
    try:
        mail = EmailMessage()
        mail["From"] = settings["user"]
        mail["To"] = RECIPIENT
        mail["Subject"] = "Your support request response"
        mail.set_content(ticket["final_reply"] or "")
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings["host"], settings["port"], timeout=25, context=context) as smtp:
            smtp.login(settings["user"], settings["password"])
            smtp.send_message(mail)
    except Exception as exc:
        error = f"Email could not be sent: {type(exc).__name__}: {exc}"[:500]
        db.execute("UPDATE tickets SET email_status='failed',email_error=? WHERE id=?", (error, ticket_id))
        db.commit()
        ticket = dict(db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone())
        return {"sent": False, "error": error, "ticket": ticket}

    db.execute("UPDATE tickets SET email_status='sent',email_sent_at=?,email_error=NULL WHERE id=?", (now, ticket_id))
    db.execute("INSERT INTO tool_logs(ticket_id,tool_name,input_json,output_json,ok,elapsed_ms,created_at) VALUES(?,?,?,?,?,?,?)",
               (ticket_id,"send_approved_email","{}",'{"recipient":"'+RECIPIENT+'","status":"sent"}',1,0,now))
    db.commit()
    ticket = dict(db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone())
    return {"sent": True, "already_sent": False, "ticket": ticket}
