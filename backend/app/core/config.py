from typing import Self
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_expire_hours: int = 168
    invite_code: str
    cron_secret: str
    domain: str = "telnor.ru"
    telegram_bot_token: str
    telegram_bot_username: str
    telegram_relay_url: str = ""
    telegram_relay_key: str = ""
    bot_secret: str
    cookie_secure: bool = True
    log_level: str = "INFO"
    recipe_images_dir: str = "/app/recipe_images"
    # None → ["https://{domain}", "https://wiki.{domain}"]; для разработки можно задать
    # CORS_ORIGINS='["https://telnor.ru","http://localhost:5173"]'
    cors_origins: list[str] | None = None
    telegram_auth_max_age_seconds: int = 300  # окно подписи Login Widget (было 3600) — уже окна меньше replay-риск
    rusender_api_key: str | None = None
    rusender_key_id: str | None = None
    email_from: str = "Telnor <noreply@telnor.ru>"
    reset_token_ttl_minutes: int = 60
    email_change_lock_days: int = 7
    rate_limit_enabled: bool = True
    # Строка подключения к базе знаний (Supabase, роль wiki_reader, пулер).
    # Пустая строка — вики выключена: /api/wiki/* отвечает 503, health — disabled.
    wiki_database_url: str = ""

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
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("TELEGRAM_RELAY_URL must contain a valid TCP port") from exc

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
