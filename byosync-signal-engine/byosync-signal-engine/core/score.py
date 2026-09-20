"""Scoring brain, phase one: hand weighted signals with exponential decay.

Phase two (after roughly 500 labelled outcomes in the ledger) swaps
`weights_for` to read learned coefficients. The interface does not change,
which is the whole point of putting it behind a function.
"""
import math, yaml, datetime as dt
from pathlib import Path
from core.db import conn

CFG = yaml.safe_load((Path(__file__).parent.parent / "config" / "signals.yaml").read_text())

def weights_for(client="byosync"):
    return CFG["byosync_weights"]

def decay(observed_at, half_life_days=30, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    age = (now - observed_at).total_seconds() / 86400.0
    return 0.5 ** (age / half_life_days)

def squash(x):
    """Logistic. Stops one loud signal from carrying an account on its own."""
    return 1 / (1 + math.exp(-(x - 1.4) * 1.9))

def score_company(rows, weights, half_life=30):
    """rows: list of (signal_type, strength, observed_at). Returns score, contributions."""
    best = {}
    for stype, strength, observed_at in rows:
        v = float(strength) * weights.get(stype, 0.0) * decay(observed_at, half_life)
        if v > best.get(stype, 0):
            best[stype] = v
    raw = sum(best.values())
    present = set(best)
    fired = []
    for combo in CFG.get("combos", []):
        if set(combo["requires"]).issubset(present):
            raw += combo["bonus"]
            fired.append(combo["name"])
    return squash(raw), best, fired

def rank(client="byosync", limit=50, half_life=30):
    w = weights_for(client)
    out = []
    with conn() as c, c.cursor() as cur:
        cur.execute("""select id, domain, name, coalesce(icp_fit, 0) from company""")
        companies = cur.fetchall()
        for cid, domain, name, fit in companies:
            cur.execute("""select signal_type, strength, observed_at
                           from signal_event
                           where company_id = %s
                             and observed_at > now() - interval '120 days'""", (cid,))
            rows = cur.fetchall()
            if not rows:
                continue
            s, contrib, combos = score_company(rows, w, half_life)
            final = s * (0.4 + 0.6 * float(fit))   # ICP fit gates, never alone decides
            out.append({
                "company_id": cid, "domain": domain, "name": name,
                "score": round(final, 4), "icp_fit": float(fit),
                "top_signals": sorted(contrib.items(), key=lambda x: -x[1])[:4],
                "combos": combos,
            })
    return sorted(out, key=lambda r: -r["score"])[:limit]

if __name__ == "__main__":
    for r in rank():
        print(f"{r['score']:.3f}  {r['domain']:<32} {[s for s,_ in r['top_signals']]} {r['combos']}")
