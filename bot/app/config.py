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

    model_config = {"env_file": ".env"}


settings = Settings()
