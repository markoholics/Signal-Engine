"""Source 1: public ATS boards. Greenhouse, Lever and Ashby all expose a
documented public JSON endpoint for a company's own careers page. We read only
what a candidate browsing the careers page would see.

Input: config/targets.yaml -> ats: [{board: greenhouse, slug: acme, domain: acme.com}]
"""
import re, yaml, datetime as dt, json
from pathlib import Path
from collectors.base import get, dedupe
from core.db import conn, upsert_company, insert_signal

SEC = re.compile(r"\b(security|appsec|infosec|soc\s?2|iso\s?27001|dpdp|hipaa|pentest|grc|compliance)\b", re.I)
DEVOPS = re.compile(r"\b(devops|sre|platform engineer|infrastructure engineer|cloud engineer)\b", re.I)
AI = re.compile(r"\b(machine learning|ml engineer|ai engineer|llm|nlp|data scientist|applied scientist)\b", re.I)
COMPLIANCE = re.compile(r"\b(soc\s?2|iso\s?27001|dpdp|gdpr|hipaa|pci[- ]dss|vapt)\b", re.I)

BOARDS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
    "lever":      "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby":      "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=false",
}

def normalise(board, data):
    if board == "greenhouse":
        return [{"title": j.get("title",""), "body": j.get("content",""),
                 "url": j.get("absolute_url"), "ts": j.get("updated_at")}
                for j in data.get("jobs", [])]
    if board == "lever":
        return [{"title": j.get("text",""), "body": json.dumps(j.get("lists", [])) + (j.get("descriptionPlain") or ""),
                 "url": j.get("hostedUrl"),
                 "ts": dt.datetime.fromtimestamp((j.get("createdAt") or 0)/1000, dt.timezone.utc).isoformat()}
                for j in data]
    if board == "ashby":
        return [{"title": j.get("title",""), "body": j.get("descriptionPlain",""),
                 "url": j.get("jobUrl"), "ts": j.get("publishedAt")}
                for j in data.get("jobs", [])]
    return []

def run(targets):
    now = dt.datetime.now(dt.timezone.utc)
    with conn() as c:
        for t in targets:
            try:
                data = get(BOARDS[t["board"]].format(slug=t["slug"])).json()
            except Exception as e:
                print(f"  skip {t['slug']}: {e}")
                continue
            jobs = normalise(t["board"], data)
            cid = upsert_company(c, t["domain"], t.get("name"))
            recent = 0
            for j in jobs:
                text = f"{j['title']} {j['body']}"
                ts = j.get("ts") or now.isoformat()
                try:
                    obs = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    obs = now
                if (now - obs).days <= 30:
                    recent += 1
                emit = []
                if SEC.search(j["title"]):        emit.append(("hiring_security_role", 0.9))
                if DEVOPS.search(j["title"]):     emit.append(("hiring_devops_infra", 0.5))
                if AI.search(j["title"]):         emit.append(("hiring_ai_engineer", 0.55))
                if COMPLIANCE.search(j["body"]):  emit.append(("jd_mentions_compliance", 0.8))
                for stype, strength in emit:
                    insert_signal(c, cid, "ats", stype, strength, obs,
                                  json.dumps({"title": j["title"]}), j.get("url"),
                                  dedupe("ats", t["slug"], stype, j.get("url")))
            if recent >= 3:
                insert_signal(c, cid, "ats", "hiring_velocity_spike", 0.45, now,
                              json.dumps({"open_roles_30d": recent}),
                              f"https://{t['domain']}/careers",
                              dedupe("ats", t["slug"], "spike", now.strftime("%Y-%W")))
            print(f"  {t['domain']}: {len(jobs)} postings, {recent} in last 30d")

if __name__ == "__main__":
    cfg = yaml.safe_load((Path(__file__).parent.parent/"config"/"targets.yaml").read_text())
    run(cfg.get("ats", []))
