from typing import Self
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_relay_url: str = ""
    telegram_relay_key: str = ""
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
    # Трекер Vikunja: webhook /vikunja-webhook. Пустой секрет — все запросы отклоняются.
    vikunja_webhook_secret: str = ""
    # JSON {"логин Vikunja": "логин telnor.ru"}; tg_id берётся из backend по логину сайта.
    vikunja_user_map: str = "{}"
    vikunja_url: str = "https://tracker.telnor.ru"

    model_config = {"env_file": ".env"}

    @model_validator(mode="after")
    def validate_telegram_relay(self) -> Self:
        if bool(self.telegram_relay_url) != bool(self.telegram_relay_key):
            raise ValueError("TELEGRAM_RELAY_URL and TELEGRAM_RELAY_KEY must be set together")
        if not self.telegram_relay_url:
            return self

        token_in_url = self.telegram_bot_token and self.telegram_bot_token in self.telegram_relay_url
        if "{token}" in self.telegram_relay_url or token_in_url:
            raise ValueError("TELEGRAM_RELAY_URL must not contain the bot token")

        parsed = urlsplit(self.telegram_relay_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or "?" in self.telegram_relay_url
            or "#" in self.telegram_relay_url
        ):
            raise ValueError("TELEGRAM_RELAY_URL must be an absolute HTTPS URL without userinfo, query or fragment")
        return self


settings = Settings()
