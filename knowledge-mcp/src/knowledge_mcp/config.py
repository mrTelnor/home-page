"""Settings from env. Required: KNOWLEDGE_USERNAME, KNOWLEDGE_PASSWORD."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    url: str = "https://knowledge.telnor.ru"
    backend_url: str = "https://api.telnor.ru"
    username: str
    password: str
    timeout_seconds: float = 30.0

    model_config = {"env_prefix": "KNOWLEDGE_"}
