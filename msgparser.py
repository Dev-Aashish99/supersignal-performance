"""
parser.py - turns raw Telegram text into a signal or outcome event(s).

IMPORTANT: patterns here are written from the handoff doc's description of your
message formats, not from real samples. Every raw message is stored untouched, so
if a pattern misses, fix it here and run  POST /rebuild  - nothing is lost.
Anything not understood lands in the review queue instead of being guessed.
"""
import re

NUM = r"([\d,]+(?:\.\d+)?)(?!\s*%|[\d.])"
CUR = r"(?:₹|Rs\.?|INR)?\s*"
STOP = {"BUY", "ABOVE", "SL", "TGT", "TARGET", "STOP", "LOSS", "DAY", "CLOSING", "BASIS",
        "PULLBACK", "MOMENTUM", "REVERSAL", "HOLDING", "PERIOD", "DAYS", "NEW", "SIGNAL",
        "TRADE", "ALERT", "POSITIONAL", "ENTRY", "CMP", "RISK", "NOTE", "FOR", "AND", "THE"}


def _num(s):
    return float(s.replace(",", ""))


def parse_signal(text: str):
    if not re.search(r"BUY\s*ABOVE", text, re.I):
        return None
    if re.search(r"#\s*INTRADAY", text, re.I):
        return None          # intraday calls are not part of the monthly tracker
    t = text.replace("\u200b", "")
    tag = re.search(r"#\s*(PULLBACK|MOMENTUM|REVERSAL)", t, re.I)
    entry = re.search(r"BUY\s*ABOVE\s*[:\-@]?\s*" + CUR + NUM, t, re.I)
    sl = re.search(r"(?:\bSL\b|STOP\s*LOSS)\s*[:\-@]?\s*" + CUR + NUM, t, re.I)
    tgt = re.search(r"(?:\bTGT\b|\bTARGET\b)\s*[:\-@]?\s*" + CUR + NUM, t, re.I)
    hold = re.search(r"(\d+)\s*(?:DAYS?|D)\b", t, re.I)

    # real format: line 1 = "#PULLBACK", line 2 = ticker
    lines = [l.strip() for l in t.strip().splitlines() if l.strip()]
    symbol = None
    if len(lines) >= 2 and re.fullmatch(r"#\w+", lines[0]) and re.fullmatch(r"[A-Za-z0-9&_\-]{2,}", lines[1]):
        symbol = lines[1]
    sym = re.search(r"(?:STOCK|SYMBOL|SCRIP|NAME)\s*[:\-]\s*#?([A-Za-z0-9&_\-]+)", t, re.I)
    symbol = symbol or (sym.group(1) if sym else None)
    if not symbol:
        head = re.split(r"BUY\s*ABOVE", t, flags=re.I)[0]
        for w in re.findall(r"#?([A-Z][A-Z0-9&_\-]{2,})", head):
            if w not in STOP:
                symbol = w
                break
    if not (symbol and entry and sl):
        return {"_incomplete": True, "reason": "could not read symbol/entry/SL"}
    return {"symbol": symbol.upper(), "tag": tag.group(1).upper() if tag else "",
            "entry": _num(entry.group(1)), "sl": _num(sl.group(1)),
            "target": _num(tgt.group(1)) if tgt else 0.0,
            "hold_days": int(hold.group(1)) if hold else 30}


def _sym_pattern(sym: str):
    parts = [re.escape(p) for p in re.split(r"[_&\-]", sym) if p]
    return r"(?<![A-Z0-9])" + r"[\s_&\-]*".join(parts) + r"(?![A-Z0-9])"


def find_symbols(text: str, known):
    up = text.upper()
    return [s for s in known if re.search(_sym_pattern(s), up)]


def _pct(text, prefer=None):
    if prefer:
        m = re.search(prefer + r"[^\d\-+%]{0,25}~?\s*([+-]?\d+(?:\.\d+)?)\s*%", text, re.I)
        if m:
            return float(m.group(1))
    m = re.search(r"~?\s*([+-]?\d+(?:\.\d+)?)\s*%", text)
    return float(m.group(1)) if m else None


def parse_outcome(text: str):
    """Return (kind, pct) or None."""
    t = text
    if re.search(r"trade\s*invalid|entry\s*didn.?t\s*trigger", t, re.I):
        return "INVALID", None
    if re.search(r"\bTSL\s*HIT", t, re.I):
        p = _pct(t, r"(?:profit|booked|gain)")
        if p is None and re.search(r"no\s*profit|no\s*loss|at\s*cost|breakeven|CTC", t, re.I):
            p = 0.0
        return "TSL_HIT", p
    if re.search(r"\bSL\s*HIT", t, re.I):
        return "SL_HIT", _pct(t, r"(?:loss)")
    if re.search(r"target\s*(?:achieved|hit|done)", t, re.I):
        return "TARGET", _pct(t, r"(?:gain|gains|profit|current|up)")
    if re.search(r"square[d]?\s*off|exit\s*at\s*LTP", t, re.I):
        return "MANUAL", None
    return None


def parse_message(text: str, known_symbols):
    """-> ('signal', dict) | ('events', [dict]) | ('review', reason) | ('ignored', '')"""
    if not text or not text.strip():
        return "ignored", ""
    sig = parse_signal(text)
    if sig is not None:
        if sig.get("_incomplete"):
            return "review", sig["reason"]
        return "signal", sig
    out = parse_outcome(text)
    if out is None:
        return "ignored", ""
    kind, pct = out
    syms = find_symbols(text, known_symbols)
    if not syms:
        return "review", f"{kind} message but no known stock symbol found"
    return "events", [{"symbol": s, "kind": kind, "pct": pct} for s in syms]
