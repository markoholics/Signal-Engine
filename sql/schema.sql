-- Signal engine schema. Postgres 14+. Supabase free tier is fine.
-- Design rule: every table that can hold a person also holds provenance and consent state.

create table if not exists company (
    id              bigserial primary key,
    domain          text unique not null,
    name            text,
    country         text,
    employee_band   text,
    first_seen      timestamptz not null default now(),
    last_seen       timestamptz not null default now(),
    icp_fit         numeric,          -- 0..1, set by core/fit.py
    icp_reasons     jsonb default '[]'::jsonb,
    meta            jsonb default '{}'::jsonb
);

create table if not exists person (
    id              bigserial primary key,
    company_id      bigint references company(id) on delete cascade,
    full_name       text,
    role_title      text,
    seniority       text,
    email           text unique,
    email_status    text default 'unverified',   -- unverified | valid | risky | invalid
    source          text not null,               -- where this contact came from
    consent_basis   text not null default 'legitimate_interest_b2b',
    suppressed      boolean not null default false,
    created_at      timestamptz not null default now()
);

-- One row per observed event. Never overwrite. Decay is applied at read time.
create table if not exists signal_event (
    id              bigserial primary key,
    company_id      bigint references company(id) on delete cascade,
    source          text not null,          -- greenhouse | github | crtsh | news | launch
    signal_type     text not null,          -- see config/signals.yaml
    strength        numeric not null,       -- 0..1 raw strength before decay
    observed_at     timestamptz not null,
    payload         jsonb not null default '{}'::jsonb,
    evidence_url    text,
    dedupe_key      text unique not null
);
create index if not exists idx_signal_company_time on signal_event (company_id, observed_at desc);

-- A client lens turns raw signals into a score. One row per client.
create table if not exists client_lens (
    id              bigserial primary key,
    client          text unique not null,
    weights         jsonb not null,
    half_life_days  integer not null default 30,
    min_score       numeric not null default 0.45,
    updated_at      timestamptz not null default now()
);

-- Every send, including control arm sends. arm is the experiment.
create table if not exists send (
    id              bigserial primary key,
    client          text not null,
    person_id       bigint references person(id) on delete cascade,
    company_id      bigint references company(id) on delete cascade,
    arm             text not null,                  -- 'signal' | 'control'
    score_at_send   numeric,
    signals_at_send jsonb default '[]'::jsonb,
    sequence_step   integer not null default 1,
    subject         text,
    body            text,
    approved_by     text,
    sent_at         timestamptz,
    provider_msg_id text,
    created_at      timestamptz not null default now()
);
create index if not exists idx_send_arm on send (client, arm, sent_at);

-- The ledger. This is the asset. One row per observed outcome.
create table if not exists outcome (
    id              bigserial primary key,
    send_id         bigint references send(id) on delete cascade,
    outcome_type    text not null,   -- delivered|open|reply|positive_reply|meeting|opportunity|won|unsubscribe|bounce
    occurred_at     timestamptz not null default now(),
    notes           text,
    source          text default 'manual'
);
create index if not exists idx_outcome_type on outcome (outcome_type, occurred_at);

-- Global suppression. Checked before every send, no exceptions.
create table if not exists suppression (
    id              bigserial primary key,
    email           text,
    domain          text,
    reason          text not null,
    created_at      timestamptz not null default now()
);
create unique index if not exists idx_supp_email on suppression (lower(email)) where email is not null;
create unique index if not exists idx_supp_domain on suppression (lower(domain)) where domain is not null;
