# Cloudflare Worker Telegram relay

Worker принимает только `POST <TELEGRAM_RELAY_URL>/<method>` с заголовком
`X-Relay-Key` и телом `application/json` или `multipart/form-data`. Токен бота
добавляется к upstream URL только внутри Worker; в конфигурации и клиентских URL
его быть не должно.

## Настройка перед деплоем

1. Выбрать имя Worker и заменить заглушку `change-me-telegram-relay-name` в
   `wrangler.toml`. Адрес Worker будет выдан Cloudflare после деплоя; заранее он
   здесь не задаётся.
2. Выполнить в этом каталоге и ввести значения интерактивно, не помещая их в
   командную строку или файлы:

   ```sh
   npx wrangler@4.151.3 secret put BOT_TOKEN
   npx wrangler@4.151.3 secret put RELAY_KEY
   ```

3. Деплой выполняет Никита отдельной командой после выбора имени:

   ```sh
   npx wrangler@4.151.3 deploy
   ```

## Локальная проверка

Тесты используют встроенный `node:test`, установка зависимостей для них не нужна:

```sh
npm test
npx wrangler@4.151.3 deploy --dry-run
```

`getUpdates.timeout` принимает значения от 0 до 10 секунд: long polling должен
завершаться до общего 15-секундного timeout upstream-запроса.
