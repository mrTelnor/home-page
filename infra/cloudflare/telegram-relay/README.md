# Cloudflare Worker Telegram relay

Worker принимает только `POST <TELEGRAM_RELAY_URL>/<method>` с заголовком
`X-Relay-Key` и телом `application/json` или `multipart/form-data`. Токен бота
добавляется к upstream URL только внутри Worker; в конфигурации и клиентских URL
его быть не должно.

## Настройка и деплой

1. Выбрать имя Worker в `name` файла `wrangler.toml` (сейчас —
   `home-page-telegram-relay`). Адрес Worker будет выдан Cloudflare после деплоя;
   заранее он здесь не задаётся.
2. Если Wrangler ещё не авторизован, выполнить в этом каталоге:

   ```sh
   npx --yes wrangler@4.151.3 login
   ```

3. Выполнить первый деплой:

   ```sh
   npx --yes wrangler@4.151.3 deploy
   ```

4. После первого деплоя задать секреты, вводя значения интерактивно, не помещая
   их в командную строку или файлы. `secret put` создаёт новую версию существующего
   Worker и сразу развёртывает её:

   ```sh
   npx --yes wrangler@4.151.3 secret put BOT_TOKEN
   npx --yes wrangler@4.151.3 secret put RELAY_KEY
   ```

## Локальная проверка

Тесты используют встроенный `node:test`, установка зависимостей для них не нужна:

```sh
npm test
npx wrangler@4.151.3 deploy --dry-run
```

`getUpdates.timeout` принимает значения от 0 до 10 секунд: long polling должен
завершаться до общего 15-секундного timeout upstream-запроса.
