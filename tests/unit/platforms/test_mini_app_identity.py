"""Mini app identity extraction in concrete platform adapters (BR-007)."""

import hashlib
import hmac
import json
from urllib.parse import urlencode

import httpx
import pytest

from infrastructure.platforms.max.adapter import MaxBotAdapter
from infrastructure.platforms.telegram.adapter import TelegramBotAdapter

pytestmark = pytest.mark.unit

TOKEN = "12345:test-token"


def _signed(params: dict[str, str]) -> str:
    data_check = "\n".join(f"{key}={params[key]}" for key in sorted(params))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**params, "hash": digest})


@pytest.mark.parametrize("adapter_cls", [TelegramBotAdapter, MaxBotAdapter])
async def test_adapter_returns_identity_from_signed_user_payload(adapter_cls) -> None:
    async with httpx.AsyncClient() as client:
        adapter = adapter_cls(client, init_data_max_age=0)
        identity = adapter.validate_init_data(
            TOKEN,
            _signed({"auth_date": "100", "user": json.dumps({"id": 777, "first_name": "Roman"})}),
        )

    assert identity is not None
    assert identity.external_user_id == "777"
    assert identity.params["user"] == '{"id": 777, "first_name": "Roman"}'
    assert "hash" not in identity.params


@pytest.mark.parametrize(
    "params",
    [
        {"auth_date": "100"},
        {"auth_date": "100", "user": "{}"},
        {"auth_date": "100", "user": "not-json"},
    ],
)
@pytest.mark.parametrize("adapter_cls", [TelegramBotAdapter, MaxBotAdapter])
async def test_adapter_rejects_signed_payload_without_trusted_user_id(adapter_cls, params) -> None:
    async with httpx.AsyncClient() as client:
        adapter = adapter_cls(client, init_data_max_age=0)
        identity = adapter.validate_init_data(TOKEN, _signed(params))

    assert identity is None
