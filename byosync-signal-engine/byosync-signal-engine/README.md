# ByoSync signal engine, narrow version

One client, five sources, 90 days, a control arm and a ledger.

## Running cost

| Component | Choice | Cost |
|---|---|---|
| Database | Supabase free tier, or Postgres on a 5 USD VPS | 0 to 5 USD/mo |
| Scheduler | cron on the same box, or GitHub Actions free minutes | 0 |
| Collectors | ATS public APIs, crt.sh, GitHub API, RSS, HN Algolia | 0 |
| Contact data | Apollo organisation lookup (people search is blocked on the current plan), plus manual founder lookup from company sites | 0 |
| Sending | Brevo free tier for the first weeks, then a paid plan | 0 to 25 USD/mo |
| Domain and mailboxes | One secondary domain, two mailboxes, warmed | roughly 15 USD/mo |
| LLM drafting | Templates first. Local model via Ollama if needed | 0 |

Everything except sending infrastructure is free. Do not try to make sending
free. Cold email from an unwarmed free mailbox lands in spam and the
experiment measures deliverability instead of signal quality.

## Setup

    cp .env.example .env          # set DATABASE_URL
    make install
    make db
    # fill config/targets.yaml with 150 to 300 ICP companies
    make collect
    make rank

## Daily loop

    make collect      # cron, 06:00 IST
    make queue        # prints drafts for Rahman review
    # approve, send via Brevo, then log outcomes as they land
    python -m outreach.ledger --log <send_id> reply

## The gate

`make report` prints both arms side by side with a two proportion z test and
refuses to declare a winner below 150 signal and 60 control sends. If the
signal arm does not separate from control on positive replies, the answer is
to fix the signal set, not to add sources or clients.
