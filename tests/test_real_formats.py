"""Messages copied EXACTLY from the V13 Apps Script builders (buildTradeAlertMessage_ / buildUpdateMessage)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from msgparser import parse_message

sig = ("#PULLBACK\nREDINGTON\nBUY ABOVE: 367\nSL: 356 (DAY-CLOSING BASIS)\nTGT: 386\nHolding Period: 30 days\n\n"
       "Target: +5% | Stop Loss: -3%\n\nThe stock has taken a short pause after a strong trend and could continue its upward move if it breaks above the trigger level.")
k, r = parse_message(sig, [])
assert k == "signal" and (r["symbol"], r["tag"], r["entry"], r["sl"], r["target"], r["hold_days"]) == ("REDINGTON", "PULLBACK", 367.0, 356.0, 386.0, 30), r

sig2 = "#MOMENTUM\nBAJAJ_AUTO\nBUY ABOVE: 11,884\nSL: 11646 (DAY-CLOSING BASIS)\nTGT: 12359\nHolding Period: 30 days"
k, r = parse_message(sig2, []); assert k == "signal" and r["symbol"] == "BAJAJ_AUTO" and r["entry"] == 11884.0, r

k, r = parse_message("#INTRADAY\nSBIN\nBUY ABOVE: 800\nSL: 790 (DAY-CLOSING BASIS)\nTGT: 815", [])
assert k == "ignored", (k, r)

known = ["REDINGTON", "BAJAJ_AUTO", "OFSS"]
cases = [
 ("OFSS | SL HIT.\nLoss booked - 2%.",                         ("SL_HIT", 2.0)),
 ("BAJAJ_AUTO | SL HIT.\nLoss booked - 2.9%.",                 ("SL_HIT", 2.9)),
 ("REDINGTON | TSL HIT.\n5.2% booked.",                        ("TSL_HIT", 5.2)),
 ("REDINGTON | TSL HIT.\nNo profit or loss booked.",           ("TSL_HIT", 0.0)),
 ("OFSS | Trade invalid.\nEntry didn't trigger.",              ("INVALID", None)),
 ("REDINGTON target achieved.\n\nCurrent gains ~9%.\n\nYou can either book profits here or trail your SL to 380 and mark the next target at 400.", ("TARGET", 9.0)),
 ("BAJAJ AUTO target achieved.\n\nCurrent gains ~4.1%.\n\nYou can either book profits here or trail your SL to CTC and mark the next target at 12100.", ("TARGET", 4.1)),
]
for text, (kind, pct) in cases:
    k, r = parse_message(text, known)
    assert k == "events" and r[0]["kind"] == kind and r[0]["pct"] == pct, (text, k, r)
print("REAL FORMAT PARSING OK")
