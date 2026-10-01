"""
Backfill from a Telegram Desktop export:
  Telegram Desktop -> test channel -> menu -> Export chat history -> JSON (untick media)
  python import_telegram_export.py path/to/result.json
Safe to re-run: messages are de-duplicated on their Telegram message id.
"""
import json, sys
import db


def flat(text):
    if isinstance(text, str):
        return text
    return "".join(p if isinstance(p, str) else p.get("text", "") for p in text)


def import_data(data):
    """data = parsed Telegram Desktop export. Returns number of messages stored."""
    db.init()
    n = 0
    for m in data.get("messages", []):
        if m.get("type") != "message":
            continue
        txt = flat(m.get("text", "")).strip()
        if txt:
            db.add_raw("telegram", int(m["id"]), m["date"][:19], txt)
            n += 1
    db.rebuild()
    return n


def main(path):
    n = import_data(json.load(open(path, encoding="utf-8")))
    print(f"imported {n} messages; run the app and open /?period=YYYY-MM")


if __name__ == "__main__":
    main(sys.argv[1])
