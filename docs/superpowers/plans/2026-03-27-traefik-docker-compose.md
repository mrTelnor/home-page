# Traefik + Docker Compose Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Развернуть базовую инфраструктуру Docker Compose с Traefik v3, PostgreSQL 16 и Portainer CE.

**Architecture:** Traefik v3 как reverse proxy с автоматическим SSL через Let's Encrypt. Статический конфиг в `traefik.yml`, роутинг сервисов через Docker labels. Две Docker-сети: `web` (публичная) и `internal` (БД). Доступ к PostgreSQL — через десктопный клиент, порт 5432 ограничен firewalld по IP. Админ-панели (Traefik, Portainer) ограничены по IP через Traefik middleware.

**Tech Stack:** Traefik v3.3, PostgreSQL 16, Portainer CE, Docker Compose

---

### Task 1: Создать .env.example

**Files:**
- Create: `infra/docker/.env.example`

- [ ] **Step 1: Создать файл .env.example**

```env
# PostgreSQL
POSTGRES_USER=homepage
POSTGRES_PASSWORD=changeme
POSTGRES_DB=homepage

# Domain
DOMAIN=telnor.ru
ACME_EMAIL=mrtelnor@gmail.com

# IP whitelist for admin panels
HOME_IP=93.100.230.103
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/.env.example
git commit -m "feat(infra): add .env.example for Docker Compose"
```

---

### Task 2: Создать статический конфиг Traefik

**Files:**
- Create: `infra/docker/traefik/traefik.yml`

- [ ] **Step 1: Создать файл traefik.yml**

```yaml
api:
  dashboard: true

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https

  websecure:
    address: ":443"

certificatesResolvers:
  letsencrypt:
    acme:
      email: mrtelnor@gmail.com
      storage: /letsencrypt/acme.json
      httpChallenge:
        entryPoint: web

providers:
  docker:
    exposedByDefault: false

log:
  level: WARN
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/traefik/traefik.yml
git commit -m "feat(infra): add Traefik v3 static config"
```

---

### Task 3: Создать docker-compose.yml с сервисом Traefik

**Files:**
- Create: `infra/docker/docker-compose.yml`

- [ ] **Step 1: Создать docker-compose.yml с Traefik**

```yaml
networks:
  web:
    name: web
  internal:
    name: internal

volumes:
  letsencrypt:
  pg_data:
  portainer_data:

services:
  traefik:
    image: traefik:v3.3
    container_name: traefik
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik/traefik.yml:/etc/traefik/traefik.yml:ro
      - letsencrypt:/letsencrypt
    networks:
      - web
    labels:
      # Dashboard
      - traefik.enable=true
      - traefik.http.routers.traefik.rule=Host(`traefik.${DOMAIN}`)
      - traefik.http.routers.traefik.entrypoints=websecure
      - traefik.http.routers.traefik.tls.certresolver=letsencrypt
      - traefik.http.routers.traefik.service=api@internal
      # IP whitelist
      - traefik.http.routers.traefik.middlewares=admin-ip@docker
      - traefik.http.middlewares.admin-ip.ipallowlist.sourcerange=${HOME_IP}/32
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/docker-compose.yml
git commit -m "feat(infra): add docker-compose with Traefik service"
```

---

### Task 4: Добавить PostgreSQL в docker-compose.yml

**Files:**
- Modify: `infra/docker/docker-compose.yml`

- [ ] **Step 1: Добавить сервис PostgreSQL**

Добавить в секцию `services` после `traefik`:

```yaml
  postgres:
    image: postgres:16
    container_name: postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
    networks:
      - internal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/docker-compose.yml
git commit -m "feat(infra): add PostgreSQL 16 service"
```

---

### Task 5: Добавить Portainer CE в docker-compose.yml

**Files:**
- Modify: `infra/docker/docker-compose.yml`

- [ ] **Step 1: Добавить сервис Portainer**

Добавить в секцию `services` после `postgres`:

```yaml
  portainer:
    image: portainer/portainer-ce
    container_name: portainer
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - portainer_data:/data
    networks:
      - web
    labels:
      - traefik.enable=true
      - traefik.http.routers.portainer.rule=Host(`portainer.${DOMAIN}`)
      - traefik.http.routers.portainer.entrypoints=websecure
      - traefik.http.routers.portainer.tls.certresolver=letsencrypt
      - traefik.http.routers.portainer.middlewares=admin-ip@docker
      - traefik.http.services.portainer.loadbalancer.server.port=9000
```

- [ ] **Step 2: Commit**

