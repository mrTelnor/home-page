"""Тесты constant_time_equals — сравнение секретов в постоянном времени."""
from app.core.security import constant_time_equals


def test_constant_time_equals_matches():
    assert constant_time_equals("secret-value", "secret-value")


def test_constant_time_equals_rejects_mismatch():
    assert not constant_time_equals("secret-valuX", "secret-value")


def test_constant_time_equals_rejects_none():
    assert not constant_time_equals(None, "secret-value")


def test_constant_time_equals_rejects_prefix():
    assert not constant_time_equals("secret", "secret-value")
