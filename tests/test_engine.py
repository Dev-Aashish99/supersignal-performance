"""Replays Ravi's September 2026 report through the engine and checks the headline numbers."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from datetime import date
from engine import Signal, Event, build_report

D = lambda d, m=9: date(2026, m, d)
S, E = [], []
n = 0

def sig(day, sym, month=9):
    global n; n += 1
    S.append(Signal(n, sym, D(day, month)))

def ev(sym, day, kind, pct=None, month=9):
    E.append(Event(sym, D(day, month), kind, pct, len(E) + 1))

# (signal day, symbol, [(day, kind, pct), ...])
T = [
 (1,"THYROCARE",[(30,"INVALID",None)]),
 (3,"REDINGTON",[(9,"TARGET",9),(15,"TSL_HIT",5.2)]),
 (3,"OFSS",[(7,"SL_HIT",-2)]),
 (3,"LAURUSLABS",[(11,"TARGET",5),(24,"TARGET",9)]),
 (3,"AEGISLOG",[(8,"TARGET",9),(10,"TSL_HIT",5)]),
 (4,"KTKBANK",[(15,"MANUAL",None)]),
 (4,"APARINDS",[(15,"SL_HIT",-3)]),
 (4,"PAYTM",[(20,"TARGET",10),(25,"TSL_HIT",6)]),
 (7,"ELGIEQUIP",[(9,"SL_HIT",-3)]),
 (7,"AUROPHARMA",[]),
 (8,"PRICOLLTD",[(30,"INVALID",None)]),
 (8,"RBLBANK",[(15,"SL_HIT",-2.9)]),
 (8,"FEDERALBNK",[(17,"SL_HIT",-2.3)]),
 (8,"DEEPINDS",[(15,"MANUAL",None)]),
 (8,"PFIZER",[(9,"SL_HIT",-1)]),
 (9,"KARURVYSYA",[(10,"SL_HIT",-2)]),
 (9,"BAJAJ_AUTO",[(18,"SL_HIT",-2)]),
 (9,"MEDANTA",[(20,"TARGET",6),(28,"TSL_HIT",0)]),
 (9,"HAPPYFORGE",[(11,"SL_HIT",-2)]),
 (9,"TDPOWERSYS",[(9,"SL_HIT",-3)]),
 (11,"RAYMOND",[(14,"TARGET",26),(16,"TSL_HIT",17.8)]),
 (17,"AVALON",[(20,"TARGET",9),(24,"TSL_HIT",5)]),
 (17,"ATHERENERG",[(23,"SL_HIT",-3.2)]),
 (18,"HAPPYFORGE",[(30,"INVALID",None)]),
 (18,"ETERNAL",[]),
 (21,"ARVIND",[(21,"SL_HIT",-2.5)]),
 (21,"QUESS",[(25,"SL_HIT",-2.8)]),
 (22,"DIVISLAB",[]),
 (22,"SPLPETRO",[(29,"SL_HIT",-3.3)]),
 (22,"SOLARINDS",[(24,"TARGET",4),(28,"TSL_HIT",0)]),
 (22,"SUNDROP",[(22,"TARGET",4)]),
 (22,"SYRMA",[(24,"SL_HIT",-3.5)]),
 (22,"ENGINERSIN",[(22,"TARGET",4.1),(25,"TARGET",8)]),
 (23,"LUMAXTECH",[(23,"SL_HIT",-3)]),
 (23,"APLAPOLLO",[]),
 (23,"SAILIFE",[(28,"SL_HIT",-2.5)]),
 (23,"CEATLTD",[(28,"SL_HIT",-2)]),
 (23,"CYIENT",[(29,"SL_HIT",-2)]),
]
for day, sym, evs in T:
    sig(day, sym)
    for d, k, p in evs:
        ev(sym, d, k, p)

# August carry-overs
sig(14, "CAPLIPOINT", 8); ev("CAPLIPOINT", 25, "TARGET", 5, 8); ev("CAPLIPOINT", 15, "TSL_HIT", 6.2)
sig(17, "ASAHIINDIA", 8); ev("ASAHIINDIA", 15, "TARGET", 5)

r = build_report(S, E, "2026-09")
st = r["stats"]
print("NEW incl. provisional :", st["new_incl_provisional"])
print("NEW closed only       :", st["new_closed_only"])
print("ALL (with carry-in)   :", st["all_incl_provisional"])
print("ALL closed only       :", st["all_closed_only"])
print("L2                    :", st["l2_all"])
print("carry-ins:", [x["symbol"] for x in r["rows"] if x["kind"] == "carry-in"])
print("already counted earlier, closing now:", [(x["symbol"], x["counted_in"]) for x in r["closing_already_counted"]])
print("excluded:", [(x["symbol"], x["status"]) for x in r["excluded"]])

a = st["new_incl_provisional"]
assert (a["counted"], a["winners"], a["losers"], a["total"], a["win_rate"], a["avg"]) == (27, 8, 19, 12.0, 29.6, 0.44), a
c = st["new_closed_only"]
assert (c["counted"], c["winners"], c["losers"], c["total"], c["win_rate"], c["avg"]) == (24, 5, 19, -9.0, 20.8, -0.38), c
b = st["all_incl_provisional"]
assert (b["counted"], b["winners"], b["total"]) == (28, 9, 17.0), b
assert [x["symbol"] for x in r["rows"] if x["kind"] == "carry-in"] == ["ASAHIINDIA"]
assert [x["symbol"] for x in r["closing_already_counted"]] == ["CAPLIPOINT"]
# Aug report must already contain CAPLIPOINT
assert "CAPLIPOINT" in [x["symbol"] for x in build_report(S, E, "2026-08")["rows"]]
# Oct: SUNDROP later exits -> must NOT be counted again
E.append(Event("SUNDROP", date(2026,10,6), "TSL_HIT", 0.0, 999))
o = build_report(S, E, "2026-10")
assert "SUNDROP" not in [x["symbol"] for x in o["rows"]]
assert "SUNDROP" in [x["symbol"] for x in o["closing_already_counted"]]
print("ALL TESTS PASSED")
