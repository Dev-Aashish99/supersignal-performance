"""
engine.py - classification + stats. Pure functions, no I/O, fully testable.

Rules encoded (from Ravi's handoff doc + his corrections):
  * Entry must trigger; INVALID / no update after 45 days is dropped.
  * SL HIT            -> loss at stated % (counted)
  * TSL HIT  > 0%     -> win at stated % (counted)
  * TSL HIT  = 0%     -> breakeven, excluded
  * Manual exit       -> excluded
  * Target hit (T1+) and NOT exited by period end -> PROVISIONAL win at the
    LAST target % reported (counted, flagged provisional)
  * A trade is counted in the FIRST period (month or week) whose cut-off shows it
    as counted. So a prior-month trade whose first target hit lands this month is
    added to this month; it is never counted twice.
"""
from dataclasses import dataclass
from datetime import date, timedelta

TERMINAL = {"SL_HIT", "TSL_HIT", "INVALID", "MANUAL"}
COUNTED = {"WIN", "LOSS", "PROVISIONAL_WIN"}
INVALID_AFTER_DAYS = 45


@dataclass
class Signal:
    id: int
    symbol: str
    signal_date: date
    tag: str = ""
    entry: float = 0.0
    sl: float = 0.0
    target: float = 0.0


@dataclass
class Event:
    symbol: str
    event_date: date
    kind: str            # TARGET | SL_HIT | TSL_HIT | INVALID | MANUAL
    pct: float | None = None
    raw_id: int | None = None
    signal_id: int | None = None


# ---------- period helpers (month "2026-09", week "2026-W40") ----------
def bounds(label: str):
    if "W" in label:
        y, w = label.split("-W")
        start = date.fromisocalendar(int(y), int(w), 1)
        return start, start + timedelta(days=6)
    y, m = map(int, label.split("-"))
    start = date(y, m, 1)
    end = date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
    return start, end


def label_for(kind: str, d: date) -> str:
    if kind == "week":
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    return f"{d.year}-{d.month:02d}"


def next_label(label: str) -> str:
    _, end = bounds(label)
    return label_for("week" if "W" in label else "month", end + timedelta(days=1))


def kind_of(label: str) -> str:
    return "week" if "W" in label else "month"


# ---------- linking events to signals ----------
def link_events(signals, events):
    """Attach every event to a signal. Returns (events_by_signal, unmatched, ambiguous)."""
    by_sym = {}
    for s in sorted(signals, key=lambda s: (s.signal_date, s.id)):
        by_sym.setdefault(s.symbol, []).append(s)
    attached = {s.id: [] for s in signals}
    terminal_ids, unmatched, ambiguous = set(), [], []

    for ev in sorted(events, key=lambda e: (e.event_date, e.raw_id or 0)):
        cands = [s for s in by_sym.get(ev.symbol, [])
                 if s.signal_date <= ev.event_date and s.id not in terminal_ids]
        if not cands:
            unmatched.append(ev)
            continue
        if ev.kind == "INVALID":
            pool = [s for s in cands if not any(e.kind == "TARGET" for e in attached[s.id])] or cands
            sig = pool[-1]                      # newest un-triggered signal
        else:
            sig = cands[0]                      # oldest open signal (FIFO)
        if len(cands) > 1:
            ambiguous.append((ev, [c.signal_date for c in cands]))
        ev.signal_id = sig.id
        attached[sig.id].append(ev)
        if ev.kind in TERMINAL:
            terminal_ids.add(sig.id)
    return attached, unmatched, ambiguous


