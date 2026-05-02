-- Run this in the Supabase SQL Editor to create the insights tables.
-- These tables track daily and lifetime usage metrics for the Wiztant Insights dashboard.

-- =============================================================
--  1. Lifetime counters (one row per user)
-- =============================================================
create table if not exists public.user_insights_lifetime (
  user_id uuid primary key references auth.users(id) on delete cascade,
  total_words_dictated bigint default 0,
  total_fixes_made bigint default 0,
  total_words_removed bigint default 0,
  dictionary_items_used bigint default 0,
  work_messages bigint default 0,
  ai_prompts bigint default 0,
  personal_messages bigint default 0,
  documents_touched bigint default 0,
  voice_commands bigint default 0,
  other_tasks bigint default 0,
  apps_used bigint default 0,
  current_streak int default 0,
  longest_streak int default 0,
  updated_at timestamptz default now()
);

-- Enable Row Level Security
alter table public.user_insights_lifetime enable row level security;

-- Users can only read their own lifetime insights
create policy "Users read own lifetime insights"
  on public.user_insights_lifetime for select
  using (auth.uid() = user_id);

-- Users can only upsert their own lifetime insights
create policy "Users upsert own lifetime insights"
  on public.user_insights_lifetime for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);


-- =============================================================
--  2. Daily rows (heatmap + streak source)
-- =============================================================
create table if not exists public.user_insights_daily (
  user_id uuid not null references auth.users(id) on delete cascade,
  date date not null,
  words_dictated int default 0,
  fixes_made int default 0,
  words_removed int default 0,
  work_messages int default 0,
  ai_prompts int default 0,
  personal_messages int default 0,
  documents_touched int default 0,
  voice_commands int default 0,
  other_tasks int default 0,
  apps_used int default 0,
  activity_score int default 0,   -- >0 means "active day" for streak calc
  primary key (user_id, date)
);

-- Fast index for heatmap queries (last N days)
create index if not exists idx_insights_daily_user_date
  on public.user_insights_daily(user_id, date desc);

-- Enable Row Level Security
alter table public.user_insights_daily enable row level security;

-- Users can only read their own daily insights
create policy "Users read own daily insights"
  on public.user_insights_daily for select
  using (auth.uid() = user_id);

-- Users can only upsert their own daily insights
create policy "Users upsert own daily insights"
  on public.user_insights_daily for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
