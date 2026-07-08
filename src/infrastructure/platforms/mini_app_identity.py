"""Mini app identity extraction after platform init data verification."""

from __future__ import annotations

import json
from collections.abc import Mapping

from application.ports.bot_platform import MiniAppIdentity


def identity_from_init_data(params: Mapping[str, str] | None) -> MiniAppIdentity | None:
    """Build trusted identity only when signed init data contains a usable user id."""
    if params is None:
        return None
    raw_user = params.get("user")
    if raw_user is None:
        return None
    try:
        user = json.loads(raw_user)
    except json.JSONDecodeError:
        return None
    if not isinstance(user, dict):
        return None
    external_user_id = str(user.get("id", ""))
    if not external_user_id:
        return None
    return MiniAppIdentity(external_user_id=external_user_id, params=params)
