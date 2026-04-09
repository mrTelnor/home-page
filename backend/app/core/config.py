from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_expire_hours: int = 168
    invite_code: str
    cron_secret: str

    model_config = {"env_file": ".env"}


settings = Settings()
