# Дополнения для базы знаний — 2026-10-01 (не внесены)

> Запись в базу знаний из Claude Code не прошла (`execute_sql` → `declined` на шаге подтверждения).
> Ниже — текст, который нужно дописать **в конец** трёх существующих заметок, и связи `note_links`.
> После внесения файл можно удалить.

## 1. Заметка «RuSender — интеграция email»

Slug `moi-domashnii-sait/rusender-email`, id `46c8e8bd-b916-4149-aa76-2d04b9b8282b`. Дописать в конец:

```markdown
## 2026-10-01 — SMTP для трекера Vikunja

Vikunja шлёт почту только по SMTP, поэтому для трекера используется SMTP-релей RuSender (HTTP API остаётся для сброса пароля). Задача трекера: Vikunja id 2 «Трекер: оповещения Vikunja по почте», коммит `acdb6b6`.

- Хост/порт: `smtp.rusender.ru:465`, неявный TLS — `VIKUNJA_MAILER_FORCESSL=true` (в Vikunja 2.6.0 `forcessl` = implicit TLS). Хост и порт заданы прямо в `infra/docker/docker-compose.yml` (сервис `vikunja`).
- Секреты: `vault_vikunja_smtp_username` / `vault_vikunja_smtp_password` → `env.j2` (`VIKUNJA_SMTP_USERNAME` / `VIKUNJA_SMTP_PASSWORD`) → `VIKUNJA_MAILER_USERNAME` / `VIKUNJA_MAILER_PASSWORD`.
- Отправитель: `VIKUNJA_MAILER_FROMEMAIL` — голый адрес, извлекается в `env.j2` из `vault_email_from` (`noreply@telnor.ru`); имя «Vikunja» трекер подставляет сам (G107).
- Получатель — email из профиля учётки Vikunja, отдельно не настраивается. Письма о назначении и комментариях уходят без отдельного выключателя; напоминания и ежедневная сводка просрочек включаются флажками в «Основных настройках» профиля.
- Проверка SMTP: `docker exec vikunja /app/vikunja/vikunja testmail <адрес>`. Проверка цепочки уведомлений — назначить задачу на пользователя (2026-10-01: письмо и Telegram пришли, письмо не в спаме).
- Исходящий SMTP с ВМ Timeweb по умолчанию закрыт — G105, G106 в [[Грабли home-page]]. История диагностики — [[Handoff 2026-10-01 — почта Vikunja через SMTP RuSender (ждём Timeweb)]].
```

## 2. Заметка «Грабли home-page»

Slug `moi-domashnii-sait/grabli`, id `5ec51f12-aa14-4691-9b21-dead17982145`. Три строки в конец таблицы (после G104):

```markdown
| G105 | Timeweb Cloud по умолчанию блокирует исходящий SMTP с ВМ (25/465/587/2525) | `dial tcp <ip>:465: i/o timeout` (таймаут, не refused); закрыты SMTP-порты ко всем почтовым хостам сразу, 443 открыт. Облачного firewall в панели нет, файрвол ВМ исходящий трафик не фильтрует | Диагностика: `for p in 465 587 25 2525 443; do timeout 5 bash -c "</dev/tcp/<host>/$p" && echo open \|\| echo closed; done` к нескольким хостам (smtp.gmail.com, smtp.yandex.ru, целевой). Закрыто везде — заявка в поддержку Timeweb на открытие исходящего 465; конфиг не трогать. См. [[RuSender — интеграция email]] (2026-10-01) |
| G106 | Timeweb снял блокировку SMTP не полностью: после ответа поддержки «порт 465 разблокирован» соединение до `smtp.rusender.ru` всё ещё не проходило | 465 до smtp.gmail.com и smtp.yandex.ru открыт, а до `smtp.rusender.ru` (185.86.93.251) 465/587 в таймауте; из другой сети те же порты открыты; `mtr -T -P 465` теряет пакеты на последнем хопе, `-P 443` доходит. Сервер RuSender, судя по маршруту (1 мс, сразу за `92.53.93.53`), стоит в сети Timeweb. Проблема была на стороне Timeweb — устранена их поддержкой по повторному обращению Никиты (2026-10-01) | Не менять конфиг и не искать ошибку у себя и у RuSender: сравнить `sudo mtr -T -P 465 -n -r -c 3 <host>` с `-P 443`, проверить порт из другой сети (`Test-NetConnection <host> -Port 465`) и вернуться в тот же тикет Timeweb с этими выводами. См. [[RuSender — интеграция email]] (2026-10-01) |
| G107 | `VIKUNJA_MAILER_FROMEMAIL` — только адрес, без имени | Если передать `Имя <адрес>` (как в `vault_email_from`), отправитель получится `Vikunja <Telnor <noreply@…>>` — Vikunja сама добавляет имя | В `env.j2` извлекать адрес: `regex_replace('^.*<([^>]+)>.*$', '\\1')`. См. [[RuSender — интеграция email]] (2026-10-01) |
```

