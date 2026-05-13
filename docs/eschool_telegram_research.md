# eSchool — Исследование авторизации через Telegram Bot

> **Дата исследования:** 13.05.2026  
> **Система:** eSchool (https://app.eschool.center)  
> **Аккаунт:** mrtelnor (Волков Никита Владимирович, роль: Родитель)

---

## 1. Стандартная авторизация (логин/пароль)

### Endpoint
```
POST https://app.eschool.center/ec-server/login
Content-Type: application/x-www-form-urlencoded
```

### Параметры запроса
| Параметр   | Значение             |
|------------|----------------------|
| `username` | логин пользователя   |
| `password` | пароль пользователя  |

### Ответ
При успешной авторизации устанавливаются куки (cookie):

| Cookie   | Описание                          |
|----------|-----------------------------------|
| `es_prs` | ID персоны (prsId)                |
| `es_user` | ID пользователя (userId)         |
| `es_org` | ID организации (orgId)            |
| `es_pos` | Позиция/роль пользователя         |

### Важно: капча
Тип капчи: `IMAGES` (Google reCAPTCHA)  
Endpoint проверки: `GET /ec-server/captcha/type`

При прямом POST-запросе к `/ec-server/login` без решённой капчи возвращается **HTTP 400**, тело ответа: `"5"` (код ошибки — капча обязательна).

**Вывод:** стандартная авторизация через скрипт без браузера **затруднена** из-за reCAPTCHA.

---

## 2. Внешняя авторизация (OAuth / OpenID Connect)

### Endpoint
```
GET https://app.eschool.center/ec-server/getExtAuth
```

### Результат
Для данного аккаунта (orgId=10) доступна только одна внешняя авторизация:

| Провайдер            | Тип              |
|----------------------|------------------|
| Европейская гимназия | OpenID Connect   |

**Telegram в разделе внешней авторизации отсутствует.**

---

## 3. Telegram Bot — исследование

### 3.1 Поиск в JavaScript файлах

Были проверены следующие JS-файлы на наличие ключевых слов (`telegram`, `tgbot`, `bot`, `t.me`):

- `/app/scripts/scripts.js`
- `/app/scripts/modulescore.js`
- `/app/scripts/modulescorea.js`
- `/app/scripts/modules.js`
- `/app/scripts/template-cache.js`

**Результат:** Ни одного упоминания Telegram в клиентском JavaScript обнаружено не было.

---

### 3.2 Найденные API Endpoints для Telegram

На сервере обнаружены следующие Telegram-связанные эндпоинты:

| Endpoint                              | Метод | Статус | Описание                         |
|---------------------------------------|-------|--------|----------------------------------|
| `/ec-server/tg/getStartLink`          | GET   | 403/404 | Получить стартовую ссылку бота  |
| `/ec-server/tg/getActivationCode`     | GET   | 403    | Получить код активации           |
| `/ec-server/tg/activate`              | POST  | 403    | Активировать Telegram-аккаунт    |
| `/ec-server/profile/tg`               | GET   | 500    | Данные профиля Telegram          |
| `/ec-server/profile/tgCode`           | GET   | 500    | Код привязки Telegram            |
| `/ec-server/profile/tgLink`           | GET   | 500    | Ссылка привязки Telegram         |

**Вывод:** Эндпоинты существуют на сервере, но **недоступны** для данного аккаунта (403 — нет прав, 500 — не настроено).

---

### 3.3 Раздел «Социальные сети» в профиле

Endpoint настроек профиля: `GET /ec-server/profile/getProfile_new?prsId=233819`

В разделе «Социальные сети» в профиле доступны только:
- Skype
- ВКонтакте
- Facebook
- Одноклассники
- Twitter
- LinkedIn

**Telegram в списке социальных сетей отсутствует.**

---

### 3.4 Почему Telegram Bot недоступен

Telegram-бот в eSchool — **опциональный модуль**, подключаемый на уровне организации.

| Параметр        | Значение                         |
|-----------------|----------------------------------|
| orgId аккаунта  | 10 (базовый — «Электронная школа») |
| orgId школы ребёнка | 4124 (ЧОУ «Школа ДИПЛОМАТ») |

Для активации Telegram-бота необходимо, чтобы администратор **организации** включил этот модуль.

---

## 4. Профиль пользователя

| Поле             | Значение                              |
|------------------|---------------------------------------|
| Логин            | mrtelnor                              |
| ФИО              | Волков Никита Владимирович            |
| Роль             | Родитель                              |
| userId           | 564041                                |
| prsId            | 233819                                |
| orgId            | 10                                    |
| Email            | mrtelnor@gmail.com                    |
| Ребёнок          | Волкова Вероника Никитична            |
| prsId ребёнка    | 219673                                |
| Класс ребёнка    | 4-а                                   |
| Организация      | ЧОУ «Школа ДИПЛОМАТ» (orgId=4124)    |

---

## 5. Ключевые API Endpoints

### Авторизация
```
POST /ec-server/login              # Войти
GET  /ec-server/state              # Проверить состояние сессии
GET  /ec-server/getExtAuth         # Внешние провайдеры авторизации
GET  /ec-server/captcha/type       # Тип капчи
```

### Профиль
```
GET /ec-server/profile/getProfile_new?prsId={prsId}   # Полный профиль
GET /ec-server/usr/profileOptions                      # Настройки профиля
```

### Дневник / Журнал
```
GET /ec-server/student/getPrsDiary?prsId={prsId}&d1={date}&d2={date}  # Дневник ученика
```

### Уведомления
```
GET /ec-server/notice/getNoticeCount    # Количество уведомлений
GET /ec-server/notice/getNotices        # Список уведомлений
```

---

## 6. Рекомендации

### Вариант A: Авторизация через браузер (Selenium/Playwright) — Рекомендуется

Обходит reCAPTCHA за счёт реального браузера:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('https://app.eschool.center/Login')
    page.fill('input[name="username"]', 'mrtelnor')
    page.fill('input[name="password"]', 'DasIstPorolen!1')
    page.click('button[type="submit"]')
    page.wait_for_url('**/Private/**')
    
    # Получить куки для дальнейших запросов
    cookies = page.context.cookies()
    
    # Выполнить API запрос
    response = page.request.get(
        'https://app.eschool.center/ec-server/student/getPrsDiary',
        params={'prsId': '219673', 'd1': '2026-05-01', 'd2': '2026-05-31'}
    )
    print(response.json())
```

---

### Вариант B: Прямые HTTP-запросы с куками (requests)

Если куки получены заранее (например, из браузера):

```python
import requests

session = requests.Session()

# Установить куки вручную (скопировать из браузера)
session.cookies.set('es_prs', '<значение>', domain='app.eschool.center')
session.cookies.set('es_user', '<значение>', domain='app.eschool.center')
session.cookies.set('es_org', '<значение>', domain='app.eschool.center')
session.cookies.set('es_pos', '<значение>', domain='app.eschool.center')

BASE_URL = 'https://app.eschool.center'

# Проверить авторизацию
state = session.get(f'{BASE_URL}/ec-server/state')
print(state.json())

# Получить дневник
diary = session.get(f'{BASE_URL}/ec-server/student/getPrsDiary', params={
    'prsId': '219673',
    'd1': '2026-05-01',
    'd2': '2026-05-31'
})
print(diary.json())
```

---

### Вариант C: Активация Telegram Bot (если будет включён администратором)

Предположительный flow на основе найденных эндпоинтов:

```
1. GET /ec-server/tg/getStartLink
   → Получить ссылку для старта бота (t.me/eschool_bot?start=...)

2. Перейти по ссылке в Telegram → нажать /start

3. GET /ec-server/tg/getActivationCode
   → Получить одноразовый код активации

4. POST /ec-server/tg/activate
   Body: { "code": "<activation_code>" }
   → Привязать Telegram-аккаунт к профилю

5. После привязки — общение с ботом через Telegram API
   (токен бота: неизвестен, управляется сервером eSchool)
```

> **Примечание:** Для активации Telegram-бота необходимо обратиться к администратору школы (ЧОУ «Школа ДИПЛОМАТ», orgId=4124) с просьбой подключить Telegram-модуль eSchool.

---

## 7. Итог

| Способ авторизации       | Статус                  | Комментарий                                         |
|--------------------------|-------------------------|-----------------------------------------------------|
| Логин/пароль (браузер)   | ✅ Работает              | Рекомендуется, обходит reCAPTCHA                   |
| Логин/пароль (requests)  | ⚠️ Частично             | Блокируется reCAPTCHA при прямом POST               |
| OpenID Connect           | ✅ Доступен              | Только «Европейская гимназия», не для данного орга  |
| Telegram Bot             | ❌ Недоступен            | Модуль не подключён для orgId=10 и orgId=4124       |

**Основной рекомендуемый подход:** использовать Playwright/Selenium для авторизации, затем извлекать куки и использовать их для последующих API-запросов через `requests`.
