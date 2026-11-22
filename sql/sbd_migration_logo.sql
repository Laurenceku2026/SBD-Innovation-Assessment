-- Run once in the same TechLife Supabase SQL editor (after sbd_schema.sql).
alter table public.sbd_settings
  add column if not exists logo_url text;
