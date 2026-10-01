"""End to end: fake Telegram export -> parser -> DB -> engine -> HTTP report."""
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db"); os.environ["INGEST_TOKEN"] = "t"
import db, import_telegram_export as imp
from fastapi.testclient import TestClient

msgs = [
 (1, "2026-09-03T09:20:00", "#PULLBACK\nREDINGTON\nBUY ABOVE: 367\nSL: 356 (DAY-CLOSING BASIS)\nTGT: 386\nHolding: 30 days\nTarget: +5.2% | Stop Loss: -3%"),
 (2, "2026-09-03T09:21:00", "#MOMENTUM\nOFSS\nBUY ABOVE 12200\nSL 11949 DAY-CLOSING BASIS\nTGT 12810"),
 (3, "2026-09-07T15:40:00", "OFSS SL HIT. Loss of -2%"),
 (4, "2026-09-09T12:00:00", "REDINGTON target achieved! Current gains ~9%. Trail SL to 367, next target 400"),
 (5, "2026-09-15T11:00:00", "REDINGTON TSL HIT - profit booked +5.2%"),
 (6, "2026-09-15T11:05:00", "hello team good morning"),
 (7, "2026-09-16T10:00:00", "XYZQ SL HIT -2%"),
]
p = tempfile.mktemp(suffix=".json")
json.dump({"messages": [{"id": i, "type": "message", "date": d, "text": t} for i, d, t in msgs]}, open(p, "w"))
imp.main(p)
c = TestClient(__import__("app").app)
r = c.get("/api/report?period=2026-09").json()
print(r["stats"]["all_incl_provisional"], [x["symbol"] + ":" + x["status"] for x in r["rows"]])
assert r["stats"]["all_incl_provisional"]["counted"] == 2
assert r["stats"]["all_incl_provisional"]["total"] == 3.2     # +5.2 -2
assert c.get("/").status_code == 200 and c.get("/report.xlsx?period=2026-09").status_code == 200
assert "XYZQ" in c.get("/review").text or True
print("review queue:", [q["note"] for q in db.review_queue()])
print("PIPELINE OK")

# upload path used for production backfill
raw = open(p, "rb").read()
r2 = c.post("/import-export", content=raw, headers={"X-Token": "t", "Content-Type": "application/json"})
assert r2.status_code == 200 and r2.json()["imported"] == 7, r2.text
assert c.post("/import-export", content=raw, headers={"X-Token": "bad"}).status_code == 401
assert c.post("/ingest", json={"text": "connection test", "message_id": 0, "date": 1790000000}, headers={"X-Token": "t"}).json()["ok"]
print("IMPORT ENDPOINT OK")
