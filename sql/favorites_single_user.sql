-- Single-user favorites table (no Supabase Auth required).
-- Use FAVORITES_USER_KEY in app env (defaults to 'kb_owner').

create table if not exists public.favorites (
  id uuid primary key default gen_random_uuid(),
  user_key text not null,
  listing_id text not null references public.listings(listing_id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_key, listing_id)
);

create index if not exists favorites_user_key_idx on public.favorites(user_key);
create index if not exists favorites_listing_id_idx on public.favorites(listing_id);

-- For single-user server-side Streamlit, simplest is to keep RLS disabled:
alter table public.favorites disable row level security;
