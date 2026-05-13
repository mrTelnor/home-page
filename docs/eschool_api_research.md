# eschool.center — Reverse-engineered API для Telegram-бота (роль: Родитель)

> **Источник знаний:** результаты исследования браузерной сессии на `app.eschool.center` (12.05.2026).  
> Это **неофициальная** документация, восстановленная из сетевых запросов веб-приложения.  
> Официального публичного API у eschool.center нет. Документация на `school-master.notion.site`  
> относится к другой платформе (School-master) и к eschool.center отношения не имеет.

---

## 1. Общие сведения

| Параметр | Значение |
|---|---|
| Базовый URL | `https://app.eschool.center/ec-server` |
| Аутентификация | Cookie-сессия (session cookie, получается при логине) |
| Формат ответов | JSON |
| Версия приложения | 1.5.19-ver-3420-gdd44a5ba.0 (по состоянию на 08.05.2026) |

---

## 2. Аутентификация

Система использует **cookie-based** аутентификацию. Токены (как в School-master) здесь не используются.

### 2.1 Логин

```
POST https://app.eschool.center/ec-server/login
Content-Type: application/json

{"login": "username", "pass": "password"}
```

- Ответ `400` с телом `8` означает неверный логин/пароль (тело — код ошибки).  
- При успехе сервер устанавливает session cookie (обычно `JSESSIONID` или аналог).
- Все последующие запросы должны передавать эту куку автоматически (через `requests.Session()` в Python).

### 2.2 Пример на Python (requests)

```python
import requests

BASE = "https://app.eschool.center/ec-server"

session = requests.Session()

# Логин
resp = session.post(f"{BASE}/login", json={"login": "ваш_логин", "pass": "ваш_пароль"})
if resp.status_code != 200:
    raise Exception(f"Login failed: {resp.status_code} {resp.text}")

# Теперь session автоматически хранит куки — все следующие запросы авторизованы
state = session.get(f"{BASE}/state").json()
print(state)
```

### 2.3 Проверка авторизованности

```
GET /ec-server/state
```

Если авторизован — возвращает объект с полями:
```json
{
  "authenticated": true,
  "userId": 564041,
  "user": {
    "sessionId": 93743164,
    "userId": 564041,
    "prsId": 233819,
    "orgId": 10,
    "username": "mrtelnor",
    "currentPosition": {
      "prsId": 233819,
      "prsFio": "Волков Никита Владимирович",
      "posName": "Родитель",
      "posTypeCode": "P",
      "orgName": "Электронная школа",
      "baseUrl": "app.eschool.center",
      "orgYearId": 90280,
      "myChildren": [
        {
          "prsId": 219673,
          "fio": "Волкова Вероника Никитична",
          "gender": 0,
          "isDefaultChild": 0
        }
      ]
    }
  }
}
```

Ключевые поля:
- `user.prsId` — ID персоны **родителя** (нужен для запросов профиля, чата)
- `user.currentPosition.myChildren[].prsId` — ID персоны **ребёнка** (нужен для дневника, расписания)
- `user.currentPosition.orgYearId` — ID текущего учебного года

---

## 3. Эндпоинты для дневника

### 3.1 Получить дневник за неделю ⭐ (главный эндпоинт)

```
GET /ec-server/student/getPrsDiary?prsId={childPrsId}&d1={timestampStart}&d2={timestampEnd}
```

Параметры:
- `prsId` — `prsId` ребёнка (из `/state`)
- `d1` — начало периода в миллисекундах (Unix timestamp × 1000), обычно понедельник
- `d2` — конец периода в миллисекундах, обычно воскресенье

Пример на Python:
```python
import datetime, time

def week_timestamps(date: datetime.date):
    """Возвращает (d1, d2) — начало и конец недели в мс для заданной даты."""
    monday = date - datetime.timedelta(days=date.weekday())
    sunday = monday + datetime.timedelta(days=6, hours=23, minutes=59, seconds=59)
    d1 = int(monday.strftime('%s')) * 1000
    d2 = int(sunday.strftime('%s')) * 1000
    return d1, d2

d1, d2 = week_timestamps(datetime.date.today())
diary = session.get(f"{BASE}/student/getPrsDiary", params={
    "prsId": 219673,
    "d1": d1,
    "d2": d2
}).json()
```

Структура ответа:
```json
{
  "isPeriodClosed": 0,
  "dateBegin": 1778446800000,
  "dateEnd": 1778965200000,
  "user": [
    {
      "id": "...",
      "prsID": 219673,
      "lastName": "...",
      "firstName": "...",
      "mark": [],
      "markTotal": [],
      "attend": [],
      "memberPeriod": []
    }
  ],
  "lesson": [ /* массив уроков */ ],
  "lessonGroup": [],
  "themPlan": []
}
```

