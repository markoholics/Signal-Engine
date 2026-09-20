# Sending infrastructure: the four week warm up

Brevo account exists but the domain is not warmed. This is the critical path.
Nothing else in the project matters if the mail lands in spam, because the
experiment would then measure deliverability rather than signal quality.

Start this today. It runs in parallel with everything else.

## Week 0: set up, before any sending

1. Buy a **secondary domain**, not markoholics.com. Something like
   markoholics-mail.com or getmarkoholics.com. If a warm up goes wrong you
   burn the secondary, not your primary.
2. Create two mailboxes on it. Two, not one. Volume per mailbox stays low.
3. Authenticate all three records in Brevo's domain settings:
   - **SPF** so Brevo is allowed to send as you
   - **DKIM** so the mail is cryptographically signed
   - **DMARC**, start at `p=none`, move to `p=quarantine` after week four
   Brevo will not let you send properly without the first two. Do all three.
4. Set up a custom tracking domain in Brevo so links do not point at a shared
   Brevo domain that other senders may have damaged.

## Weeks 1 to 4: the ramp

Per mailbox, per working day:

| Week | Emails per mailbox per day | What you send |
|---|---|---|
| 1 | 5 | Real conversations. Colleagues, past clients, Varun, anyone who will reply |
| 2 | 10 | Mix of real conversations and the first genuine prospects |
| 3 | 15 | Mostly prospects |
| 4 | 25 | Full rate, experiment begins |

Rules for the ramp:

- Replies are the signal mailbox providers care about most. Ask the people in
  week one to actually reply, not just receive.
- Never send the same body to more than a handful of addresses in these weeks.
- Keep bounce rate under 2 percent and spam complaints under 0.1 percent.
  Above that, stop and go back a week.
- No links in week one. Add one link from week two.
- Send at a human pace on working days only. A burst of 25 at 09:00 sharp
  reads as automation.

## What this means for the ninety days

The experiment clock starts when week four ends, not today. Plan for:

- **Weeks 1 to 4**: warm up, target discovery, contact building, collectors
  running and accumulating signal history. No cold sends.
- **Weeks 5 to 13**: the experiment. Two mailboxes at 25 a day, five working
  days, is 250 sends a week. The ledger's decision gate needs 150 signal and
  60 control sends, which you clear inside the first two weeks of sending.

Signal history accumulating during warm up is a genuine advantage. By the time
you send, accounts have sixty days of observed behaviour behind them rather
than a single snapshot.

## Before the first send, confirm all of these

- Working unsubscribe link in every email
- A real physical postal address in the footer
- Suppression table live and checked by `outreach/queue.py`
- Every draft reviewed by Rahman, `send.approved_by` set
- Varun has signed off on the positioning language in the templates
