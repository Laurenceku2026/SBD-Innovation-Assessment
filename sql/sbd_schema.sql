-- Run in the existing TechLife Supabase SQL editor.
-- Isolated SBD Innovation Assessment tables (do not mix with profiles).

create table if not exists public.sbd_users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  status text not null default 'pending' check (status in ('pending', 'approved', 'disabled')),
  display_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.sbd_login_events (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  logged_at timestamptz not null default now()
);
create index if not exists sbd_login_events_email_time
  on public.sbd_login_events (email, logged_at desc);

create table if not exists public.sbd_access_requests (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  message text,
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  created_at timestamptz not null default now()
);

create table if not exists public.sbd_settings (
  id int primary key default 1,
  admin_emails text not null default ''
);

insert into public.sbd_settings (id, admin_emails)
values (1, '')
on conflict (id) do nothing;

alter table public.sbd_users enable row level security;
alter table public.sbd_login_events enable row level security;
alter table public.sbd_access_requests enable row level security;
alter table public.sbd_settings enable row level security;
