"""Source 6: watch the company's own public pages for change.

This is the highest intent signal available for a security and compliance
buyer, and almost nobody collects it. When a company publishes a /security
page, adds an Enterprise pricing tier, or names SOC 2 for the first time, a
customer has just asked them hard questions. That is the week to call.

We fetch the same public pages a prospective customer would read, once a week,
and compare against last week's fingerprint. We store a hash and a handful of
extracted facts, never the page content.
"""
import re, json, yaml, hashlib, datetime as dt
from pathlib import Path
from collectors.base import get, dedupe
from core.db import conn, upsert_company, insert_signal

PAGES = {
    "security": ["/security", "/trust", "/security-policy", "/trust-center"],
    "pricing":  ["/pricing", "/plans", "/pricing-plans"],
    "careers":  ["/careers", "/jobs", "/join-us", "/work-with-us"],
}

ENTERPRISE = re.compile(r"\b(enterprise|custom pricing|talk to sales|contact sales)\b", re.I)
CERTS      = re.compile(r"\b(soc\s?2|iso\s?27001|dpdp|gdpr|hipaa|pci[- ]dss)\b", re.I)
SUBPROC    = re.compile(r"\b(sub[- ]?processor|data processing addendum|dpa)\b", re.I)
SEC_ROLE   = re.compile(r"\b(security engineer|appsec|infosec|security lead|grc|compliance manager)\b", re.I)
AI_ROLE    = re.compile(r"\b(ml engineer|ai engineer|llm|applied scientist|machine learning)\b", re.I)
DEVOPS     = re.compile(r"\b(devops|sre|platform engineer|infrastructure engineer)\b", re.I)

def strip_html(html):
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()

def facts_for(kind, text):
    if kind == "security":
        return {"exists": True,
                "certs": sorted({m.lower().replace(" ", "") for m in CERTS.findall(text)}),
                "subprocessors": bool(SUBPROC.search(text))}
    if kind == "pricing":
        return {"enterprise_tier": bool(ENTERPRISE.search(text)),
                "certs": sorted({m.lower().replace(" ", "") for m in CERTS.findall(text)})}
    return {"security_role": bool(SEC_ROLE.search(text)),
            "ai_role": bool(AI_ROLE.search(text)),
            "devops_role": bool(DEVOPS.search(text)),
            "mentions_certs": sorted({m.lower().replace(" ", "") for m in CERTS.findall(text)})}

def fetch_first(domain, paths):
    for p in paths:
        for scheme in ("https://", "https://www."):
            url = f"{scheme}{domain}{p}"
            try:
                r = get(url)
            except Exception:
                continue
            if len(r.text) > 500:
                return url, strip_html(r.text)[:40000]
    return None, None

def previous(cur, company_id, kind):
    cur.execute("""select content_hash, facts from page_snapshot
                   where company_id=%s and page_kind=%s
                   order by captured_at desc limit 1""", (company_id, kind))
    return cur.fetchone()

def run(companies):
    now = dt.datetime.now(dt.timezone.utc)
    with conn() as c, c.cursor() as cur:
        for comp in companies:
            dom, name = comp["domain"], comp.get("name")
            cid = upsert_company(c, dom, name)
            for kind, paths in PAGES.items():
                url, text = fetch_first(dom, paths)
                if not text:
                    continue
                facts = facts_for(kind, text)
                h = hashlib.sha1(text.encode()).hexdigest()
                prev = previous(cur, cid, kind)
                prev_facts = (prev[1] if prev else {}) or {}

                emit = []
                if kind == "security" and not prev:
                    emit.append(("security_page_published", 0.8))
                if kind == "pricing":
                    if facts["enterprise_tier"] and not prev_facts.get("enterprise_tier"):
                        emit.append(("enterprise_tier_added", 0.85))
                if kind == "careers":
                    if facts["security_role"] and not prev_facts.get("security_role"):
                        emit.append(("hiring_security_role", 0.9))
                    if facts["ai_role"] and not prev_facts.get("ai_role"):
                        emit.append(("hiring_ai_engineer", 0.55))
                    if facts["devops_role"] and not prev_facts.get("devops_role"):
                        emit.append(("hiring_devops_infra", 0.5))
                new_certs = set(facts.get("certs") or facts.get("mentions_certs") or []) - \
                            set(prev_facts.get("certs") or prev_facts.get("mentions_certs") or [])
                if new_certs and prev:
                    emit.append(("certification_first_mentioned", 0.9))
                if facts.get("subprocessors") and not prev_facts.get("subprocessors"):
                    emit.append(("subprocessor_list_published", 0.7))
                if prev and prev[0] != h and not emit:
                    emit.append(("watched_page_changed", 0.25))

                for stype, strength in emit:
                    insert_signal(c, cid, "pagewatch", stype, strength, now,
                                  json.dumps({"page": kind, **facts}), url,
                                  dedupe("pw", dom, kind, stype, now.strftime("%Y-%W")))
                    print(f"  {dom}: {stype} ({kind})")

                cur.execute("""insert into page_snapshot
                               (company_id, page_kind, url, content_hash, facts)
                               values (%s,%s,%s,%s,%s::jsonb)""",
                            (cid, kind, url, h, json.dumps(facts)))

if __name__ == "__main__":
    cfg = yaml.safe_load((Path(__file__).parent.parent/"config"/"targets.yaml").read_text())
    run(cfg.get("companies", []))
