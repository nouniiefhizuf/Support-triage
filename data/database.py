import csv
import os
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("SUPPORT_DB", DATA / "supportdesk.sqlite"))
CSV_PATH = DATA / "Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"
DATASET_URL = "https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset/resolve/main/Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv"
DATASET_ID = "bitext/Bitext-customer-support-llm-chatbot-training-dataset"

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS reference_examples(
 id INTEGER PRIMARY KEY, flags TEXT NOT NULL, instruction TEXT NOT NULL,
 category TEXT NOT NULL, intent TEXT NOT NULL, response TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tickets(
 id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','draft','approved','failed')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 category TEXT, intent TEXT, urgency TEXT, summary TEXT,
 draft_reply TEXT, final_reply TEXT, confidence REAL, last_error TEXT,
 email_status TEXT NOT NULL DEFAULT 'not_sent', email_sent_at TEXT, email_attempted_at TEXT, email_error TEXT
);
CREATE TABLE IF NOT EXISTS tool_logs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER,
 tool_name TEXT NOT NULL, input_json TEXT NOT NULL, output_json TEXT NOT NULL,
 ok INTEGER NOT NULL, elapsed_ms INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    return db

def ensure_dataset_file():
    if CSV_PATH.exists() and CSV_PATH.stat().st_size > 100_000:
        return
    request = urllib.request.Request(DATASET_URL, headers={"User-Agent": "SupportDeskOperator/1.0"})
    tmp = CSV_PATH.with_suffix(CSV_PATH.suffix + ".download")
    try:
        with urllib.request.urlopen(request, timeout=90) as response, open(tmp, "wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk: break
                out.write(chunk)
        if tmp.stat().st_size < 100_000:
            raise RuntimeError("Hugging Face returned an unexpectedly small dataset file")
        tmp.replace(CSV_PATH)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise

def import_dataset(db):
    ensure_dataset_file()
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"instruction", "category", "intent", "response"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise RuntimeError(f"Unexpected Hugging Face CSV columns: {reader.fieldnames}")
        batch = []
        for row in reader:
            instruction = (row.get("instruction") or "").strip()
            response = (row.get("response") or "").strip()
            if not instruction or not response: continue
            batch.append(((row.get("flags") or "").strip(), instruction,
                          (row.get("category") or "OTHER").strip().upper(),
                          (row.get("intent") or "other").strip().lower(), response))
    db.execute("DELETE FROM reference_examples")
    db.executemany("INSERT INTO reference_examples(flags,instruction,category,intent,response) VALUES(?,?,?,?,?)", batch)
    db.execute("INSERT OR REPLACE INTO app_meta(key,value) VALUES('dataset_id',?)", (DATASET_ID,))
    db.execute("INSERT OR REPLACE INTO app_meta(key,value) VALUES('dataset_rows',?)", (str(len(batch)),))
    db.execute("INSERT OR REPLACE INTO app_meta(key,value) VALUES('dataset_imported_at',?)", (datetime.now(timezone.utc).isoformat(),))
    try:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS examples_fts USING fts5(instruction, category, intent, content='reference_examples', content_rowid='id', tokenize='unicode61 remove_diacritics 2')")
        db.execute("INSERT INTO examples_fts(examples_fts) VALUES('rebuild')")
        db.execute("INSERT OR REPLACE INTO app_meta(key,value) VALUES('fts_enabled','true')")
    except sqlite3.OperationalError:
        db.execute("INSERT OR REPLACE INTO app_meta(key,value) VALUES('fts_enabled','false')")
    db.commit()

def init_db():
    db = connect()
    db.executescript(SCHEMA)
    columns={r[1] for r in db.execute("PRAGMA table_info(tickets)")}
    for name,definition in (("email_status","TEXT NOT NULL DEFAULT 'not_sent'"),("email_sent_at","TEXT"),("email_attempted_at","TEXT"),("email_error","TEXT")):
        if name not in columns: db.execute(f"ALTER TABLE tickets ADD COLUMN {name} {definition}")
    row = db.execute("SELECT value FROM app_meta WHERE key='dataset_rows'").fetchone()
    count = db.execute("SELECT COUNT(*) FROM reference_examples").fetchone()[0]
    if not row or count == 0:
        import_dataset(db)
    db.commit()
    return db

def meta(db):
    return {r["key"]: r["value"] for r in db.execute("SELECT key,value FROM app_meta")}
