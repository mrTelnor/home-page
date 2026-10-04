-- --------------------------------------------------
-- Роль wiki_reader: чтение базы знаний (Supabase) для backend вики
-- Проект Supabase: vcfqubocjfnzebpiwczw, схема public
-- Задача: https://tracker.telnor.ru/tasks/9 (родительская — /tasks/7)
-- --------------------------------------------------
--
-- Как выполнять (делает Никита, агент этот файл через MCP не выполняет — G108):
--   1. Скопировать файл в SQL Editor Supabase и выполнить целиком (Run).
--      Пароля в файле нет: роль создаётся без пароля и войти под ней нельзя,
--      пока пароль не задан отдельно (см. ниже).
--   2. Задать пароль роли через psql — процедура «Задать / сменить пароль».
--
-- Задать / сменить пароль (только через psql, не через SQL Editor):
--   Пароль в тексте SQL писать нельзя: запрос с открытым паролем остаётся
--   в pg_stat_statements, в логе Postgres и в сохранённых запросах SQL Editor.
--   Команда \password хеширует пароль на стороне клиента — на сервер уходит
--   готовый SCRAM-хеш.
--   1. Сгенерировать пароль: только буквы и цифры (он попадёт в строку
--      подключения), не короче 24 символов — SCRAM-хеш пароля остаётся в логе
--      Postgres и в pg_stat_statements, от перебора защищает только длина.
--      Хранить в Ansible Vault — vault_wiki_db_password.
--   2. Подключиться под postgres через пулер (session, порт 5432); пароль базы
--      psql спросит сам. Нужен psql 10+ с поддержкой SSL (psql из .superpowers
--      собран без SSL и не подходит). На рабочем ПК — из образа postgres:16
--      в докере WSL (PowerShell):
--        wsl docker run --rm -it postgres:16 psql "host=aws-1-eu-central-1.pooler.supabase.com port=5432 dbname=postgres user=postgres.vcfqubocjfnzebpiwczw sslmode=require"
--   3. В psql выполнить и дважды ввести пароль wiki_reader:
--        \password wiki_reader
--   После смены пароля пулер может какое-то время отказывать в подключении
--   со старым и новым паролем (кэш учётных данных Supavisor — не проверено).
--
-- Идемпотентность: файл можно выполнять повторно. Повторный запуск приводит
-- атрибуты, ограничения, права и политики роли к описанным здесь и пароль
-- не трогает.
--
-- Что файл НЕ делает:
--   - не задаёт и не меняет пароль роли;
--   - не даёт прав на схему backup (снимок таблиц от 2026-09-30);
--   - не меняет права anon / authenticated / service_role;
--   - не меняет схему базы (таблицы, view, триггеры).

begin;

-- --------------------------------------------------
-- 1. Роль
-- --------------------------------------------------
-- Создаётся без пароля, если её нет. Существующая роль и её пароль остаются.

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'wiki_reader') then
        create role wiki_reader login;
    end if;
end
$$;

-- Атрибуты приводятся к эталону при каждом запуске — и для новой роли,
-- и для существующей. NOSUPERUSER здесь нет намеренно: менять этот атрибут
-- может только суперпользователь, а postgres в Supabase им не является
-- (по той же причине выдать SUPERUSER этой роли некому).
alter role wiki_reader with
    login
    nocreatedb
    nocreaterole
    noreplication
    nobypassrls;

-- --------------------------------------------------
-- 2. Ограничения роли
-- --------------------------------------------------
-- Лимит соединений: при пересоздании контейнера backend старый и новый пулы
-- живут одновременно (3 + 3), поэтому pool_size + max_overflow пула вики
-- в backend должен быть не больше 3. Для ручной проверки через psql при
-- работающем backend остаётся 3 соединения.
alter role wiki_reader connection limit 6;

-- Транзакции по умолчанию только на чтение. Это страховка, а не защита:
-- параметр можно переопределить в сессии. Защита — отсутствие прав на запись
-- (шаг 3) и политики только на SELECT (шаг 4).
alter role wiki_reader set default_transaction_read_only = on;

