"""Source 5: launch and developer platform feeds.

Hacker News via the free Algolia API, plus Product Hunt's public RSS. A launch
is the moment a product goes from private to publicly reachable, which is
exactly when its external surface becomes everyone's problem.
"""
import re, json, yaml, datetime as dt
from pathlib import Path
import feedparser
from collectors.base import get, dedupe
from core.db import conn, upsert_company, insert_signal

API_WORDS = re.compile(r"\b(api|developer platform|public beta|sdk|mcp server)\b", re.I)
HN = "https://hn.algolia.com/api/v1/search_by_date?query={q}&tags=story&hitsPerPage=50"
PH = "https://www.producthunt.com/feed"

def match(blob, targets):
    blob = blob.lower()
    for t in targets:
        nm = (t.get("name") or t["domain"].split(".")[0]).lower()
        if len(nm) > 3 and (nm in blob or t["domain"] in blob):
            return t["domain"], t.get("name")
    return None, None

def run(targets, queries=None):
    now = dt.datetime.now(dt.timezone.utc)
    queries = queries or ["Launch HN India AI", "Show HN India"]
    with conn() as c:
        for q in queries:
            try:
                hits = get(HN.format(q=q.replace(" ", "%20"))).json().get("hits", [])
            except Exception as e:
                print(f"  skip HN {q}: {e}")
                continue
            for h in hits:
                blob = f"{h.get('title','')} {h.get('url','')}"
                dom, name = match(blob, targets)
                if not dom:
                    continue
                obs = dt.datetime.fromisoformat(h["created_at"].replace("Z", "+00:00"))
                cid = upsert_company(c, dom, name)
                stype, strength = ("api_public_beta", 0.7) if API_WORDS.search(blob) else ("product_launch", 0.6)
                insert_signal(c, cid, "launch", stype, strength, obs,
                              json.dumps({"title": h.get("title")}),
                              f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                              dedupe("hn", h.get("objectID")))
                print(f"  {dom}: {stype} — {h.get('title','')[:60]}")
        for e in feedparser.parse(PH).entries[:50]:
            blob = f"{e.get('title','')} {e.get('summary','')}"
            dom, name = match(blob, targets)
            if not dom:
                continue
            cid = upsert_company(c, dom, name)
            insert_signal(c, cid, "launch", "product_launch", 0.6, now,
                          json.dumps({"title": e.get("title")}), e.get("link"),
                          dedupe("ph", e.get("link")))
            print(f"  {dom}: product_launch (Product Hunt)")

if __name__ == "__main__":
    cfg = yaml.safe_load((Path(__file__).parent.parent/"config"/"targets.yaml").read_text())
    run(cfg.get("companies", []), cfg.get("hn_queries"))
