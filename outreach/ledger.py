"""The outcome ledger and the 90 day readout.

This decides whether the engine scales or dies. It reports both arms side by
side with a two proportion z test, and it refuses to call a winner before the
sample can support one. Reporting a 40 percent lift on 18 sends is how these
projects get funded and then fail.
"""
import math, argparse, datetime as dt
from core.db import conn

STAGES = ["delivered", "reply", "positive_reply", "meeting", "opportunity", "won"]

def log(send_id, outcome_type, notes=None, source="manual"):
    with conn() as c, c.cursor() as cur:
        cur.execute("""insert into outcome (send_id, outcome_type, notes, source)
                       values (%s,%s,%s,%s)""", (send_id, outcome_type, notes, source))
        if outcome_type in ("unsubscribe", "bounce"):
            cur.execute("""insert into suppression (email, reason)
                           select p.email, %s from send s join person p on p.id = s.person_id
                           where s.id = %s
                           on conflict do nothing""", (outcome_type, send_id))

def two_prop_z(x1, n1, x2, n2):
    if min(n1, n2) == 0:
        return None, None
    p1, p2 = x1 / n1, x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return None, None
    z = (p1 - p2) / se
    pval = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return z, pval

def report(client="byosync"):
    with conn() as c, c.cursor() as cur:
        cur.execute("""select arm, count(*) from send
                       where client=%s and sent_at is not null group by arm""", (client,))
        totals = dict(cur.fetchall())
        rows = {}
        for stage in STAGES:
            cur.execute("""select s.arm, count(distinct s.id)
                           from send s join outcome o on o.send_id = s.id
                           where s.client=%s and o.outcome_type=%s group by s.arm""",
                        (client, stage))
            rows[stage] = dict(cur.fetchall())

        # Which individual signals actually convert. This is the learned asset.
        cur.execute("""select sig, count(*) filter (where replied) as replies, count(*) as sends
                       from (
                         select jsonb_array_elements_text(s.signals_at_send) as sig,
                                exists(select 1 from outcome o where o.send_id=s.id
                                       and o.outcome_type='positive_reply') as replied
                         from send s where s.client=%s and s.arm='signal' and s.sent_at is not null
                       ) t group by sig order by 3 desc""", (client,))
        per_signal = cur.fetchall()

    ns, nc = totals.get("signal", 0), totals.get("control", 0)
    print(f"\nByoSync signal engine readout   {dt.date.today()}")
    print(f"Sends: signal {ns}, control {nc}\n")
    print(f"{'stage':<16}{'signal':>16}{'control':>16}{'lift':>10}{'p':>9}")
    for stage in STAGES:
        xs, xc = rows[stage].get("signal", 0), rows[stage].get("control", 0)
        rs = xs / ns if ns else 0
        rc = xc / nc if nc else 0
        _, p = two_prop_z(xs, ns, xc, nc)
        lift = f"{(rs/rc - 1)*100:+.0f}%" if rc else "n/a"
        pstr = f"{p:.3f}" if p is not None else "n/a"
        print(f"{stage:<16}{xs:>6} ({rs*100:5.1f}%){xc:>6} ({rc*100:5.1f}%){lift:>10}{pstr:>9}")

    print("\nPer signal positive reply rate")
    for sig, replies, sends in per_signal:
        print(f"  {sig:<28} {replies}/{sends}" + (f"  {replies/sends*100:5.1f}%" if sends else ""))

    print("\nDecision gate")
    if ns < 150 or nc < 60:
        print("  HOLD. Need roughly 150 signal and 60 control sends before reading a result.")
    else:
        xs, xc = rows["positive_reply"].get("signal", 0), rows["positive_reply"].get("control", 0)
        _, p = two_prop_z(xs, ns, xc, nc)
        rs, rc = xs/ns, xc/nc if nc else 0
        if p is not None and p < 0.05 and rs > rc:
            print(f"  SCALE. Signal arm beats control on positive replies, p={p:.3f}.")
        else:
            print("  DO NOT SCALE YET. No significant separation. Fix the signal set or the copy, not the volume.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", nargs=2, metavar=("SEND_ID", "OUTCOME"))
    ap.add_argument("--notes", default=None)
    a = ap.parse_args()
    if a.log:
        log(int(a.log[0]), a.log[1], a.notes)
        print("logged")
    else:
        report()