# ---------- state of one signal at a cut-off date ----------
def state_at(sig: Signal, evs, cutoff: date):
    evs = [e for e in evs if e.event_date <= cutoff]
    term = next((e for e in evs if e.kind in TERMINAL), None)
    targets = [e for e in evs if e.kind == "TARGET" and (term is None or e.event_date <= term.event_date)]
    pcts = [e.pct for e in targets if e.pct is not None]
    peak = max(pcts) if pcts else None
    last_t = pcts[-1] if pcts else None
    out = {"status": "OPEN", "l1": None, "l2": None, "peak": peak,
           "note": "", "last_event": evs[-1].event_date if evs else None}

    if term is not None:
        k, p = term.kind, term.pct
        if k == "INVALID":
            out.update(status="INVALID", note="entry never triggered")
        elif k == "MANUAL":
            out.update(status="MANUAL", note="manual exit, no clean classification")
        elif k == "SL_HIT":
            if p is None and sig.entry and sig.sl:
                p = round((sig.sl - sig.entry) / sig.entry * 100, 1)
            if p is None:
                out.update(status="REVIEW", note="SL hit but % missing")
            else:
                p = -abs(p)
                out.update(status="LOSS", l1=p, l2=p)
        elif k == "TSL_HIT":
            if p is None:
                out.update(status="REVIEW", note="TSL hit but % missing")
            elif p > 0:
                out.update(status="WIN", l1=p, l2=max(peak or p, p))
            elif p == 0:
                out.update(status="BREAKEVEN", l1=0.0, l2=peak,
                           note="TSL at cost, excluded")
            else:
                out.update(status="LOSS", l1=p, l2=p)
        out["exit_date"] = term.event_date
        return out

    if last_t is not None:
        out.update(status="PROVISIONAL_WIN", l1=last_t, l2=peak,
                   note="target hit, not exited - counted at last target %")
    elif not evs and (cutoff - sig.signal_date).days > INVALID_AFTER_DAYS:
        out.update(status="INVALID", note="no update after 45 days")
    return out


# ---------- stats ----------
def stats(rows, key="l1"):
    vals = [r[key] for r in rows if r.get(key) is not None]
    n = len(vals)
    w = sum(1 for v in vals if v > 0)
    l = sum(1 for v in vals if v < 0)
    tot = round(sum(vals), 2)
    return {"counted": n, "winners": w, "losers": l,
            "win_rate": round(w / n * 100, 1) if n else 0.0,
            "total": tot, "avg": round(tot / n, 2) if n else 0.0}


def build_report(signals, events, label: str):
    start, end = bounds(label)
    kind = kind_of(label)
    attached, unmatched, ambiguous = link_events(signals, events)
    sigs = [s for s in signals if s.signal_date <= end]

    rows, excluded, closing_already_counted = [], [], []
    for s in sigs:
        origin = label_for(kind, s.signal_date)
        # first period (origin..label) in which the trade is "counted"
        counted_in, cur = None, origin
        while cur <= label:
            st = state_at(s, attached[s.id], bounds(cur)[1])
            if st["status"] in COUNTED:
                counted_in = cur
                break
            cur = next_label(cur)
        now = state_at(s, attached[s.id], end)
        base = {"symbol": s.symbol, "signal_date": s.signal_date, "tag": s.tag,
                "entry": s.entry, "sl": s.sl, "target": s.target,
                "origin": origin, **now}

        if counted_in == label:
            base["kind"] = "new" if origin == label else "carry-in"
            rows.append(base)
        elif counted_in is not None and counted_in < label:
            ex = now.get("exit_date")
            if ex and start <= ex <= end:
                base["counted_in"] = counted_in
                closing_already_counted.append(base)
        elif origin == label:
            excluded.append(base)       # invalid / breakeven / manual / open / review
        elif now["status"] in ("BREAKEVEN", "MANUAL", "INVALID") and now.get("exit_date") \
                and start <= now["exit_date"] <= end:
            base["kind"] = "carry-in"
            excluded.append(base)

    new_rows = [r for r in rows if r["kind"] == "new"]
    closed = lambda rs: [r for r in rs if r["status"] != "PROVISIONAL_WIN"]
    # L2 view: also counts breakeven-after-target trades at their peak
    l2_rows = rows + [r for r in excluded if r["status"] == "BREAKEVEN" and (r["l2"] or 0) > 0]

    return {
        "label": label, "start": start, "end": end,
        "rows": sorted(rows, key=lambda r: (r["signal_date"], r["symbol"])),
        "excluded": sorted(excluded, key=lambda r: (r["signal_date"], r["symbol"])),
        "closing_already_counted": closing_already_counted,
        "stats": {
            "new_incl_provisional": stats(new_rows),
            "new_closed_only": stats(closed(new_rows)),
            "all_incl_provisional": stats(rows),
            "all_closed_only": stats(closed(rows)),
            "l2_all": stats(l2_rows, "l2"),
        },
        "unmatched_events": unmatched,
        "ambiguous": ambiguous,
        "review": [r for r in rows + excluded if r["status"] == "REVIEW"],
    }
