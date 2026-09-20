# Ninety day runbook

## Phase 0, weeks 1 to 4: build while the domain warms

Daily, automatic:
- `collect` runs 06:00 IST, gathering signals against the target list

Weekly, automatic:
- `discover` runs Sunday, topping up `config/targets.yaml` from the YC mirror
  and pulling any published founder emails

Yours, once:
- Follow `docs/warmup-plan.md` from day one
- Run `discover` manually to seed the first few hundred companies
- Work through companies with no published founder email. Company site team
  pages and contact pages are the free route. Add them to `data/contacts.csv`
  and run the `import-contacts` workflow
- Ask Varun to sign off on the email template language before week five

Target by end of week four: 200 or more companies, 120 or more contacts, sixty
days of signal history, domain at full send rate.

## Phase 1, weeks 5 to 8: send and log

Daily:
- `queue` runs 08:30 IST and produces `drafts.md` as a workflow artifact
- You download it, review every draft, and send the approved ones from Brevo
- The Brevo webhook logs delivered, open, bounce and unsubscribe automatically
- You log `reply`, `positive_reply`, `meeting` and `opportunity` by hand in the
  Supabase table editor, because those require a human to read the reply

Weekly:
- `report` runs Monday. Read it. Change nothing yet.

## Phase 2, weeks 9 to 13: read and decide

- At 150 signal and 60 control sends the ledger stops saying HOLD
- Read the per signal table. Signals with zero positive replies across thirty
  or more sends get their weight cut in `config/signals.yaml`
- Change one thing at a time. Two changes in a week means the ledger cannot
  attribute the movement to either

## The decision

`make report` prints SCALE or DO NOT SCALE YET based on whether the signal arm
separates from control on positive replies at p below 0.05.

If SCALE: add sources, add a second client lens, keep the control arm running
at a lower share so you can detect decay.

If DO NOT SCALE: the answer is the signal set or the copy. Adding more sources
or more volume to a hypothesis that failed is how this category of project
burns a year. Kill it or rebuild the hypothesis, do not scale it.

## Things that will go wrong

- **Scheduled workflows stop after sixty days of repo inactivity.** Push a
  commit in month two. The `discover` workflow commits weekly, which covers
  you, but check it is running.
- **Supabase free tier pauses a project after a week of inactivity.** The
  daily collectors keep it awake. If you pause the project, unpause before the
  crons run.
- **crt.sh is slow and sometimes times out.** The collector is set to
  continue-on-error. A missed day is fine, the data is cumulative.
- **GitHub API rate limits** at 1000 requests an hour with the Actions token.
  Keep the github target list under about 60 orgs or split the run.
