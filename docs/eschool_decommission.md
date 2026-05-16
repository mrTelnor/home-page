# Электронный дневник — отказ от интеграции

В мае 2026 была реализована интеграция с `app.eschool.center`
(HTTP-клиент с cookie-аутентификацией, парсеры ДЗ и оценок,
расписание дайджестов и push-уведомлений в Telegram).
От доведения до прода отказались по следующим причинам:

1. **reCAPTCHA на login.** `/ec-server/login` блокируется капчей,
   автоматический логин по login/password невозможен — пришлось
   переходить на ручные cookies из браузера.
2. **Короткий TTL cookies.** Сессия eschool протухает за часы,
   не дни — ручное обновление требуется слишком часто, чтобы это
   было полезно.
3. **Нестабильная структура API.** Поля в реальных ответах
   отличаются от тестовых (camelCase vs lowercase ID, ISO-строка
   vs миллисекунды), парсер постоянно ломается.
4. **Польза vs трудозатраты.** Цена поддержки превышает выгоду —
   проще зайти в стандартный UI eschool напрямую.

## Удалённые компоненты

- `bot/app/eschool/` (клиент, парсер, форматтеры, сервис)
- `/check-eschool` endpoint и три cron-задачи
  (`homework_digest`, `homework_push`, `grades_digest`)
- Backend-endpoints `/api/auth/users/admin-volkovs` и
  `/api/auth/users/by-eschool-prs-id/{prs_id}`, связанные сервисы
  и схемы (`EschoolUserResponse`, `get_user_by_eschool_prs_id`,
  `get_admin_volkov_users`)
- ENV: `ESCHOOL_COOKIES`, `ESCHOOL_LOGIN`, `ESCHOOL_PASSWORD`
  и соответствующие vault-переменные
- Старые research-документы (`docs/eschool_api_research.md`,
  `docs/eschool_telegram_research.md`)

## Что оставлено в БД

Колонка `auth.users.eschool_prs_id` (миграция `006_add_eschool_prs_id`)
**не откатывается** — данных в ней нет (всё `NULL`), ORM-модель
сохраняет соответствие схеме БД. Если в будущем интеграцию решат
возродить — колонка готова к использованию.

## Если возвращаться к интеграции

Возрождать имеет смысл только при одном из условий:
- eschool снимет капчу с `/ec-server/login` и появится возможность
  автоматического логина;
- eschool выпустит OAuth/API-токены или официальный API;
- появится способ продлевать сессию без ручного похода в браузер.

История разработки сохранена в git до коммита, удаляющего эти
компоненты, — можно вернуться через `git log --diff-filter=D
--name-only | grep eschool`.
