-- Nexora shell: delta on top of Alembic 0001-0008. Reference SQL; the real
-- migration is 0009_organizations.py (replica-backend writes it).
-- Access rule: no RLS. Every query goes through an org-scoped dependency
-- (require_org_member) in apps/api; repositories take org_id explicitly.

create table organizations (
  id uuid primary key default gen_random_uuid(),
  clerk_org_id text unique,                 -- null for personal orgs until linked
  name text not null,
  slug text not null unique check (slug ~ '^[a-z0-9-]{2,48}$'),
  is_personal boolean not null default false,
  created_by uuid not null references accounts(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table memberships (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  account_id uuid not null references accounts(id) on delete cascade,
  role text not null check (role in ('owner','admin','member','viewer')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (org_id, account_id)
);
create index on memberships (account_id);
-- exactly-one-owner is enforced in the service layer, plus:
create unique index one_owner_per_org on memberships (org_id) where role = 'owner';

create table product_enablements (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  product_slug text not null check (product_slug in ('vigilo','sentinel','cspm','gateway','neurawall')),
  status text not null default 'enabled' check (status in ('enabled','disabled')),
  enabled_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (org_id, product_slug)
);

-- Existing tables move from account scope to org scope.
-- Order: add nullable org_id -> backfill a personal org per account -> set not null.
alter table projects          add column org_id uuid references organizations(id) on delete cascade;
alter table subscriptions     add column org_id uuid references organizations(id) on delete cascade;
alter table subscriptions     add column product_slug text not null default 'vigilo';
alter table subscriptions     add column billing_interval text not null default 'month'
  check (billing_interval in ('month','year'));
alter table api_keys          add column org_id uuid references organizations(id) on delete cascade;
alter table branding_profiles add column org_id uuid references organizations(id) on delete cascade;
alter table api_keys          add column created_by uuid references accounts(id) on delete set null;
create index on projects (org_id);
create index on subscriptions (org_id, product_slug);
create index on api_keys (org_id);
create unique index on branding_profiles (org_id);
-- after backfill: alter ... set not null on org_id for all four.
-- accounts.plan_id stays for one release as a read-through cache, then is dropped.
-- A product has at most one active subscription per org:
create unique index one_active_sub_per_product on subscriptions (org_id, product_slug)
  where status = 'active';

create table usage_counters (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  product_slug text not null,
  meter text not null,                      -- scans | requests | targets | nodes
  period_start date not null,               -- first day of the month, UTC
  count bigint not null default 0 check (count >= 0),
  updated_at timestamptz not null default now(),
  unique (org_id, product_slug, meter, period_start)
);
-- written with: insert ... on conflict (...) do update set count = usage_counters.count + excluded.count

-- Idempotency for Stripe: reuse/extend the existing webhook-event handling.
create table stripe_events (
  event_id text primary key,
  type text not null,
  processed_at timestamptz not null default now()
);

create table org_invites (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  email text not null,
  role text not null check (role in ('admin','member','viewer')),
  token_hash text not null unique,          -- sha256, plaintext shown once
  invited_by uuid references accounts(id) on delete set null,
  expires_at timestamptz not null,
  accepted_at timestamptz,
  created_at timestamptz not null default now()
);
create index on org_invites (org_id);
create unique index on org_invites (org_id, lower(email)) where accepted_at is null;

-- audit_events is append-only (trigger from 0002); add org context:
alter table audit_events add column org_id uuid references organizations(id) on delete set null;
create index on audit_events (org_id, created_at desc);
