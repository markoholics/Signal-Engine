import os, psycopg
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DSN = os.environ.get("DATABASE_URL")

@contextmanager
def conn():
    if not DSN:
        raise RuntimeError("DATABASE_URL not set. Copy .env.example to .env.")
    with psycopg.connect(DSN, autocommit=True) as c:
        yield c

def upsert_company(c, domain, name=None, country="IN", meta=None):
    with c.cursor() as cur:
        cur.execute(
            """insert into company (domain, name, country, meta)
               values (%s, %s, %s, coalesce(%s::jsonb, '{}'::jsonb))
               on conflict (domain) do update
                 set last_seen = now(),
                     name = coalesce(company.name, excluded.name)
               returning id""",
            (domain.lower().strip(), name, country, meta),
        )
        return cur.fetchone()[0]

def insert_signal(c, company_id, source, signal_type, strength, observed_at,
                  payload, evidence_url, dedupe_key):
    """Idempotent. Re-running a collector never double counts."""
    with c.cursor() as cur:
        cur.execute(
            """insert into signal_event
               (company_id, source, signal_type, strength, observed_at,
                payload, evidence_url, dedupe_key)
               values (%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
               on conflict (dedupe_key) do nothing
               returning id""",
            (company_id, source, signal_type, strength, observed_at,
             payload, evidence_url, dedupe_key),
        )
        row = cur.fetchone()
        return row[0] if row else None

def is_suppressed(c, email=None, domain=None):
    with c.cursor() as cur:
        cur.execute(
            """select 1 from suppression
               where (email is not null and lower(email) = lower(%s))
                  or (domain is not null and lower(domain) = lower(%s))
               limit 1""",
            (email or "", domain or ""),
        )
        return cur.fetchone() is not None
