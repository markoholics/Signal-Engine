"""Pull founder names and, where YC publishes them, founder emails.

YC company profiles are public pages. The yc-oss mirror exposes the same
fields, including a founders array. Where an email is published we take it as
published. Where it is not, we record the person with no email and leave
email_status as 'unverified', so the queue skips them until you supply one.

We do not guess or generate email addresses. A guessed address that bounces
damages the sending domain, and the ledger then measures your deliverability
rather than your signals.

Everything written here is business contact data at companies in the ICP,
stored with consent_basis 'legitimate_interest_b2b' and checked against the
suppression table before any send.
"""
import re, yaml, json
from pathlib import Path
from collectors.base import get
from core.db import conn, upsert_company

ALL = "https://yc-oss.github.io/api/companies/all.json"
CFG = Path(__file__).parent.parent / "config" / "targets.yaml"

SENIOR = [
    (re.compile(r"\b(founder|co[- ]?founder|ceo)\b", re.I), "founder"),
    (re.compile(r"\b(cto|chief technology)\b", re.I), "cto"),
    (re.compile(r"\b(vp eng|head of eng|engineering lead|vp of engineering)\b", re.I), "head_eng"),
]

def seniority_of(title):
    for rx, label in SENIOR:
        if rx.search(title or ""):
            return label
    return "other"

def run():
    cfg = yaml.safe_load(CFG.read_text())
    wanted = {c["domain"]: c.get("name") for c in cfg.get("companies", [])}
    data = get(ALL).json()

    added = no_email = 0
    with conn() as c, c.cursor() as cur:
        for comp in data:
            site = (comp.get("website") or "").lower()
            dom = next((d for d in wanted if d and d in site), None)
            if not dom:
                continue
            cid = upsert_company(c, dom, comp.get("name"))
            for f in comp.get("founders") or []:
                name = f.get("full_name") or f.get("name")
                title = f.get("title") or "Founder"
                email = (f.get("email") or "").strip().lower() or None
                if not name:
                    continue
                if not email:
                    no_email += 1
                    continue
                cur.execute(
                    """insert into person
                       (company_id, full_name, role_title, seniority, email, source)
                       values (%s,%s,%s,%s,%s,%s)
                       on conflict (email) do nothing""",
                    (cid, name, title, seniority_of(title), email,
                     "YC public company profile"),
                )
                added += 1
    print(f"imported {added} contacts with published emails")
    print(f"{no_email} founders found with no published email. "
          f"Source those manually from company site team or contact pages, "
          f"then add them to data/contacts.csv and run import-contacts.")

if __name__ == "__main__":
    run()
