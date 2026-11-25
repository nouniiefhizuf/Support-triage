import json, os, shutil, sqlite3, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from data import database
from agent import run_agent, approve_draft, validate_new_message, AgentError, MAX_STEPS

cases=json.loads((Path(__file__).with_name("scenarios.json")).read_text(encoding="utf-8"))["scenarios"]
source=database.init_db()
tmpdir=tempfile.TemporaryDirectory(prefix="supportdesk-eval-")
test_path=Path(tmpdir.name)/"eval.sqlite"
target=sqlite3.connect(test_path)
source.backup(target); source.close(); target.close()
database.DB_PATH=test_path
db=database.connect()
db.execute("DELETE FROM tickets"); db.execute("DELETE FROM tool_logs"); db.commit()
passed=0; failures=[]

def new_ticket(message):
    from datetime import datetime,timezone
    n=datetime.now(timezone.utc).isoformat()
    cur=db.execute("INSERT INTO tickets(message,status,created_at,updated_at) VALUES(?,'new',?,?)",(message,n,n)); db.commit(); return cur.lastrowid

def fake_for(c):
    cats=[r[0] for r in db.execute("SELECT DISTINCT category FROM reference_examples ORDER BY category")]
    intents=[r[0] for r in db.execute("SELECT DISTINCT intent FROM reference_examples ORDER BY intent")]
    mode=c.get("model")
    if mode=="malformed": return lambda t,e: "not json"
    def model(ticket,examples):
        result={"category":cats[0],"intent":intents[0],"urgency":c.get("urgency","normal"),"summary":"Customer is asking for support with their request.","reply":"Thanks for reaching out. I understand your concern. Please share the relevant order details through the official support page so the team can look into this for you.","confidence":0.82}
        if mode=="bad_category": result["category"]="UNKNOWN"
        if mode=="bad_intent": result["intent"]="unknown_action"
        if mode=="bad_urgency": result["urgency"]="critical"
        if mode=="empty_summary": result["summary"]=""
        if mode=="long_reply": result["reply"]="x"*3001
        if mode=="bad_confidence": result["confidence"]=1.2
        return result
    return model

for c in cases:
    try:
        if c.get("invalid") in ("oversize","empty"):
            msg="x"*4001 if c["invalid"]=="oversize" else ""
            try:
                validate_new_message(msg); raise AssertionError("input should be rejected")
            except AgentError: pass
            passed+=1; continue
        if c.get("invalid")=="missing":
            result=run_agent(db,999999,fake_model=fake_for(c))
            if "error" not in result or "not found" not in result["error"].lower(): raise AssertionError("missing ticket should fail clearly")
            passed+=1; continue
        if c.get("invalid")=="bad_id":
            result=run_agent(db,"abc",fake_model=fake_for(c))
            if "error" not in result: raise AssertionError("non-numeric id should fail clearly")
            passed+=1; continue
        if c.get("invalid")=="approve_new":
            tid=new_ticket("A new request")
            try: approve_draft(db,tid,"This reply should not be approved because no draft exists."); raise AssertionError("approval before draft should fail")
            except AgentError: passed+=1; continue
        tid=new_ticket(c.get("message","Test message"))
        before=c.get("message","Test message")
        if c.get("preserve"):
            res=run_agent(db,tid,fake_model=fake_for(c),fail_tool=c.get("fail_tool"))
        else:
            res=run_agent(db,tid,fake_model=fake_for(c),fail_tool=c.get("fail_tool"))
        trace=res["trajectory"]
        if c.get("tools") and [x["tool"] for x in trace] != c["tools"][:len(trace)]: raise AssertionError(f"trajectory {[x['tool'] for x in trace]} != {c['tools'][:len(trace)]}")
        if len(trace)>MAX_STEPS: raise AssertionError("step cap exceeded")
        row=db.execute("SELECT * FROM tickets WHERE id=?",(tid,)).fetchone()
        if c.get("status")=="failed" and "error" not in res: raise AssertionError("expected safe failure")
        if c.get("status")=="draft" and row["status"]!="draft": raise AssertionError(f"expected draft, got {row['status']}")
        if c.get("status")=="failed" and row["status"]!="failed": raise AssertionError(f"expected failed, got {row['status']}")
        if c.get("preserve") and row["message"]!=before: raise AssertionError("original message changed")
        if c.get("approve"):
            reply="This is the edited reply that the operator reviewed and saved in the local ticket database." if c.get("edit_reply") else row["draft_reply"]
            first=approve_draft(db,tid,reply)
            if first["ticket"]["status"]!="approved": raise AssertionError("approval state not saved")
            if c.get("edit_reply") and first["ticket"]["final_reply"]!=reply: raise AssertionError("operator's edited reply not saved")
            if c.get("approve_twice") and not approve_draft(db,tid,reply)["already_approved"]: raise AssertionError("repeat approval was not idempotent")
        if c.get("tools") and c.get("approve"):
            all_tools=[r[0] for r in db.execute("SELECT tool_name FROM tool_logs WHERE ticket_id=? ORDER BY id",(tid,))]
            if all_tools!=c["tools"]: raise AssertionError(f"full trajectory {all_tools} != {c['tools']}")
        if c.get("approve_empty"):
            try: approve_draft(db,tid,""); raise AssertionError("empty approval should fail")
            except AgentError: pass
        if c.get("analyze_twice"):
            run_agent(db,tid,fake_model=fake_for(c)); n=db.execute("SELECT COUNT(*) FROM tickets WHERE id=?",(tid,)).fetchone()[0]
            if n!=1: raise AssertionError("reanalysis duplicated ticket")
        if c.get("stop_check") and len(trace)>MAX_STEPS: raise AssertionError("stop rule check failed")
        if c.get("approve") and not c.get("approve_twice"):
            n=db.execute("SELECT COUNT(*) FROM tool_logs WHERE ticket_id=? AND tool_name='approve_draft'",(tid,)).fetchone()[0]
            if n!=1: raise AssertionError("approval should have exactly one logged write")
        passed+=1
    except Exception as e: failures.append(f"{c['id']} {c['name']}: {e}")

print(f"Support desk trajectory evaluation: {passed}/{len(cases)} passed")
db.close(); tmpdir.cleanup()
if failures:
    print("\n".join(failures)); sys.exit(1)
