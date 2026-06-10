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
    bot_secret: str
    cookie_secure: bool = True
    log_level: str = "INFO"
    # None → ["https://{domain}"]; для разработки можно задать
    # CORS_ORIGINS='["https://telnor.ru","http://localhost:5173"]'
    cors_origins: list[str] | None = None
    telegram_auth_max_age_seconds: int = 3600

    model_config = {"env_file": ".env"}


settings = Settings()
