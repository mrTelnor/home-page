from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    bot_secret: str
    backend_url: str = "http://backend:8000"
    webhook_host: str = "https://bot.telnor.ru"
    webhook_path: str = "/webhook"
    cron_secret: str
    uptime_secret: str
    port: int = 8080
    # Google Calendar integration
    google_service_account_b64: str = ""
    calendar_configs: str = "[]"
    reminders_data_path: str = "/data/sent_reminders.json"
    # Default reminders (минуты, через запятую) — применяются когда у события
    # нет explicit overrides (useDefault=true или поле отсутствует).
    calendar_default_reminders_min: str = "30"
    # Eschool integration
    eschool_login: str = ""
    eschool_password: str = ""
    eschool_base_url: str = "https://app.eschool.center/ec-server"
    # Cookie-режим: строка из заголовка Cookie браузерной сессии,
    # например "JSESSIONID=...; es_prs=...; es_user=..."
    # Если задано — клиент использует cookies и не пытается логиниться.
    eschool_cookies: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
