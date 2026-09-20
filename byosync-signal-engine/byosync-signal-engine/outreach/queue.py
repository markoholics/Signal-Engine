"""Builds the daily send queue and assigns the experiment arm.

The experiment is the whole point of the 90 days. Every day the engine takes
the ranked accounts and randomly assigns each to one of two arms:

  signal  : contacted now, with the signal named in the opening line
  control : contacted now, same ICP, same sequence, no signal reference

Control is not a cold list of worse accounts. It is the same accounts, sent
generic copy. That isolates one variable: does the signal earn the reply, or
does the ICP alone? A control arm of worse accounts would prove nothing and
would flatter the result, which is the usual way this test gets faked.
"""
import random, json, datetime as dt
from core.db import conn, is_suppressed
from core.score import rank

CONTROL_SHARE = 0.30     # 30 percent to control. Enough power, low revenue cost.
DAILY_CAP = 25           # per sending mailbox. Deliverability, not ambition.

def build(client="byosync", cap=DAILY_CAP, seed=None):
    rng = random.Random(seed)
    queued = []
    with conn() as c, c.cursor() as cur:
        cur.execute("select min_score from client_lens where client=%s", (client,))
        row = cur.fetchone()
        min_score = float(row[0]) if row else 0.45
        for r in rank(client=client, limit=cap * 4):
            if r["score"] < min_score:
                continue
            cur.execute("""select id, email, full_name, role_title from person
                           where company_id=%s and suppressed=false
                             and email_status in ('valid','unverified')
                           order by case seniority when 'founder' then 0
                                                   when 'cto' then 1
                                                   when 'head_eng' then 2
                                                   else 3 end
                           limit 1""", (r["company_id"],))
            p = cur.fetchone()
            if not p:
                continue
            pid, email, name, title = p
            if is_suppressed(c, email=email, domain=r["domain"]):
                continue
            cur.execute("""select 1 from send
                           where person_id=%s and created_at > now() - interval '90 days'""", (pid,))
            if cur.fetchone():
                continue
            arm = "control" if rng.random() < CONTROL_SHARE else "signal"
            cur.execute("""insert into send
                (client, person_id, company_id, arm, score_at_send, signals_at_send)
                values (%s,%s,%s,%s,%s,%s::jsonb) returning id""",
                (client, pid, r["company_id"], arm, r["score"],
                 json.dumps([s for s, _ in r["top_signals"]])))
            sid = cur.fetchone()[0]
            queued.append({"send_id": sid, "arm": arm, "domain": r["domain"],
                           "person": name, "title": title, "email": email,
                           "score": r["score"], "signals": [s for s, _ in r["top_signals"]],
                           "combos": r["combos"]})
            if len(queued) >= cap:
                break
    return queued

if __name__ == "__main__":
    q = build()
    print(f"{len(q)} queued  ({sum(1 for x in q if x['arm']=='signal')} signal / "
          f"{sum(1 for x in q if x['arm']=='control')} control)")
    for x in q:
        print(f"  [{x['arm']:<7}] {x['score']:.3f} {x['domain']:<28} {x['signals']}")
