"""Offline tests for approved-reply email delivery; SMTP is mocked."""
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import email_service


class FakeSMTP:
    sent=[]
    def __init__(self,*args,**kwargs): pass
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def login(self,*args): pass
    def send_message(self,message): self.sent.append(message)


class EmailDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
          CREATE TABLE tickets(id INTEGER PRIMARY KEY,status TEXT,final_reply TEXT,
            email_status TEXT,email_sent_at TEXT,email_attempted_at TEXT,email_error TEXT);
          CREATE TABLE tool_logs(id INTEGER PRIMARY KEY,ticket_id INTEGER,tool_name TEXT,
            input_json TEXT,output_json TEXT,ok INTEGER,elapsed_ms INTEGER,created_at TEXT);
          INSERT INTO tickets VALUES(1,'approved','Thanks for contacting support.','not_sent',NULL,NULL,NULL);
        ''')
        FakeSMTP.sent.clear()

    def tearDown(self): self.db.close()

    def test_sends_only_approved_reply_and_is_idempotent(self):
        config={"recipient":email_service.RECIPIENT,"configured":True,"user":"sender@example.com",
                "password":"fake-secret","host":"smtp.example.com","port":465}
        with patch.object(email_service,"email_settings",return_value=config), patch.object(email_service.smtplib,"SMTP_SSL",FakeSMTP):
            first=email_service.send_approved_reply(self.db,1)
            second=email_service.send_approved_reply(self.db,1)
        self.assertTrue(first["sent"])
        self.assertTrue(second["already_sent"])
        self.assertEqual(len(FakeSMTP.sent),1)
        self.assertEqual(FakeSMTP.sent[0]["To"],email_service.RECIPIENT)
        self.assertEqual(FakeSMTP.sent[0].get_content().strip(),"Thanks for contacting support.")
        self.assertEqual(first["ticket"]["email_status"],"sent")

    def test_missing_credentials_does_not_attempt_send(self):
        with patch.object(email_service,"email_settings",return_value={"configured":False,"recipient":email_service.RECIPIENT}), patch.object(email_service.smtplib,"SMTP_SSL",FakeSMTP):
            result=email_service.send_approved_reply(self.db,1)
        self.assertFalse(result["sent"])
        self.assertEqual(result["ticket"]["email_status"],"not_configured")
        self.assertEqual(FakeSMTP.sent,[])


if __name__=='__main__': unittest.main(verbosity=2)
