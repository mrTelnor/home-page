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

    model_config = {"env_file": ".env"}


settings = Settings()