-- Тяжёлый запрос не должен держать соединение из маленького пула.
alter role wiki_reader set statement_timeout = '5s';

-- --------------------------------------------------
-- 3. Права: только чтение шести объектов схемы public
-- --------------------------------------------------
grant usage on schema public to wiki_reader;

grant select on table
    public.notebooks,
    public.notes,
    public.tags,
    public.note_tags,
    public.note_links,
    public.backlinks_view
to wiki_reader;

-- --------------------------------------------------
-- 4. Политики чтения (RLS включён на всех пяти таблицах)
-- --------------------------------------------------
-- Строго TO wiki_reader: у anon и authenticated полные GRANT на эти таблицы,
-- и их сейчас останавливает только отсутствие политик. Политика TO public
-- открыла бы им чтение через публичный ключ.
--
-- backlinks_view создан с security_invoker = true: запрос к view выполняется
-- с правами вызывающей роли, поэтому чтение через view идёт по этим же
-- политикам на notes и note_links. Отдельной политики для view не нужно.

drop policy if exists wiki_reader_select on public.notebooks;
create policy wiki_reader_select on public.notebooks
    for select to wiki_reader using (true);

drop policy if exists wiki_reader_select on public.notes;
create policy wiki_reader_select on public.notes
    for select to wiki_reader using (true);

drop policy if exists wiki_reader_select on public.tags;
create policy wiki_reader_select on public.tags
    for select to wiki_reader using (true);

drop policy if exists wiki_reader_select on public.note_tags;
create policy wiki_reader_select on public.note_tags
    for select to wiki_reader using (true);

drop policy if exists wiki_reader_select on public.note_links;
create policy wiki_reader_select on public.note_links
    for select to wiki_reader using (true);

commit;

-- --------------------------------------------------
-- Проверка после выполнения (под postgres, в SQL Editor)
-- --------------------------------------------------
-- Роль: rolcanlogin = true, rolconnlimit = 6, остальные флаги false,
-- в rolconfig — default_transaction_read_only=on и statement_timeout=5s.
--
-- select rolname, rolcanlogin, rolsuper, rolcreaterole, rolcreatedb,
--        rolreplication, rolbypassrls, rolconnlimit, rolconfig
-- from pg_roles where rolname = 'wiki_reader';
--
-- Политики: ровно пять строк, все SELECT и {wiki_reader}.
--
-- select tablename, policyname, cmd, roles, qual
-- from pg_policies where schemaname = 'public' order by tablename;
--
-- Права: шесть строк, только SELECT.
--
-- select table_schema, table_name, privilege_type
-- from information_schema.role_table_grants
-- where grantee = 'wiki_reader' order by 1, 2, 3;
--
-- Схема backup недоступна: false.
--
-- select has_schema_privilege('wiki_reader', 'backup', 'USAGE');

-- --------------------------------------------------
-- Откат (выполнять вручную, раскомментировав блок целиком)
-- --------------------------------------------------
-- Перед откатом остановить обращения backend к вики: открытые соединения
-- роли будут разорваны.
-- После отката убрать из репозитория то, что ссылается на роль (когда оно
-- появится): vault_wiki_db_password в Ansible Vault и строку подключения вики
-- в env.j2.
--
-- begin;
--
-- select pg_terminate_backend(pid) from pg_stat_activity where usename = 'wiki_reader';
--
-- drop policy if exists wiki_reader_select on public.notebooks;
-- drop policy if exists wiki_reader_select on public.notes;
-- drop policy if exists wiki_reader_select on public.tags;
-- drop policy if exists wiki_reader_select on public.note_tags;
-- drop policy if exists wiki_reader_select on public.note_links;
--
-- do $$
-- begin
--     if exists (select 1 from pg_roles where rolname = 'wiki_reader') then
--         revoke select on table
--             public.notebooks,
--             public.notes,
--             public.tags,
--             public.note_tags,
--             public.note_links,
--             public.backlinks_view
--         from wiki_reader;
--         revoke usage on schema public from wiki_reader;
--         drop role wiki_reader;
--     end if;
-- end
-- $$;
--
-- commit;
