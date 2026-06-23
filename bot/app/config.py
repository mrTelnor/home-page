from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    bot_secret: str
    backend_url: str = "http://backend:8000"
    cron_secret: str
    uptime_secret: str
    port: int = 8080
    # Публичный адрес сайта — для ссылок в оповещениях (например, на рецепт-победитель).
    site_url: str = "https://telnor.ru"
    # Google Calendar integration
    google_service_account_b64: str = ""
    calendar_configs: str = "[]"
    reminders_data_path: str = "/data/sent_reminders.json"
    # Default reminders (минуты, через запятую) — применяются когда у события
    # нет explicit overrides (useDefault=true или поле отсутствует).
    calendar_default_reminders_min: str = "30"

    model_config = {"env_file": ".env"}


settings = Settings()
