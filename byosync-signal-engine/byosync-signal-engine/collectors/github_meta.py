"""Source 3: GitHub public metadata only.

Hard boundary: we read manifest filenames and dependency names from public
repositories, plus commit counts. We do not clone, scan for secrets, probe for
vulnerabilities, or store code. Anything that looks like reconnaissance of a
weakness is out of scope, permanently. The signal we want is "new agentic or
integration surface exists", not "here is how to break in".

Auth: a free personal access token raises the rate limit from 60 to 5000/hour.
"""
import os, re, json, yaml, base64, datetime as dt
from pathlib import Path
from collectors.base import get, dedupe
from core.db import conn, upsert_company, insert_signal

TOKEN = os.environ.get("GITHUB_TOKEN")
H = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

LLM = re.compile(r"\b(openai|anthropic|langchain|llama-?index|crewai|autogen|litellm|mistralai|cohere)\b", re.I)
INTEG = re.compile(r"\b(stripe|razorpay|twilio|auth0|clerk|firebase|plaid|segment|hubspot|salesforce)\b", re.I)
MANIFESTS = ["package.json", "requirements.txt", "pyproject.toml", "go.mod", "Gemfile"]

def run(orgs):
    now = dt.datetime.now(dt.timezone.utc)
    with conn() as c:
        for o in orgs:
            try:
                repos = get(f"https://api.github.com/orgs/{o['org']}/repos?per_page=30&sort=pushed",
                            headers=H).json()
            except Exception as e:
                print(f"  skip {o['org']}: {e}")
                continue
            if not isinstance(repos, list):
                print(f"  skip {o['org']}: {repos}")
                continue
            cid = upsert_company(c, o["domain"], o.get("name"))
            has_policy, deps_text, active = False, "", 0
            for r in repos[:12]:
                if r.get("private"):
                    continue
                pushed = dt.datetime.fromisoformat(r["pushed_at"].replace("Z", "+00:00"))
                if (now - pushed).days <= 30:
                    active += 1
                for m in MANIFESTS:
                    try:
                        f = get(f"https://api.github.com/repos/{o['org']}/{r['name']}/contents/{m}",
                                headers=H).json()
                        deps_text += base64.b64decode(f.get("content", "")).decode("utf-8", "ignore")
                        break
                    except Exception:
                        continue
                try:
                    get(f"https://api.github.com/repos/{o['org']}/{r['name']}/contents/SECURITY.md",
                        headers=H)
                    has_policy = True
                except Exception:
                    pass
            if LLM.search(deps_text):
                insert_signal(c, cid, "github", "llm_sdk_adopted", 0.65, now,
                              json.dumps({"matches": sorted(set(m.lower() for m in LLM.findall(deps_text)))}),
                              f"https://github.com/{o['org']}",
                              dedupe("gh", o["org"], "llm", now.strftime("%Y-%m")))
            if INTEG.search(deps_text):
                insert_signal(c, cid, "github", "new_integration_dep", 0.45, now,
                              json.dumps({"matches": sorted(set(m.lower() for m in INTEG.findall(deps_text)))}),
                              f"https://github.com/{o['org']}",
                              dedupe("gh", o["org"], "integ", now.strftime("%Y-%m")))
            if not has_policy and repos:
                insert_signal(c, cid, "github", "no_security_policy", 0.35, now,
                              json.dumps({"public_repos_checked": len(repos[:12])}),
                              f"https://github.com/{o['org']}",
                              dedupe("gh", o["org"], "nopolicy", now.strftime("%Y-%m")))
            if active >= 3:
                insert_signal(c, cid, "github", "high_commit_velocity", 0.3, now,
                              json.dumps({"repos_pushed_30d": active}),
                              f"https://github.com/{o['org']}",
                              dedupe("gh", o["org"], "velocity", now.strftime("%Y-%W")))
            print(f"  {o['org']}: {len(repos)} repos, {active} active, security.md={has_policy}")

if __name__ == "__main__":
    cfg = yaml.safe_load((Path(__file__).parent.parent/"config"/"targets.yaml").read_text())
    run(cfg.get("github", []))
