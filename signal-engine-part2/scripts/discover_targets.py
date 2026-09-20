"""Build the target list automatically from free public sources.

Primary source: the yc-oss unofficial YC API, a static JSON mirror of YC's own
public Algolia index, updated daily, no key, no quota.
  https://yc-oss.github.io/api/companies/all.json

We filter to the ByoSync ICP shape: India located, small team, recent batch,
AI or B2B software. Team size is the cheapest proxy available for "4 to 100
employees and no security team".

This writes config/targets.yaml. Hand edits survive: anything already in the
file is kept and never overwritten, so you can pin companies the filter misses.
"""
import re, yaml, json
from pathlib import Path
from urllib.parse import urlparse
from collectors.base import get

ALL = "https://yc-oss.github.io/api/companies/all.json"
CFG = Path(__file__).parent.parent / "config" / "targets.yaml"

AI_TAGS = {"ai", "artificial-intelligence", "generative-ai", "machine-learning",
           "ai-assistant", "aiops", "llm", "saas", "b2b", "developer-tools",
           "api", "fintech", "healthcare", "security", "legaltech", "hr-tech"}

MIN_BATCH_YEAR = 2022      # young enough to still be small
MIN_TEAM, MAX_TEAM = 4, 100

def domain_of(url):
    if not url:
        return None
    host = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    return host[4:] if host.startswith("www.") else host or None

def batch_year(batch):
    m = re.search(r"(20\d{2})", batch or "")
    return int(m.group(1)) if m else 0

def fits(c):
    if "india" not in (c.get("all_locations") or "").lower():
        return False
    team = c.get("team_size") or 0
    if not (MIN_TEAM <= team <= MAX_TEAM):
        return False
    if batch_year(c.get("batch")) < MIN_BATCH_YEAR:
        return False
    tags = {t.lower().replace(" ", "-") for t in (c.get("tags") or [])}
    industry = (c.get("industry") or "").lower()
    return bool(tags & AI_TAGS) or "b2b" in industry or "ai" in industry

def github_org(c):
    """YC profiles sometimes carry a GitHub link. Only use it if it is an org."""
    for key in ("github_url", "url"):
        v = c.get(key) or ""
        m = re.search(r"github\.com/([A-Za-z0-9-]+)/?$", v)
        if m:
            return m.group(1)
    return None

def run():
    data = get(ALL).json()
    existing = yaml.safe_load(CFG.read_text()) if CFG.exists() else {}
    known = {c["domain"] for c in existing.get("companies", [])}

    added = []
    for c in data:
        if not fits(c):
            continue
        dom = domain_of(c.get("website"))
        if not dom or dom in known:
            continue
        entry = {"domain": dom, "name": c.get("name"),
                 "source": f"YC {c.get('batch')}", "team_size": c.get("team_size")}
        gh = github_org(c)
        if gh:
            entry["github_org"] = gh
        added.append(entry)
        known.add(dom)

    existing.setdefault("companies", []).extend(
        [{k: v for k, v in e.items() if k in ("domain", "name")} for e in added])
    existing.setdefault("github", []).extend(
        [{"org": e["github_org"], "domain": e["domain"], "name": e["name"]}
         for e in added if e.get("github_org")])

    CFG.write_text(yaml.safe_dump(existing, sort_keys=False, allow_unicode=True))
    print(f"discovered {len(added)} new companies, {len(existing['companies'])} total")
    for e in added[:25]:
        print(f"  {e['domain']:<34} {e['name']}  ({e['source']}, team {e['team_size']})")
    if len(added) > 25:
        print(f"  ... and {len(added)-25} more")

if __name__ == "__main__":
    run()
