"""Служебные роуты работоспособности (для оркестрации и healthcheck'ов)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: процесс жив и отвечает."""
    return {"status": "ok"}
