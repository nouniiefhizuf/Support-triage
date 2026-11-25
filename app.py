import json, mimetypes, os, sys, threading, urllib.request, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from data.database import init_db, connect, meta, DB_PATH, DATASET_ID
from agent import run_agent, approve_draft, validate_new_message, AgentError, OLLAMA_BASE, OLLAMA_MODEL
from email_service import email_settings, send_approved_reply

ROOT=Path(__file__).resolve().parent
WEB=ROOT/"web"
HOST="127.0.0.1"; PORT=int(os.environ.get("PORT","8787"))
init_db().close()

def health():
    try:
        with urllib.request.urlopen(OLLAMA_BASE+"/api/tags",timeout=3) as r: tags=json.loads(r.read().decode())
        names=[m.get("name","") for m in tags.get("models",[])]
        if OLLAMA_MODEL in names or any(n.split(":")[0]==OLLAMA_MODEL.split(":")[0] for n in names):
            return {"ok":True,"model":OLLAMA_MODEL,"host":OLLAMA_BASE}
        return {"ok":False,"model":OLLAMA_MODEL,"host":OLLAMA_BASE,"error":"Model is not installed. Run: ollama pull "+OLLAMA_MODEL}
    except Exception:
        return {"ok":False,"model":OLLAMA_MODEL,"host":OLLAMA_BASE,"error":"Ollama is not reachable. Start Ollama, then refresh this page."}

class Handler(BaseHTTPRequestHandler):
    server_version="SupportDesk/1.0"
    def setup(self):
        super().setup(); self.db=connect()
    def finish(self):
        try: super().finish()
        finally: self.db.close()
    def log_message(self,*args): pass
    def send_json(self,status,obj):
        body=json.dumps(obj,ensure_ascii=False,default=str).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)
    def body_json(self):
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n>12000: raise ValueError("Request body is too large")
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception as e: raise ValueError("Invalid JSON request") from e
    def do_GET(self):
        p=urlparse(self.path).path
        if p=="/api/health":
            m=meta(self.db); mail=email_settings(); return self.send_json(200,{"ollama":health(),"email":{"configured":mail["configured"],"recipient":mail["recipient"]},"dataset":{"id":m.get("dataset_id",DATASET_ID),"rows":int(m.get("dataset_rows","0")),"imported_at":m.get("dataset_imported_at")},"database":str(DB_PATH.name)})
        if p=="/api/state":
            tickets=[dict(r) for r in self.db.execute("SELECT * FROM tickets ORDER BY id DESC LIMIT 100")]
            counts={r["status"]:r["n"] for r in self.db.execute("SELECT status,COUNT(*) n FROM tickets GROUP BY status")}
            logs=[dict(r) for r in self.db.execute("SELECT id,ticket_id,tool_name,ok,elapsed_ms,created_at FROM tool_logs ORDER BY id DESC LIMIT 30")]
            return self.send_json(200,{"tickets":tickets,"counts":counts,"logs":logs})
        if p.startswith("/api/tickets/"):
            try:
                tid=int(p.rsplit("/",1)[1]); row=self.db.execute("SELECT * FROM tickets WHERE id=?",(tid,)).fetchone()
                if not row: return self.send_json(404,{"error":"Ticket not found"})
                logs=[dict(r) for r in self.db.execute("SELECT * FROM tool_logs WHERE ticket_id=? ORDER BY id",(tid,))]
                return self.send_json(200,{"ticket":dict(row),"logs":logs})
            except Exception: return self.send_json(400,{"error":"Invalid ticket ID"})
        if p=="/": p="/index.html"
        rel=Path(unquote(p.lstrip("/")))
        if ".." in rel.parts: return self.send_json(403,{"error":"Forbidden"})
        file=(WEB/rel).resolve()
        if WEB.resolve() not in file.parents and file!=WEB.resolve(): return self.send_json(403,{"error":"Forbidden"})
        if not file.is_file(): return self.send_json(404,{"error":"Not found"})
        data=file.read_bytes(); self.send_response(200); self.send_header("Content-Type",mimetypes.guess_type(file.name)[0] or "application/octet-stream"); self.send_header("Content-Length",str(len(data))); self.send_header("X-Content-Type-Options","nosniff"); self.end_headers(); self.wfile.write(data)
    def do_POST(self):
        p=urlparse(self.path).path
        try: body=self.body_json()
        except ValueError as e: return self.send_json(400,{"error":str(e)})
        if p=="/api/tickets":
            try: msg=validate_new_message(body.get("message"))
            except AgentError as e: return self.send_json(400,{"error":str(e)})
            from datetime import datetime,timezone
            now=datetime.now(timezone.utc).isoformat()
            cur=self.db.execute("INSERT INTO tickets(message,status,created_at,updated_at) VALUES(?,'new',?,?)",(msg,now,now)); self.db.commit()
            return self.send_json(201,{"ticket":dict(self.db.execute("SELECT * FROM tickets WHERE id=?",(cur.lastrowid,)).fetchone())})
        bits=p.strip("/").split("/")
        if len(bits)==4 and bits[0]=="api" and bits[1]=="tickets":
            try: tid=int(bits[2])
            except ValueError: return self.send_json(400,{"error":"Invalid ticket ID"})
            if bits[3]=="analyze":
                result=run_agent(self.db,tid)
                return self.send_json(200 if "error" not in result else 502,result)
            if bits[3]=="approve":
                try:
                    approved=approve_draft(self.db,tid,body.get("reply"),body.get("category"),body.get("intent"))
                    delivery=send_approved_reply(self.db,tid)
                    approved["ticket"]=delivery.get("ticket",approved["ticket"])
                    approved["email"]={"sent":delivery["sent"],"error":delivery.get("error"),"already_sent":delivery.get("already_sent",False)}
                    return self.send_json(200,approved)
                except Exception as e: return self.send_json(409,{"error":str(e)})
            if bits[3]=="send":
                result=send_approved_reply(self.db,tid)
                return self.send_json(200 if result.get("ticket") else 409,result)
        return self.send_json(404,{"error":"Unknown action"})

if __name__=="__main__":
    try:
        startup_db=connect(); rowcount=startup_db.execute("SELECT COUNT(*) FROM reference_examples").fetchone()[0]; startup_db.close()
    except Exception as e:
        print("Database setup failed:",e); sys.exit(1)
    print(f"Support Desk Operator is ready at http://{HOST}:{PORT}")
    print(f"Hugging Face knowledge examples: {rowcount:,} | SQLite: {DB_PATH}")
    print(f"Ollama: {OLLAMA_BASE} | model: {OLLAMA_MODEL}")
    threading.Timer(1.0,lambda:webbrowser.open(f"http://{HOST}:{PORT}")).start()
    try: ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
    except KeyboardInterrupt: print("\nServer stopped.")