Структура одного урока (`lesson[i]`):
```json
{
  "id": 9789281,
  "date": 1778533200000,
  "numInDay": 1,
  "statusID": 2,
  "isODOD": 0,
  "unit": {
    "id": 12416,
    "name": "Иностранный язык (английский)",
    "short": "Иност."
  },
  "clazz": {
    "id": 374756,
    "name": "4-а"
  },
  "teacher": {
    "factID": 73292,
    "factTeacherIN": "Вербицкая Маргарита Григорьевна",
    "prsId": 57059
  },
  "part": [
    {
      "id": 11932811,
      "cat": "DZ",
      "name": "Домашнее задание",
      "color": "e57a7a",
      "hasTask": 1,
      "variant": [
        {
          "id": 5982880,
          "text": "<p>дз на 12.05 упр.11 стр.81 PB</p>",
          "deadLine": 1778533200000,
          "preview": "дз на 12.05 упр.11 стр.81 PB"
        }
      ]
    },
    {
      "id": 11994509,
      "cat": "RK",
      "name": "Классная работа",
      "color": "79b560",
      "hasTask": 0
    }
  ],
  "date_d": "2026-05-12"
}
```

Типы `part[].cat`:
- `"DZ"` — домашнее задание
- `"RK"` — классная работа
- (возможны другие коды в зависимости от настроек школы)

Как получить текст ДЗ:
```python
from bs4 import BeautifulSoup

def get_homework(lesson):
    for part in lesson.get("part", []):
        if part.get("cat") == "DZ" and part.get("hasTask"):
            for variant in part.get("variant", []):
                # text содержит HTML, preview — чистый текст
                return variant.get("preview") or BeautifulSoup(variant.get("text",""), "html.parser").get_text()
    return None
```

---

## 4. Расписание

### 4.1 Получить расписание на период

```
GET /ec-server/lesson/schedule?begDate={tsMs}&endDate={tsMs}&prsId={childPrsId}&type=STD
```

Параметры:
- `begDate` — начало периода (мс)
- `endDate` — конец периода (мс)
- `prsId` — prsId ребёнка
- `type` — `STD` (студент/ученик)

Структура ответа — массив уроков:
```json
[
  {
    "lessonId": 9789281,
    "lessonDt": 1778533200000,
    "lessonNum": 1,
    "isOdod": 0,
    "isSubst": 0,
    "lessonStatus": 2,
    "groupId": 374756,
    "groupName": "4-а",
    "unitId": 12416,
    "unitName": "Иностранный язык (английский)",
    "unitShortName": "Иност.",
    "orgId": 4124,
    "teacherPrsId": 57059,
    "teacherLastName": "Вербицкая",
    "teacherFirstName": "Маргарита",
    "teacherMiddleName": "Григорьевна",
    "classNum": "4",
    "lesData": {
      "lp": [
        {"lpt": "Домашнее задание", "ptcId": 1},
        {"lpt": "Классная работа", "ptcId": 4}
      ],
      "subj": "62 Родная страна и страны изучаемого языка"
    },
    "tchArray": [...]
  }
]
```

Отличие от `getPrsDiary`: расписание не содержит текст ДЗ и оценки, только структуру уроков. Для полного дневника используйте `getPrsDiary`.

---

## 5. Профиль и учебные годы

### 5.1 Профиль пользователя

```
GET /ec-server/profile/getProfile_new?prsId={prsId}
```

Поля ответа: `lastName`, `firstName`, `middleName`, `email`, `login`, `birthDate`, `gender`, `prsRel` (связанные персоны).

Поле `prsRel[].relCode` содержит тип связи: `"DAUGHTER"`, `"SON"`, и т.д.

### 5.2 Учебные годы

```
GET /ec-server/yearplan/academyears
```

Возвращает массив:
```json
[
  {
    "yearId": 90280,
    "name": "2025 / 2026",
    "yearState": "CURR",
    "fullStartDate": 1756674000000,
    "fullEndDate": 1788123600000
  }
]
```

`yearState`: `"CURR"` — текущий год, `"ARC"` — архивный.

---

## 6. Дополнительные эндпоинты

| Эндпоинт | Метод | Описание |
|---|---|---|
| `/ec-server/srv/sysTime` | GET | Системное время сервера |
| `/ec-server/dict/acadyears` | GET | Краткий список учебных лет |
| `/ec-server/dict/schoolyears` | GET | Список школьных лет |
| `/ec-server/dict/getMarkSys` | GET | Система оценивания |
| `/ec-server/journal/marks/dict` | GET | Справочник оценок |
| `/ec-server/journal/attends/dict` | GET | Справочник пропусков |
| `/ec-server/student/getMarkSysConvRules` | GET | Правила конвертации оценок |
| `/ec-server/tasks/digest` | GET | Дайджест задач/напоминаний |
| `/ec-server/news/digest?page=1&pageSize=5` | GET | Новости школы |
| `/ec-server/actions/digest` | GET | Ближайшие события/мероприятия |
| `/ec-server/actions/getActions/?begDate={ms}&endDate={ms}&filterByMem=1&memberIds={childPrsId}` | GET | Мероприятия ребёнка за период |
| `/ec-server/chat/count?prsId={prsId}` | GET | Количество непрочитанных сообщений |
| `/ec-server/chat/privateThreads` | GET | Приватные чаты |

