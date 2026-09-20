"""Source 2: certificate transparency via crt.sh. Free, public, no key.

A new certificate for api.company.com is a public record that new external
surface just appeared. This is the earliest legitimate signal available and it
requires no contact with the target's systems at all: we query a public log,
not the company.
"""
import re, yaml, json, datetime as dt
from pathlib import Path
from collections import defaultdict
from collectors.base import get, dedupe
from core.db import conn, upsert_company, insert_signal

API = re.compile(r"^(api|app|gateway|graphql|admin|portal)\.", re.I)
NONPROD = re.compile(r"^(staging|stage|dev|uat|test|qa|sandbox)\.", re.I)

def run(domains):
    now = dt.datetime.now(dt.timezone.utc)
    with conn() as c:
        for d in domains:
            try:
                rows = get(f"https://crt.sh/?q=%25.{d['domain']}&output=json").json()
            except Exception as e:
                print(f"  skip {d['domain']}: {e}")
                continue
            cid = upsert_company(c, d["domain"], d.get("name"))
            seen = defaultdict(lambda: None)
            for r in rows:
                for name in (r.get("name_value") or "").split("\n"):
                    name = name.strip().lower().lstrip("*.")
                    if not name.endswith(d["domain"]):
                        continue
                    try:
                        first = dt.datetime.fromisoformat(r["not_before"]).replace(tzinfo=dt.timezone.utc)
                    except Exception:
                        continue
                    if seen[name] is None or first < seen[name]:
                        seen[name] = first
            fresh = {n: t for n, t in seen.items() if (now - t).days <= 60}
            host = lambda n: n.replace(d["domain"], "").rstrip(".") + "."
            for n, t in fresh.items():
                sub = n[: -len(d["domain"])]
                if API.match(sub):
                    insert_signal(c, cid, "crtsh", "new_api_subdomain", 0.7, t,
                                  json.dumps({"host": n}), f"https://crt.sh/?q={n}",
                                  dedupe("crtsh", n, "api"))
                if NONPROD.match(sub):
                    insert_signal(c, cid, "crtsh", "staging_exposed", 0.6, t,
                                  json.dumps({"host": n}), f"https://crt.sh/?q={n}",
                                  dedupe("crtsh", n, "nonprod"))
            if len(fresh) >= 5:
                insert_signal(c, cid, "crtsh", "subdomain_sprawl", 0.5, now,
                              json.dumps({"new_hosts_60d": len(fresh)}),
                              f"https://crt.sh/?q=%25.{d['domain']}",
                              dedupe("crtsh", d["domain"], "sprawl", now.strftime("%Y-%W")))
            print(f"  {d['domain']}: {len(fresh)} new hosts in 60d")

if __name__ == "__main__":
    cfg = yaml.safe_load((Path(__file__).parent.parent/"config"/"targets.yaml").read_text())
    run(cfg.get("companies", []))
