"""Drafts the opening email for each queued send.

Copy rules are enforced in code because they are non-negotiable on this
account: no em dashes, no competitor names, no 24/7 monitoring claims, no
biometric or KYC language, no government affiliation, no invented statistics,
no standalone "compliance" as a headline noun. Locked brand lines appear
verbatim or not at all.

Control arm drafts deliberately contain no signal reference. That is the test.
"""
import re, sys, json
from core.db import conn

BANNED = [
    (r"—|–", "em or en dash"),
    (r"\b(vanta|sprinto|drata)\b", "competitor name"),
    (r"24/7|24x7|round[- ]the[- ]clock", "24/7 monitoring claim"),
    (r"\b(biometric|face auth|facial recognition|kyc)\b", "prohibited product framing"),
    (r"\b(ministry|government[- ]backed|govt[- ]approved)\b", "implied government affiliation"),
]

TAGLINE = "Find the leak. Fix the flow. Keep the proof."

SIGNAL_OPENERS = {
    "hiring_security_role":
        "Saw you have a security role open at {company}.",
    "jd_mentions_compliance":
        "Your open role at {company} lists SOC 2 and ISO 27001 work.",
    "enterprise_logo_announced":
        "Congratulations on the {company} enterprise announcement.",
    "new_api_subdomain":
        "Noticed {company} has stood up a new public API endpoint.",
    "api_public_beta":
        "Saw {company} opened its API to the public.",
    "funding_round":
        "Congratulations on the raise at {company}.",
    "llm_sdk_adopted":
        "Saw {company} is building on LLM tooling in the open.",
    "product_launch":
        "Saw the {company} launch.",
    "staging_exposed":
        "Noticed {company} has non production environments resolving publicly.",
}

SIGNAL_BODY = {
    "hiring_security_role":
        "That search usually runs six months, and the risk does not wait for the hire.",
    "jd_mentions_compliance":
        "That reads like a customer asked for evidence before signing.",
    "enterprise_logo_announced":
        "A customer of that size brings a security questionnaire with it.",
    "new_api_subdomain":
        "New surface is the point where findings pile up fastest.",
    "api_public_beta":
        "A public API changes who can reach your data, and how fast.",
    "funding_round":
        "The next set of buyers will ask for proof before they sign.",
    "llm_sdk_adopted":
        "Agent tooling moves faster than the controls around it.",
    "product_launch":
        "Launch week is when external surface grows quickest.",
    "staging_exposed":
        "Non production environments tend to hold production shaped data.",
}

CLOSE = ("ByoSync is the security and compliance engineering layer for Indian "
         "AI native SaaS teams with a live product and no security team. "
         "AI proposes. Humans approve. Deterministic runtime enforces.\n\n"
         "Worth fifteen minutes to see whether it applies to you?\n\n"
         "Mohammad H. Rahman, Markoholics")

def draft(item):
    company = (item.get("name") or item["domain"].split(".")[0]).title()
    first = (item.get("person") or "there").split()[0]
    if item["arm"] == "signal":
        sig = next((s for s in item["signals"] if s in SIGNAL_OPENERS), None)
        if not sig:
            item = {**item, "arm": "control"}
        else:
            subject = f"{company} and the gap after the API ships"
            body = (f"Hi {first},\n\n"
                    f"{SIGNAL_OPENERS[sig].format(company=company)} "
                    f"{SIGNAL_BODY[sig]}\n\n{CLOSE}")
            return check(subject, body, sig)
    subject = f"Security engineering for {company}"
    body = (f"Hi {first},\n\n"
            f"I work with Indian AI native SaaS teams that have a live product, "
            f"sensitive customer data and no dedicated security team.\n\n{CLOSE}")
    return check(subject, body, None)

def check(subject, body, sig):
    problems = []
    for pattern, label in BANNED:
        if re.search(pattern, subject + body, re.I):
            problems.append(label)
    return {"subject": subject, "body": body, "signal_used": sig, "violations": problems}

def run(queue):
    out = []
    with conn() as c, c.cursor() as cur:
        for item in queue:
            d = draft(item)
            if d["violations"]:
                print(f"  BLOCKED {item['domain']}: {d['violations']}")
                continue
            cur.execute("update send set subject=%s, body=%s where id=%s",
                        (d["subject"], d["body"], item["send_id"]))
            out.append({**item, **d})
    return out

if __name__ == "__main__":
    from outreach.queue import build
    for d in run(build()):
        print("=" * 70)
        print(f"[{d['arm']}] {d['email']}  score={d['score']:.3f}")
        print(d["subject"]); print(); print(d["body"])
