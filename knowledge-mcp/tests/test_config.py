import pytest

from knowledge_mcp.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_USERNAME", "u")
    monkeypatch.setenv("KNOWLEDGE_PASSWORD", "p")
    s = Settings()
    assert s.username == "u"
    assert s.password == "p"
    assert s.backend_url == "https://api.telnor.ru"
    assert s.url == "https://knowledge.telnor.ru"


def test_settings_requires_creds(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_USERNAME", raising=False)
    monkeypatch.delenv("KNOWLEDGE_PASSWORD", raising=False)
    with pytest.raises(Exception):
        Settings()
