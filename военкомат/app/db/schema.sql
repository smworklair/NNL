-- «Моё дело»: отметки человека по статьям Расписания болезней. Хранятся по Telegram ID, проверенному на сервере.
create table if not exists users (
  tg_id      bigint primary key,
  created_at timestamptz not null default now()
);

create table if not exists delo (
  tg_id       bigint      not null references users (tg_id) on delete cascade,
  article_id  text        not null,
  status      text        not null default 'слово' check (status in ('слово', 'врач')),
  added_at    timestamptz not null default now(),
  step_closed boolean     not null default false,
  primary key (tg_id, article_id)
);

create index if not exists delo_by_user on delo (tg_id, added_at desc);
