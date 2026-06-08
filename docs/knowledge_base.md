# Knowledge Base (Postgres + PostgREST + MCP)

База знаний — отдельная database `knowledge` в существующем Postgres-контейнере.
Доступ MCP-серверу `knowledge-mcp` через PostgREST на `https://knowledge.telnor.ru`,
JWT выдаётся backend'ом по логину/паролю админа (`POST /api/auth/knowledge-token`).

## Архитектура

Полный план: [`docs/superpowers/plans/2026-06-06-knowledge-base-postgres.md`](superpowers/plans/2026-06-06-knowledge-base-postgres.md).

Краткая схема:

```
Claude Desktop
  │  stdio MCP
  ▼
knowledge-mcp (Python, локально у пользователя)
  │  HTTPS, JWT
  ▼
PostgREST (Docker, knowledge.telnor.ru)
  │  SQL
  ▼
Postgres `knowledge` database (тот же контейнер что homepage)
```

Backend выдаёт JWT по логину/паролю через `/api/auth/knowledge-token` — только пользователям с `role=admin`. JWT подписывается `KNOWLEDGE_JWT_SECRET` (отдельный от backend `JWT_SECRET`).

## Initial setup на прод (одноразово)

1. Vault уже содержит `vault_knowledge_jwt_secret`.
2. Создать БД на проде (initdb-скрипт не сработает на существующем volume):

   ```bash
   wsl bash -c "cd /mnt/d/Gitlab/home-page/home-page/infra/ansible && \
     ANSIBLE_ROLES_PATH=roles ansible -i inventory/hosts.yml homepage -m shell \
     -a 'docker exec postgres psql -U postgres -c \"CREATE DATABASE knowledge\" || true' \
     --vault-password-file /tmp/vp"
   ```

3. Передеплоить (без тегов — много новых файлов):

   ```bash
   wsl bash -c "cd /mnt/d/Gitlab/home-page/home-page/infra/ansible && \
     ANSIBLE_ROLES_PATH=roles ansible-playbook -i inventory/hosts.yml playbooks/setup.yml \
     --vault-password-file /tmp/vp"
   ```

   Это создаст `postgrest` контейнер, новый Traefik route, новые env-переменные, backend перезапустится с новым endpoint.

4. Применить миграции knowledge на проде:

   ```bash
   wsl bash -c "cd /mnt/d/Gitlab/home-page/home-page && \
     KNOWLEDGE_DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<server>:5432/knowledge \
     cd knowledge && ./.venv/Scripts/python.exe -m alembic upgrade head"
   ```

   (Или альтернативно — скопировать `knowledge/` на сервер через `scp` и применить там.)

5. Запустить миграцию Obsidian → DB (см. ниже).

## Миграция Obsidian → DB

Локально:

```bash
cd tools/migrate_obsidian
KNOWLEDGE_USERNAME=<admin> KNOWLEDGE_PASSWORD=<pass> \
  ./.venv/Scripts/python.exe -m migrate_obsidian "/d/Obsidian Vault/Удивительная жизнь Никиты" \
  --knowledge-url https://knowledge.telnor.ru \
  --backend-url https://api.telnor.ru
```

Проверить:

```bash
TOKEN=$(curl -s https://api.telnor.ru/api/auth/knowledge-token \
  -H "Content-Type: application/json" \
  -d '{"username":"<admin>","password":"<pass>"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN" -H "Prefer: count=exact" \
  "https://knowledge.telnor.ru/notes?limit=0" -I | grep -i content-range
```

Ожидается: `Content-Range: 0-0/86` (или сколько у тебя .md в vault).

## Установка knowledge-mcp + Claude Desktop config

```bash
cd /d/Gitlab/home-page/home-page/knowledge-mcp
python -m pip install -e .
```

Открыть `%APPDATA%\Claude\claude_desktop_config.json` и добавить:

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "knowledge-mcp",
      "env": {
        "KNOWLEDGE_URL": "https://knowledge.telnor.ru",
        "KNOWLEDGE_BACKEND_URL": "https://api.telnor.ru",
        "KNOWLEDGE_USERNAME": "<твой admin username>",
        "KNOWLEDGE_PASSWORD": "<твой пароль>"
      }
    }
  }
}
```

Полный quit Claude Desktop (System tray → Quit) и запустить заново. В чате: «Список всех ноутбуков». Claude вызывает `list_notebooks` → 2 ноутбука.

## Смена пароля админа

Меняется через `POST /api/auth/change-password` (или admin UI). После смены — обнови `KNOWLEDGE_PASSWORD` в `claude_desktop_config.json` и перезапусти Claude Desktop. MCP-клиент сам перелогинится.

## Ротация `KNOWLEDGE_JWT_SECRET`

1. Сгенерировать новый: `openssl rand -base64 48`
2. Перешифровать в vault:
   ```bash
   cd infra/ansible
   ansible-vault encrypt_string '<новый>' --name vault_knowledge_jwt_secret
   ```
3. Заменить блок `vault_knowledge_jwt_secret` в `inventory/group_vars/all/vault.yml`.
4. Передеплоить backend + postgrest:
   ```bash
   ansible-playbook -i inventory/hosts.yml playbooks/setup.yml --tags backend,postgrest
   ```
   Старые JWT мгновенно становятся невалидными (401 от PostgREST), MCP-клиент сам получит новый при первом 401.

## Бэкап + восстановление

Knowledge данные бэкапятся cron'ом каждую ночь в `knowledge_YYYY-MM-DD.dump.gz` вместе с homepage (см. `infra/docker/cron/backup.sh`). Ротация 14 дней.

Восстановление knowledge:

```bash
docker exec postgres psql -U postgres -c "DROP DATABASE knowledge"
docker exec postgres psql -U postgres -c "CREATE DATABASE knowledge"
cat knowledge_YYYY-MM-DD.dump.gz | gunzip \
  | docker exec -i postgres pg_restore -U postgres -d knowledge
```

## Откат миграции Obsidian

```bash
TOKEN=$(...)  # см. выше
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  "https://knowledge.telnor.ru/notebooks"  # truncate всех ноутбуков (CASCADE)
```

Затем повторно `python -m migrate_obsidian ...`.
