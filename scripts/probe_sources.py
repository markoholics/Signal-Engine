"""Work out which companies have public job boards and GitHub orgs.

For each company we try the obvious slugs on Greenhouse, Lever and Ashby and
keep whichever responds. Same for GitHub organisations. These are the
companies' own public pages; we are checking whether a careers page exists,
which is what any job seeker does.
"""
import re, yaml, requests, time
from pathlib import Path

CFG = Path(__file__).parent.parent / "config" / "targets.yaml"
UA = {"User-Agent": "signal-engine/0.1 (+markoholics.com)"}

BOARDS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{s}/jobs",
    "lever": "https://api.lever.co/v0/postings/{s}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{s}",
}

def slugs(name, domain):
    base = domain.split(".")[0]
    clean = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    dashed = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return list(dict.fromkeys([base, clean, dashed]))

def alive(url):
    try:
        r = requests.get(url, headers=UA, timeout=15)
        return r.status_code == 200 and len(r.text) > 40
    except Exception:
        return False

def run():
    cfg = yaml.safe_load(CFG.read_text())
    companies = cfg.get("companies", [])
    ats, gh = [], []

    for c in companies:
        dom, name = c["domain"], c.get("name")
        found_board = False
        for s in slugs(name, dom):
            if found_board:
                break
            for board, tmpl in BOARDS.items():
                time.sleep(0.3)
                if alive(tmpl.format(s=s)):
                    ats.append({"board": board, "slug": s, "domain": dom, "name": name})
                    print(f"  JOBS  {dom} -> {board}/{s}")
                    found_board = True
                    break
        for s in slugs(name, dom):
            time.sleep(0.3)
            if alive(f"https://api.github.com/orgs/{s}"):
                gh.append({"org": s, "domain": dom, "name": name})
                print(f"  CODE  {dom} -> github/{s}")
                break

    cfg["ats"], cfg["github"] = ats, gh
    CFG.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    print(f"\n{len(ats)} job boards, {len(gh)} github orgs, from {len(companies)} companies")

if __name__ == "__main__":
    run()
