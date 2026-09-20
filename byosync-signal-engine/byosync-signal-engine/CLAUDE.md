# CLAUDE.md

Context for Claude Code working in this repository.

## What this is

A 90 day experiment, not a product. One client (ByoSync), five signal sources,
a randomised control arm, and an outcome ledger that decides whether the
approach scales. Everything in here should stay small enough to delete.

## The one question this repo answers

Do emails that reference a real, recent, public signal about a company earn
more positive replies than the same sequence sent to the same quality of
account with no signal reference?

Any change that makes that question harder to answer is a regression, however
clever it is. In particular: never let the control arm drift to lower quality
accounts, never let signal arm copy get more polished than control arm copy,
and never remove the randomised assignment in `outreach/queue.py`.

## Client context

ByoSync (Kavion Intelligence Pvt Ltd) sells a continuous security and
compliance engineering layer to Indian AI native SaaS companies and technology
MSMEs. ICP: founders, CTOs and heads of engineering, 4 to 100 employees, live
product handling sensitive customer data through two or more integrations, no
dedicated security team.

Locked brand lines, verbatim only, never paraphrased:
- "Find the leak. Fix the flow. Keep the proof."
- "Security cannot be an afterthought. Compliance cannot be an aftermath."
- "AI proposes. Humans approve. Deterministic runtime enforces."

## Copy rules, enforced in code

`outreach/draft.py` blocks a draft rather than sending it if it contains any
of these. Do not weaken the checks.

- No em dashes or en dashes anywhere.
- No competitor names (Vanta, Sprinto, Drata).
- No 24/7 or round the clock monitoring claims.
- No biometric, face authentication or KYC language. That is prior product
  direction and is prohibited.
- No implied government affiliation.
- No fabricated or unverified statistics, no rounded figures.
- No standalone "compliance" as a headline noun.
- Evidence based urgency, never fear based.

Two gate approval: Rahman reviews every draft before it sends. Varun Khatri
holds final sign off on positioning and anything public facing. The engine
never sends unapproved copy. `send.approved_by` must be set before dispatch.

## Legal and ethical boundaries, non negotiable

- Public sources only. ATS boards, certificate transparency logs, GitHub public
  metadata, RSS, Hacker News and Product Hunt. All of these publish openly.
- No LinkedIn scraping. It breaches their terms and gets accounts banned.
- No reading anyone's personal email or social accounts.
- No vulnerability probing, port scanning, secret hunting or any activity that
  resembles reconnaissance of a weakness. GitHub collection reads dependency
  names and commit counts, nothing else. Selling security while probing
  someone's infrastructure uninvited would end the business.
- Company level signals only. Person level behavioural tracking is out.
- Global suppression table is checked before every send. One touch per person
  per 90 days, enforced in `outreach/queue.py`.
- Every outbound email carries a working unsubscribe and a physical address.
  DPDP and Indian IT rules apply; so does CAN-SPAM for any US recipient.

## Architecture

```
collectors/   five sources, each idempotent via dedupe_key
core/db.py    thin psycopg layer
core/fit.py   structural ICP fit, slow moving, 0..1
core/score.py behavioural score, fast moving, decay plus combos, 0..1
outreach/     queue (arm assignment), draft (copy plus guardrails), ledger
sql/schema.sql
config/signals.yaml   taxonomy, weights, combo hypotheses
config/targets.yaml   seed company list
```

Final priority is `score * (0.4 + 0.6 * icp_fit)`. Fit gates, it never decides
alone. Score decays with a 30 day half life so a six month old funding round
stops pretending to be news.

## Phasing

- Days 1 to 30: collectors running daily, seed list of 150 to 300 companies,
  manual outcome logging, sends capped at 25 per mailbox per day.
- Days 31 to 60: first readout, prune signals with zero positive replies,
  adjust weights by hand and write down why.
- Days 61 to 90: run `make report`. The decision gate is in `ledger.py` and it
  refuses to call a winner below 150 signal and 60 control sends.

## When adding a signal

1. Add it to `config/signals.yaml` with a strength, a weight and a written
   hypothesis about why it predicts buying.
2. Emit it from a collector with a stable `dedupe_key`.
3. Do not touch the weights of existing signals in the same change. One
   variable at a time or the ledger cannot attribute anything.

## Commands

    make install
    make db
    make collect
    make rank
    make queue
    make report
    python -m outreach.ledger --log 42 positive_reply --notes "asked for pricing"