---

## 7. Рекомендации по реализации Telegram-бота

### Структура проекта

```
eschool-tg-bot/
├── main.py              # Точка входа, регистрация хэндлеров
├── config.py            # Переменные окружения (BOT_TOKEN, LOGIN, PASS)
├── eschool/
│   ├── client.py        # HTTP-клиент (сессия, логин, методы API)
│   ├── parser.py        # Парсинг ответов в удобные dataclass'ы
│   └── models.py        # Dataclass'ы: Lesson, Homework, DiaryWeek
├── bot/
│   ├── handlers.py      # Хэндлеры команд /diary, /schedule, /hw
│   └── formatters.py    # Форматирование сообщений для Telegram
└── requirements.txt
```

### Пример ESchoolClient

```python
# eschool/client.py
import requests
from datetime import date, timedelta

class ESchoolClient:
    BASE = "https://app.eschool.center/ec-server"

    def __init__(self, login: str, password: str):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (compatible; TelegramBot)"
        )
        self._login(login, password)
        self._load_state()

    def _login(self, login: str, password: str):
        resp = self.session.post(
            f"{self.BASE}/login",
            json={"login": login, "pass": password}
        )
        resp.raise_for_status()

    def _load_state(self):
        state = self.session.get(f"{self.BASE}/state").json()
        pos = state["user"]["currentPosition"]
        self.parent_prs_id = pos["prsId"]
        self.children = pos["myChildren"]  # list of {prsId, fio}
        self.default_child_prs_id = self.children[0]["prsId"]

    def get_diary(self, prs_id: int, week_date: date = None) -> dict:
        """Получить дневник за неделю, содержащую week_date."""
        if week_date is None:
            week_date = date.today()
        monday = week_date - timedelta(days=week_date.weekday())
        sunday = monday + timedelta(days=6)
        d1 = int(monday.strftime("%s")) * 1000
        d2 = int(sunday.strftime("%s")) * 1000 + 86399000
        return self.session.get(
            f"{self.BASE}/student/getPrsDiary",
            params={"prsId": prs_id, "d1": d1, "d2": d2}
        ).json()

    def get_schedule(self, prs_id: int, week_date: date = None) -> list:
        """Получить расписание за неделю."""
        if week_date is None:
            week_date = date.today()
        monday = week_date - timedelta(days=week_date.weekday())
        sunday = monday + timedelta(days=6)
        d1 = int(monday.strftime("%s")) * 1000
        d2 = int(sunday.strftime("%s")) * 1000 + 86399000
        return self.session.get(
            f"{self.BASE}/lesson/schedule",
            params={"prsId": prs_id, "begDate": d1, "endDate": d2, "type": "STD"}
        ).json()
```

### Рекомендуемые команды бота

| Команда | Действие |
|---|---|
| `/start` | Приветствие, список команд |
| `/diary` | Дневник на текущую неделю (предметы + ДЗ) |
| `/diary next` | Дневник на следующую неделю |
| `/hw` | Только домашние задания на завтра |
| `/schedule` | Расписание на текущую неделю |
| `/child` | Переключить ребёнка (если детей несколько) |

### Зависимости (requirements.txt)

```
python-telegram-bot>=20.0
requests>=2.31.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
```

---

## 8. Важные замечания

1. **Нет официального API** — эти эндпоинты получены reverse-engineering'ом веб-приложения. Они могут измениться после обновления платформы.

2. **Сессия истекает** — реализуйте автоматический re-login при получении `401`/`403`.

3. **Timestamps в миллисекундах** — все даты в API передаются как Unix timestamp, умноженный на 1000. При конвертации: `datetime.fromtimestamp(ts / 1000)`.

4. **HTML в тексте ДЗ** — поле `lesson.part[].variant[].text` содержит HTML. Используйте `BeautifulSoup` или `html.unescape` + regexp для получения чистого текста. Поле `preview` уже содержит чистый текст.

5. **prsId родителя vs ребёнка** — это разные значения! Для дневника/расписания всегда используйте `prsId` **ребёнка**.

6. **Конфиденциальность** — не логируйте куки и пароли. Храните учётные данные в переменных окружения (`.env`).
