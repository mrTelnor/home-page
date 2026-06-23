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
    recipe_images_dir: str = "/app/recipe_images"
    # None → ["https://{domain}"]; для разработки можно задать
    # CORS_ORIGINS='["https://telnor.ru","http://localhost:5173"]'
    cors_origins: list[str] | None = None
    telegram_auth_max_age_seconds: int = 3600
    rusender_api_key: str | None = None
    email_from: str = "Telnor <noreply@telnor.ru>"
    reset_token_ttl_minutes: int = 60
    email_change_lock_days: int = 7

    model_config = {"env_file": ".env"}


settings = Settings()
