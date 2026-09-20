"""ICP fit for ByoSync, scored 0..1 from cheap public attributes.

ICP (from the engagement brief): founders, CTOs and heads of engineering at
Indian AI-native SaaS or technology MSMEs, 4 to 100 employees, with a live
product handling sensitive customer data through two or more integrations and
no dedicated security team.

Fit is structural and slow moving. Score is behavioural and fast moving.
They are deliberately kept apart so a perfect fit account with no timing does
not get emailed, and a hot signal at a 5000 person enterprise does not either.
"""
import json
from core.db import conn

AI_TOKENS = {"ai", "ml", "llm", "agent", "genai", "copilot", "model"}
SENSITIVE_TOKENS = {"health", "fintech", "insur", "bank", "lend", "medical",
                    "payroll", "hr", "legal", "kyc", "edtech", "patient"}

def score_fit(meta):
    reasons, pts, total = [], 0.0, 0.0

    def add(cond, weight, label):
        nonlocal pts, total
        total += weight
        if cond:
            pts += weight
            reasons.append(label)

    country = (meta.get("country") or "").upper()
    add(country in ("IN", "INDIA"), 2.0, "India based")

    band = meta.get("employee_band") or ""
    add(band in ("4-10", "11-50", "51-100", "2-10", "11-100"), 2.0, "4 to 100 employees")

    text = " ".join([meta.get("name", ""), meta.get("description", ""),
                     " ".join(meta.get("tags", []))]).lower()
    add(any(t in text for t in AI_TOKENS), 1.5, "AI native product")
    add(any(t in text for t in SENSITIVE_TOKENS), 1.5, "Regulated or sensitive data domain")
    add(int(meta.get("integration_count", 0)) >= 2, 1.5, "Two or more integrations")
    add(bool(meta.get("has_live_product")), 1.5, "Live product in market")
    add(not meta.get("has_security_hire", False), 1.0, "No dedicated security hire found")

    return round(pts / total, 3) if total else 0.0, reasons

def refresh_all():
    with conn() as c, c.cursor() as cur:
        cur.execute("select id, domain, name, country, employee_band, meta from company")
        for cid, domain, name, country, band, meta in cur.fetchall():
            m = dict(meta or {})
            m.update({"name": name or domain, "country": country, "employee_band": band})
            fit, reasons = score_fit(m)
            cur.execute("update company set icp_fit=%s, icp_reasons=%s::jsonb where id=%s",
                        (fit, json.dumps(reasons), cid))

if __name__ == "__main__":
    refresh_all()
    print("ICP fit refreshed.")
