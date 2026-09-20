"""Source 6: watch each company's own public pages for changes.

The highest intent signal available for a security and compliance buyer is not
on a job board. It is on the prospect's own site. When an Enterprise tier
appears on the pricing page, or a /security page shows up, or a sub-processor
list is published, somebody's procurement team has just asked hard questions.

Method: fetch a small set of well known paths weekly, reduce each page to a
fingerprint of the facts we care about, and store it. Next week, compare. A
change fires a signal. The first run establishes the baseline and fires
nothing, which is correct and not a failure.

We fetch the same pages a customer evaluating them would fetch, at one request
per second, and we read text only. Nothing here probes for weaknesses.
"""
import re, json, yaml, hashlib, datetime as dt
from pathlib import Path
import requests
from core.db import conn, upsert_company, insert_signal

CFG = Path(__file__).parent.parent / "config" / "targets.yaml"
UA = {"User-Agent": "signal-engine/0.1 (+markoholics.com)"}

PATHS = ["/pricing", "/security", "/trust", "/careers", "/jobs",
         "/legal/sub-processors", "/subprocessors", "/compliance"]

# What we look for in the text. Each is a fact that, once true, means something.
MARKERS = {
    "enterprise_tier":   re.compile(r"\benterprise\b.{0,40}(plan|tier|pricing|contact sales)", re.I),
    "soc2_claim":        re.compile(r"\bsoc\s?2\b", re.I),
    "iso27001_claim":    re.compile(r"\biso[\s/-]?27001\b", re.I),
    "dpdp_claim":        re.compile(r"\bdpdp\b|digital personal data protection", re.I),
    "gdpr_claim":        re.compile(r"\bgdpr\b", re.I),
    "hipaa_claim":       re.compile(r"\bhipaa\b", re.I),
    "subprocessor_list": re.compile(r"\bsub[-\s]?processor", re.I),
    "trust_centre":      re.compile(r"\btrust (cent|port|page)", re.I),
    "security_hiring":   re.compile(r"\b(security engineer|appsec|infosec|security lead)\b", re.I),
    "ai_hiring":         re.compile(r"\b(ml engineer|ai engineer|llm engineer)\b", re.I),
}

# What a newly appeared marker is worth, and what it means.
ON_APPEAR = {
    "enterprise_tier":   ("enterprise_tier_added", 0.8),
    "soc2_claim":        ("compliance_claim_added", 0.85),
    "iso27001_claim":    ("compliance_claim_added", 0.85),
    "dpdp_claim":        ("compliance_claim_added", 0.8),
    "gdpr_claim":        ("compliance_claim_added", 0.6),
    "hipaa_claim":       ("compliance_claim_added", 0.75),
    "subprocessor_list": ("subprocessor_list_published", 0.7),
    "trust_centre":      ("trust_page_published", 0.75),
    "security_hiring":   ("hiring_security_role", 0.9),
    "ai_hiring":         ("hiring_ai_engineer", 0.55),
}

def text_of(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)[:200000]

def fetch(domain, path):
    for scheme in ("https://", "https://www."):
        try:
            r = requests.get(scheme + domain + path, headers=UA, timeout=20,
                             allow_redirects=True)
            if r.status_code == 200 and len(r.text) > 500:
                return r.text
        except Exception:
            continue
    return None

def fingerprint(domain):
    """Which markers are currently true anywhere on this company's public pages."""
    found = set()
    pages_seen = 0
    import time
    for p in PATHS:
        html = fetch(domain, p)
        time.sleep(1.0)
        if not html:
            continue
        pages_seen += 1
        txt = text_of(html)
        for key, rx in MARKERS.items():
            if rx.search(txt):
                found.add(key)
    return found, pages_seen

def run(companies):
    now = dt.datetime.now(dt.timezone.utc)
    first_run = changed = 0
    with conn() as c, c.cursor() as cur:
        for comp in companies:
            dom = comp["domain"]
            if dom in ("play.google.com",):
                continue
            found, pages = fingerprint(dom)
            if pages == 0:
                print(f"  {dom}: no readable pages")
                continue
            cid = upsert_company(c, dom, comp.get("name"))

            cur.execute("""select payload->'markers' from signal_event
                           where company_id=%s and signal_type='page_baseline'
                           order by observed_at desc limit 1""", (cid,))
            row = cur.fetchone()
            previous = set(row[0]) if row and row[0] else None

            if previous is None:
                insert_signal(c, cid, "pagewatch", "page_baseline", 0.0, now,
                              json.dumps({"markers": sorted(found), "pages": pages}),
                              f"https://{dom}",
                              hashlib.sha1(f"baseline|{dom}|{now.date()}".encode()).hexdigest())
                first_run += 1
                print(f"  {dom}: baseline set, {len(found)} markers across {pages} pages")
                continue

            appeared = found - previous
            for m in appeared:
                stype, strength = ON_APPEAR[m]
                insert_signal(c, cid, "pagewatch", stype, strength, now,
                              json.dumps({"marker": m, "page_count": pages}),
                              f"https://{dom}",
                              hashlib.sha1(f"appear|{dom}|{m}|{now.strftime('%Y-%W')}".encode()).hexdigest())
                print(f"  {dom}: NEW {m} -> {stype}")
                changed += 1

            insert_signal(c, cid, "pagewatch", "page_baseline", 0.0, now,
                          json.dumps({"markers": sorted(found), "pages": pages}),
                          f"https://{dom}",
                          hashlib.sha1(f"baseline|{dom}|{now.date()}".encode()).hexdigest())

    print(f"\n{first_run} baselines established, {changed} changes detected")
    if first_run and not changed:
        print("First run establishes the baseline and fires nothing. "
              "Changes appear from next week onwards.")

if __name__ == "__main__":
    cfg = yaml.safe_load(CFG.read_text())
    run(cfg.get("companies", []))