```bash
git add infra/docker/docker-compose.yml
git commit -m "feat(infra): add Portainer CE service"
```

---

### Task 6: Добавить правило firewalld для PostgreSQL

**Files:**
- Modify: `infra/ansible/roles/firewalld/tasks/main.yml`

- [ ] **Step 1: Добавить rich rule для порта 5432**

Добавить в конец файла `infra/ansible/roles/firewalld/tasks/main.yml` (перед таском удаления SSH 22):

```yaml
- name: Allow PostgreSQL only from home IP
  ansible.posix.firewalld:
    rich_rule: 'rule family="ipv4" source address="{{ home_ip }}" port port="5432" protocol="tcp" accept'
    permanent: true
    immediate: true
    state: enabled
```

- [ ] **Step 2: Добавить переменную home_ip в vault.yml**

Добавить в `infra/ansible/inventory/group_vars/all/vault.yml`:

```
vault_home_ip: "93.100.230.103"
```

Зашифровать:

```bash
ansible-vault encrypt_string '93.100.230.103' --name 'vault_home_ip'
```

- [ ] **Step 3: Добавить маппинг переменной в hosts.yml**

В `infra/ansible/inventory/group_vars/all/` создать `vars.yml`:

```yaml
home_ip: "{{ vault_home_ip }}"
```

- [ ] **Step 4: Commit**

```bash
git add infra/ansible/roles/firewalld/tasks/main.yml infra/ansible/inventory/group_vars/all/vars.yml
git commit -m "feat(infra): add firewalld rule for PostgreSQL access by home IP"
```

---

### Task 7: Деплой на ВМ и проверка

**Files:**
- Modify: `infra/ansible/playbooks/setup.yml` — добавить роль app
- Create: `infra/ansible/roles/app/tasks/main.yml` — роль деплоя

- [ ] **Step 1: Создать роль app для деплоя**

`infra/ansible/roles/app/tasks/main.yml`:

```yaml
---
- name: Create app directory
  file:
    path: /opt/home-page
    state: directory
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"

- name: Create traefik config directory
  file:
    path: /opt/home-page/traefik
    state: directory
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"

- name: Copy docker-compose.yml
  copy:
    src: ../../../docker/docker-compose.yml
    dest: /opt/home-page/docker-compose.yml
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"

- name: Copy traefik.yml
  copy:
    src: ../../../docker/traefik/traefik.yml
    dest: /opt/home-page/traefik/traefik.yml
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"

- name: Copy .env file
  copy:
    src: ../../../docker/.env
    dest: /opt/home-page/.env
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: "0600"

- name: Start services
  community.docker.docker_compose_v2:
    project_src: /opt/home-page
    state: present
  become_user: "{{ ansible_user }}"
```

- [ ] **Step 2: Добавить роль app в setup.yml**

```yaml
---
# Subsequent runs (SSH already on port 9922):
#   ansible-playbook -i inventory/hosts.yml playbooks/setup.yml

- name: Setup Home Page server
  hosts: homepage
  become: true

  roles:
    - docker
    - firewalld
    - app
```

- [ ] **Step 3: Создать .env на основе .env.example**

```bash
cp infra/docker/.env.example infra/docker/.env
# Заполнить реальными значениями
```

- [ ] **Step 4: Настроить DNS**

В панели управления доменом `telnor.ru` добавить A-записи:

| Запись | Тип | Значение |
|---|---|---|
| `traefik.telnor.ru` | A | `147.45.183.98` |
| `portainer.telnor.ru` | A | `147.45.183.98` |

- [ ] **Step 5: Запустить деплой**

```bash
cd infra/ansible
ansible-playbook -i inventory/hosts.yml playbooks/setup.yml
```

- [ ] **Step 6: Проверить работу сервисов**

```bash
# На ВМ
docker ps

# С домашнего ПК
curl -I https://traefik.telnor.ru
curl -I https://portainer.telnor.ru

# Проверка PostgreSQL (из десктопного pgAdmin)
# Host: 147.45.183.98, Port: 5432, User/Password из .env
```

Ожидаемый результат:
- `traefik.telnor.ru` и `portainer.telnor.ru` отвечают 200/302 с SSL
- PostgreSQL доступен с домашнего IP на порту 5432
- PostgreSQL НЕ доступен с других IP

- [ ] **Step 7: Commit роли деплоя**

```bash
git add infra/ansible/roles/app/tasks/main.yml infra/ansible/playbooks/setup.yml
git commit -m "feat(infra): add app deployment role with Docker Compose"
```
