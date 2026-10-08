# База знаний (Supabase)

Личная база знаний — зеркало Obsidian-хранилища «Удивительная жизнь Никиты»,
перенесённое в **Supabase** (managed Postgres). Пишут в неё агенты через
Supabase MCP-сервер, подключённый в Claude / Claude Code; люди читают на
`wiki.telnor.ru` (см. «Доступ вики»).

> Это отдельный от веб-сервиса `home-page` контур: к рецептам/голосованию он
> отношения не имеет, живёт в собственном Supabase-проекте. Сайт только читает
> её для вики.

## История (почему Supabase, а не self-hosted)

Изначально (июнь 2026) база знаний разворачивалась self-hosted: отдельная БД
`knowledge` в том же Postgres-контейнере, REST поверх PostgREST на
`knowledge.telnor.ru`, JWT от backend (`POST /api/auth/knowledge-token`),
MCP-сервер `knowledge-mcp` и одноразовый мигратор `tools/migrate_obsidian`.

От этого подхода отказались — слишком много движущихся частей ради личной базы
заметок (свой контейнер PostgREST, свой Traefik-route и сертификат, отдельный
JWT-секрет и его ротация, кастомная роль `knowledge_rw`, локальная установка
`knowledge-mcp` в Claude Desktop, дублирование в бэкапах). Supabase закрывает всё
это из коробки: managed Postgres с PostgREST, готовый MCP-сервер, бэкапы,
аутентификация.

Весь self-hosted-код удалён из репозитория, БД `knowledge` на ВМ выведена из
эксплуатации. Исходный план — [`docs/superpowers/plans/2026-06-06-knowledge-base-postgres.md`](superpowers/plans/2026-06-06-knowledge-base-postgres.md)
(помечен устаревшим).

## Где живут данные

Supabase-проект `vcfqubocjfnzebpiwczw`, схема `public`. Полная реляционная модель
(перенесена 1:1 из self-hosted-схемы):

| Объект | Назначение |
|---|---|
| `notebooks` | папки; иерархия через `parent_id` (self-FK, ON DELETE CASCADE) |
| `notes` | заметки: `title`, `slug` (уникальный), `content` (markdown), `metadata` (JSONB из frontmatter), `search_vector` (TSVECTOR) |
| `tags`, `note_tags` | теги и M:N-связь с заметками |
| `note_links` | wiki-ссылки `[[...]]` как рёбра графа (`source`→`target`, опц. `alias`) |
| `backlinks_view` | view обратных ссылок (`security_invoker`) |

- **Полнотекстовый поиск:** `search_vector` заполняется триггером
  `notes_search_vector_update` (конфиг `simple` — работает с RU/EN, title=A,
  content=B), GIN-индекс `idx_notes_search`.
- **RLS** включён на всех таблицах. Политик для `anon` и `authenticated` нет и
  быть не должно: у этих ролей в Supabase полные `GRANT`, их останавливает только
  отсутствие политик. Запись — через `service_role` (Supabase MCP / Dashboard),
  чтение для вики — отдельной ролью `wiki_reader`.

## Доступ вики (роль `wiki_reader`)

Backend сайта читает базу для вики ролью Postgres `wiki_reader`. Роль создаётся
файлом [`infra/supabase/wiki_reader.sql`](../infra/supabase/wiki_reader.sql)
(идемпотентный, выполняется вручную в SQL Editor):

- `login`, без `createdb` / `createrole` / `replication` / `bypassrls`,
  `connection limit 6`, `default_transaction_read_only = on`,
  `statement_timeout = 5s`;
- `USAGE` на схему `public` и `SELECT` на `notebooks`, `notes`, `tags`,
  `note_tags`, `note_links`, `backlinks_view`; на остальное, включая схему
  `backup`, прав нет;
- пять политик `wiki_reader_select` — `FOR SELECT TO wiki_reader USING (true)`,
  по одной на таблицу. `backlinks_view` создан с `security_invoker`, поэтому
  читается по тем же политикам и своей не требует.

Пароля в файле нет: он задаётся отдельно командой `\password wiki_reader` в psql,
чтобы открытый текст не попал в `pg_stat_statements` и лог Postgres. Хранится в
Ansible Vault (`vault_wiki_db_password`).

Подключение — через пулер Supabase в session-режиме, пользователь
`wiki_reader.<ref проекта>`; параметры — `vault_wiki_db_*`, строка собирается в
`env.j2` в переменную `WIKI_DATABASE_URL`. Как backend ей пользуется — в
[architecture.md](architecture.md), раздел «Вики».

Проверять запрет записи под этой ролью нужно в `begin read write … rollback`:
обычный `insert` отклоняется режимом «только чтение», который сессия может снять,
и о правах ничего не говорит.

Бесплатный проект Supabase уходит в паузу от простоя — cron раз в сутки
запрашивает `/api/wiki/health` (`wiki-wake.sh`).

## Доступ из Claude

Через Supabase MCP:

- структура БД — `list_tables`;
- чтение/поиск — `execute_sql`. Полнотекстовый поиск:
  ```sql
  select title, slug, ts_rank(search_vector, q) rank
  from notes, to_tsquery('simple', 'argocd') q
  where search_vector @@ q order by rank desc;
  ```
- обратные ссылки — `select * from backlinks_view where target_slug = '...'`;
- изменения схемы — `apply_migration`.

## Миграция из Obsidian (как это делалось)

Перенос выполнен из vault `D:\Obsidian Vault\Удивительная жизнь Никиты`:

- папки верхнего уровня → `notebooks`; файлы `.md` в корне vault → ноутбук
  «Разное» (`raznoe`);
- каждый `.md` → `notes` (`title` = имя файла, `slug` = путь со slug-ификацией и
  кириллической транслитерацией, `content` = тело без frontmatter,
  `metadata` = frontmatter как JSONB);
- frontmatter-теги и инлайновые `#tag` → `tags` + `note_tags`;
- `[[wikilink|alias]]` → `note_links` (резолв по точному заголовку-цели;
  неразрешённые ссылки на заголовки/пути пропускаются).

С тех пор база пополняется агентами напрямую; актуальные числа — запросом
`count(*)`.

Повторная миграция (если Obsidian правился) — заново собрать `INSERT`'ы из vault
и применить к Supabase напрямую (session pooler) или через `apply_migration`.
Одноразовый мигратор намеренно не хранится в репозитории.

## Бэкап

Данные бэкапятся средствами Supabase (Dashboard → Database → Backups). Отдельный
`pg_dump` в cron, который раньше дампил `knowledge` вместе с `homepage`, удалён —
теперь cron бэкапит только `homepage` на Я.Диск.
