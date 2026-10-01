"""db.py - SQLite storage. raw_messages is the source of truth; signals/events are rebuilt from it."""
import os, sqlite3
from datetime import date
from engine import Signal, Event
from msgparser import parse_message

DB_PATH = os.environ.get("DB_PATH", "tracker.db")


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS raw_messages(
          id INTEGER PRIMARY KEY, source TEXT, tg_id INTEGER, posted_at TEXT, text TEXT,
          status TEXT DEFAULT 'new', note TEXT DEFAULT '',
          UNIQUE(source, tg_id));
        CREATE TABLE IF NOT EXISTS signals(
          id INTEGER PRIMARY KEY, raw_id INTEGER UNIQUE, symbol TEXT, tag TEXT,
          signal_date TEXT, entry REAL, sl REAL, target REAL, hold_days INTEGER);
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY, raw_id INTEGER, symbol TEXT, event_date TEXT,
          kind TEXT, pct REAL);
        CREATE TABLE IF NOT EXISTS manual_events(
          id INTEGER PRIMARY KEY, symbol TEXT, event_date TEXT, kind TEXT, pct REAL);
        """)


def add_raw(source, tg_id, posted_at, text):
    """Insert or update (edited messages overwrite). posted_at = 'YYYY-MM-DDTHH:MM:SS' IST."""
    with conn() as c:
        c.execute("""INSERT INTO raw_messages(source,tg_id,posted_at,text) VALUES(?,?,?,?)
                     ON CONFLICT(source,tg_id) DO UPDATE SET text=excluded.text""",
                  (source, tg_id, posted_at, text))


def rebuild():
    """Re-parse every stored message in time order. Safe to run any time."""
    with conn() as c:
        c.execute("DELETE FROM signals"); c.execute("DELETE FROM events")
        known = []
        for r in c.execute("SELECT * FROM raw_messages ORDER BY posted_at, id").fetchall():
            kind, res = parse_message(r["text"], known)
            d = r["posted_at"][:10]
            if kind == "signal":
                c.execute("""INSERT INTO signals(raw_id,symbol,tag,signal_date,entry,sl,target,hold_days)
                             VALUES(?,?,?,?,?,?,?,?)""",
                          (r["id"], res["symbol"], res["tag"], d, res["entry"], res["sl"],
                           res["target"], res["hold_days"]))
                if res["symbol"] not in known:
                    known.append(res["symbol"])
                c.execute("UPDATE raw_messages SET status='signal', note='' WHERE id=?", (r["id"],))
            elif kind == "events":
                for e in res:
                    c.execute("INSERT INTO events(raw_id,symbol,event_date,kind,pct) VALUES(?,?,?,?,?)",
                              (r["id"], e["symbol"], d, e["kind"], e["pct"]))
                c.execute("UPDATE raw_messages SET status='event', note='' WHERE id=?", (r["id"],))
            else:
                c.execute("UPDATE raw_messages SET status=?, note=? WHERE id=?",
                          ("review" if kind == "review" else "ignored", res, r["id"]))


def load():
    with conn() as c:
        sigs = [Signal(r["id"], r["symbol"], date.fromisoformat(r["signal_date"]), r["tag"],
                       r["entry"], r["sl"], r["target"])
                for r in c.execute("SELECT * FROM signals")]
        evs = [Event(r["symbol"], date.fromisoformat(r["event_date"]), r["kind"], r["pct"], r["raw_id"])
               for r in c.execute("SELECT * FROM events")]
        evs += [Event(r["symbol"], date.fromisoformat(r["event_date"]), r["kind"], r["pct"], -r["id"])
                for r in c.execute("SELECT * FROM manual_events")]
    return sigs, evs


def review_queue():
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id,posted_at,text,note FROM raw_messages WHERE status='review' ORDER BY posted_at")]


def add_manual_event(symbol, d, kind, pct):
    with conn() as c:
        c.execute("INSERT INTO manual_events(symbol,event_date,kind,pct) VALUES(?,?,?,?)",
                  (symbol.upper(), d, kind, pct))
