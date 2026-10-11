-- ============================================================
-- GeradorBB — Migração inicial
-- Cole este SQL no Supabase → SQL Editor → Run
-- ============================================================

-- 0. Tabela de versões (para auto-update dos clientes)
--    Você insere aqui quando quiser soltar uma atualização:
--    INSERT INTO versoes (versao, url_download, notas)
--    VALUES ('1.1', 'https://link.do/GeradorBB_v1.1.zip', 'Novas funções');
create table if not exists public.versoes (
  id           uuid default gen_random_uuid() primary key,
  versao       text not null,
  url_download text not null,
  notas        text default '',
  created_at   timestamptz default now()
);
-- Qualquer usuário autenticado pode LER a versão mais recente
alter table public.versoes enable row level security;
create policy "versoes_publico_le"
  on public.versoes for select
  using (true);

-- 1. Tabela de perfis (extende auth.users)
create table if not exists public.profiles (
  id         uuid references auth.users on delete cascade primary key,
  nome       text not null default '',
  email      text not null default '',
  is_admin   boolean default false,
  created_at timestamptz default now()
);

-- 2. Tabela de licenças
create table if not exists public.licencas (
  id         uuid default gen_random_uuid() primary key,
  user_id    uuid references public.profiles(id) on delete cascade not null,
  tipo       text not null check (tipo in ('30dias','60dias','90dias','vitalicio')),
  expira     date,
  ativa      boolean default true,
  created_at timestamptz default now()
);

-- 3. Row Level Security
alter table public.profiles enable row level security;
alter table public.licencas enable row level security;

create policy "usuario_ve_proprio_perfil"
  on public.profiles for select
  using (auth.uid() = id);

create policy "usuario_ve_proprias_licencas"
  on public.licencas for select
  using (auth.uid() = user_id);

-- 4. Trigger: cria perfil + licença trial de 30 dias ao registrar
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, nome, email)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'nome', split_part(new.email, '@', 1)),
    new.email
  )
  on conflict (id) do nothing;

  insert into public.licencas (user_id, tipo, expira)
  values (
    new.id,
    '30dias',
    (current_date + interval '30 days')::date
  );

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
