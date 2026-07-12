"""CodeExecutorPort — порт изолированного исполнения пользовательских блоков.

BR-004: Python-блок исполняется как чистая функция ``run(context) -> dict``
в песочнице (таймаут 1–3 с, лимиты памяти/ответа, без доступа к ФС, env,
токенам, БД; сеть — только по whitelist). ``context`` не содержит токенов
и соединений. Реализация появится в infrastructure/code_executor/ (ADR-0003, запланировано).
"""

from __future__ import annotations

from typing import Protocol


class CodeExecutorPort(Protocol):
    """Запускает версионированный пользовательский блок в изоляции."""

    async def run(self, code_id: str, version: int, context: dict[str, object]) -> dict[str, object]:
        """Исполняет блок и возвращает его результат (dict).

        :raises ApplicationError: таймаут, превышение лимитов, ошибка кода —
            реализация оборачивает их в свои классы ошибок; сценарий
            обрабатывает сбой блока как ветку ошибки, а не падение движка.
        """
        ...