## 3. Заметка «Трекер Vikunja — структура доски и подключение MCP»

Slug `rabota-s-claude/vikunja-struktura-i-mcp`, id `57e9577c-972a-4e47-99cd-e6d8b71e6204`. Дописать в конец:

````markdown
---
## 2026-10-01 — перенос задач между корзинами

В `@aimbitgmbh/vikunja-mcp` нет инструмента переноса задачи между корзинами (`tasks_update` / `tasks_bulk_update` корзину не принимают; `tasks_create` кладёт в корзину по умолчанию). Рабочий способ — прямой вызов API с токеном учётки агента из `VIKUNJA_API_TOKEN`:

```powershell
Invoke-RestMethod -Method Post -Uri "https://tracker.telnor.ru/api/v1/projects/<project>/views/<view>/buckets/<bucket>/tasks" -Headers @{ Authorization = "Bearer $env:VIKUNJA_API_TOKEN" } -ContentType "application/json" -Body '{"task_id":<id>}'
```

id проектов, видов и корзин — в таблице выше. Проверено 2026-10-01: задача id 2 проекта `home-page` → «На проверке» (view 32, bucket 42). Прочее: `tasks_get`, `tasks_create`, `task_assignees_add`, `task_comments_create`, `project_views_list` с Vikunja 2.6.0 работают. В `tasks_get` поле `id` — числовой id задачи, а `identifier` (`#N`) — номер внутри проекта, они не совпадают (задача id 2 = `#1`).
````

## 4. Связи `note_links`

| Откуда | Куда |
|---|---|
| RuSender — интеграция email (`46c8e8bd-b916-4149-aa76-2d04b9b8282b`) | Грабли home-page (`5ec51f12-aa14-4691-9b21-dead17982145`) |
| RuSender — интеграция email (`46c8e8bd-b916-4149-aa76-2d04b9b8282b`) | Handoff 2026-10-01 — почта Vikunja… (`b710bd39-6277-4570-820d-32c52ea0c026`) |
| Грабли home-page (`5ec51f12-aa14-4691-9b21-dead17982145`) | RuSender — интеграция email (`46c8e8bd-b916-4149-aa76-2d04b9b8282b`) |

```sql
insert into note_links (source_note_id, target_note_id)
select s, t from (values
 ('46c8e8bd-b916-4149-aa76-2d04b9b8282b'::uuid, '5ec51f12-aa14-4691-9b21-dead17982145'::uuid),
 ('46c8e8bd-b916-4149-aa76-2d04b9b8282b'::uuid, 'b710bd39-6277-4570-820d-32c52ea0c026'::uuid),
 ('5ec51f12-aa14-4691-9b21-dead17982145'::uuid, '46c8e8bd-b916-4149-aa76-2d04b9b8282b'::uuid)
) v(s, t)
where not exists (select 1 from note_links l where l.source_note_id = v.s and l.target_note_id = v.t);
```
