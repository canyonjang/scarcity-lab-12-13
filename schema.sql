-- Supabase SQL Editor에서 한 번 실행하십시오.
-- BQ(retire) 테이블은 수정하지 않습니다.
create table if not exists public.scarcity_lab_sessions (
  class_name text primary key,
  experiment text not null default 'rpm' check (experiment in ('rpm', 'heartflower')),
  is_open boolean not null default false,
  reveal boolean not null default false
);
create table if not exists public.scarcity_lab_students (
  class_name text not null,
  student_name text not null,
  primary key (class_name, student_name)
);
create table if not exists public.scarcity_lab_results (
  class_name text not null,
  student_name text not null,
  experiment text not null check (experiment in ('rpm', 'heartflower')),
  trials jsonb not null,
  correct_count integer not null,
  trial_count integer not null,
  accuracy numeric(5,2) not null,
  mean_rt_ms numeric not null,
  submitted_at timestamptz not null default now(),
  primary key (class_name, student_name, experiment)
);
-- 모든 접근은 Streamlit Python 서버에서만 처리하며 Supabase 키를 학생 브라우저에 노출하지 않습니다.
-- 서버에 service_role 비밀키를 SUPABASE_KEY로 설정할 때 아래 RLS 정책으로
-- 공개 REST 접근을 차단하면서 서버의 service_role 접근을 허용할 수 있습니다.
alter table public.scarcity_lab_sessions enable row level security;
alter table public.scarcity_lab_students enable row level security;
alter table public.scarcity_lab_results enable row level security;
-- anon/authenticated를 위한 공개 정책은 만들지 않습니다.
