"""Криптоядро валидации init data mini app (BR-007) — общее для TG и MAX."""

import hashlib
import hmac
from urllib.parse import urlencode

import pytest

from infrastructure.platforms.webapp_signature import verify_init_data

pytestmark = pytest.mark.unit

TOKEN = "12345:test-secret-token"


def _sign(token: str, params: dict[str, str]) -> str:
    """Собирает подписанную init-data-строку (эталон алгоритма)."""
    data_check = "\n".join(f"{k}={params[k]}" for k in sorted(params))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**params, "hash": digest})


def test_valid_signature_returns_params_without_hash() -> None:
    init = _sign(TOKEN, {"auth_date": "100", "query_id": "q1", "user": '{"id":1}'})
    params = verify_init_data(TOKEN, init, max_age_seconds=0)
    assert params is not None
    assert params["query_id"] == "q1"
    assert "hash" not in params


def test_wrong_token_rejected() -> None:
    init = _sign(TOKEN, {"auth_date": "100", "x": "y"})
    assert verify_init_data("other:token", init, max_age_seconds=0) is None


def test_tampered_value_rejected() -> None:
    init = _sign(TOKEN, {"auth_date": "100", "x": "y"}).replace("x=y", "x=z")
    assert verify_init_data(TOKEN, init, max_age_seconds=0) is None


def test_injected_extra_field_breaks_signature() -> None:
    init = _sign(TOKEN, {"auth_date": "100"}) + "&injected=1"
    assert verify_init_data(TOKEN, init, max_age_seconds=0) is None


def test_missing_hash_returns_none() -> None:
    assert verify_init_data(TOKEN, "auth_date=100&x=y", max_age_seconds=0) is None


def test_expired_auth_date_rejected() -> None:
    init = _sign(TOKEN, {"auth_date": "1000", "x": "y"})
    assert verify_init_data(TOKEN, init, max_age_seconds=100, now=5000) is None


def test_fresh_auth_date_accepted() -> None:
    init = _sign(TOKEN, {"auth_date": "4950", "x": "y"})
    assert verify_init_data(TOKEN, init, max_age_seconds=100, now=5000) is not None


def test_special_chars_in_value_roundtrip() -> None:
    # Значение с '&' и '=' (как в JSON user) корректно url-декодируется до сборки подписи.
    user = '{"id":7,"first_name":"A&B=C"}'
    init = _sign(TOKEN, {"auth_date": "100", "user": user})
    params = verify_init_data(TOKEN, init, max_age_seconds=0)
    assert params is not None
    assert params["user"] == user
