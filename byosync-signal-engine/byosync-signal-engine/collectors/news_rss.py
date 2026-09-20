"""Source 4: funding and company news via free RSS.

Google News RSS plus Indian startup press feeds. No key, no quota. We match
headlines against the target list and against generic India AI SaaS funding
queries so the engine also discovers companies we had not listed.
"""
import re, json, yaml, datetime as dt
from pathlib import Path
import feedparser
from collectors.base import dedupe
from core.db import conn, upsert_company, insert_signal

FUNDING = re.compile(r"\b(raises|raised|funding|seed round|pre-series|series a|bags|secures)\b", re.I)
ENTERPRISE = re.compile(r"\b(partners with|selected by|wins|deploys at|onboards)\b.*\b(bank|insurer|insurance|hospital|healthcare|government|nbfc)\b", re.I)
LEADER = re.compile(r"\b(appoints|joins as|named)\b.*\b(cto|vp engineering|head of engineering|chief technology)\b", re.I)

FEEDS = [
    "https://news.google.com/rss/search?q=india+AI+SaaS+startup+raises+seed&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=india+AI+startup+%22series+A%22&hl=en-IN&gl=IN&ceid=IN:en",
    "https://inc42.com/feed/",
    "https://yourstory.com/feed",
]

def domain_from(entry, targets):
    blob = f"{entry.get('title','')} {entry.get('summary','')}".lower()
    for t in targets:
        nm = (t.get("name") or t["domain"].split(".")[0]).lower()
        if len(nm) > 3 and nm in blob:
            return t["domain"], t.get("name")
    return None, None

def run(targets, extra_feeds=None):
    now = dt.datetime.now(dt.timezone.utc)
    feeds = FEEDS + (extra_feeds or [])
    with conn() as c:
        for url in feeds:
            d = feedparser.parse(url)
            for e in d.entries[:60]:
                dom, name = domain_from(e, targets)
                if not dom:
                    continue
                title = e.get("title", "")
                try:
                    obs = dt.datetime(*e.published_parsed[:6], tzinfo=dt.timezone.utc)
                except Exception:
                    obs = now
                cid = upsert_company(c, dom, name)
                emit = []
                if FUNDING.search(title):    emit.append(("funding_round", 0.75))
                if ENTERPRISE.search(title): emit.append(("enterprise_logo_announced", 0.85))
                if LEADER.search(title):     emit.append(("leadership_hire_eng", 0.5))
                for stype, strength in emit:
                    insert_signal(c, cid, "news", stype, strength, obs,
                                  json.dumps({"headline": title}), e.get("link"),
                                  dedupe("news", stype, e.get("link")))
                    print(f"  {dom}: {stype} — {title[:70]}")

if __name__ == "__main__":
    cfg = yaml.safe_load((Path(__file__).parent.parent/"config"/"targets.yaml").read_text())
    run(cfg.get("companies", []), cfg.get("extra_feeds"))
