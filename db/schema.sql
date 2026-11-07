-- Application tables. Safe to run more than once.
-- LangGraph creates its own checkpoint tables through PostgresSaver.setup().

create extension if not exists vector;

create table if not exists app_users (
    id         text primary key,
    name       text not null,
    all_brands boolean not null default false
);

create table if not exists user_brands (
    user_id text not null references app_users (id) on delete cascade,
    brand   text not null,
    primary key (user_id, brand)
);

-- Each change of tone is a new version; exactly one version is active.
create table if not exists personas (
    id           serial primary key,
    name         text not null,
    version      integer not null,
    instructions text not null,
    active       boolean not null default false,
    created_at   timestamptz not null default now(),
    unique (name, version)
);
create unique index if not exists personas_single_active on personas (active) where active;

create table if not exists reports (
    id              bigserial primary key,
    owner_id        text not null references app_users (id),
    conversation_id text not null,
    title           text not null,
    body_text       text not null,
    body_html       text not null,
    created_at      timestamptz not null default now(),
    search          tsvector generated always as (to_tsvector('english', title || ' ' || body_text)) stored
);
create index if not exists reports_search on reports using gin (search);
create index if not exists reports_owner on reports (owner_id, conversation_id);

-- A delete runs only from the report IDs stored here, once, before expiry.
create table if not exists delete_requests (
    id            uuid primary key default gen_random_uuid(),
    owner_id      text not null references app_users (id),
    report_ids    bigint[] not null,
    description   text not null,
    created_at    timestamptz not null default now(),
    expires_at    timestamptz not null,
    used_at       timestamptz,
    deleted_count integer
);
