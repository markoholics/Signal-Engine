-- Stores a fingerprint of each watched page so we can detect change week to week.
-- We keep a hash and a small set of extracted facts, never the page itself.

create table if not exists page_snapshot (
    id            bigserial primary key,
    company_id    bigint references company(id) on delete cascade,
    page_kind     text not null,          -- pricing | security | careers | home
    url           text not null,
    content_hash  text not null,
    facts         jsonb not null default '{}'::jsonb,
    captured_at   timestamptz not null default now()
);
create index if not exists idx_snap_company on page_snapshot (company_id, page_kind, captured_at desc);
