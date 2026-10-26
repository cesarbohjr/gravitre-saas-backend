-- Where a conversation was started (web, desktop, extension or voice), so the other
-- surfaces can show "Started in the extension". Null for conversations from before this.
alter table public.conversations
  add column if not exists surface text;

alter table public.conversations
  drop constraint if exists conversations_surface_check;

alter table public.conversations
  add constraint conversations_surface_check
  check (surface is null or surface in ('web', 'desktop', 'extension', 'voice'));
