"""Периметр локального контура: наружу выходят только рантайм-эндпоинты.

Зачем. Приём вебхуков на рабочей машине делается через туннель
(`cloudflared`/`ngrok`), а туннель публикует **весь** origin. У ядра Admin API
пока без аутентификации (`security.md`, «Чего не хватает до прода»), поэтому
туннель прямо на `:8000` открывает интернету `POST /api/bots` (подключить свой
токен), `GET /api/bots/{id}/flow` (прочитать чужой сценарий),
`PUT /events-token` и `PUT /notifications/{role}` (увести доставку). Это не
утечка, а полный захват всех ботов инстанса — риск №1 в
[ADR-0018](../memory-bank/decisions/0018-vps-deployment-perimeter.md).

Что делает. Тот же **allowlist**, что ADR-0018 предписывает reverse-proxy на
VPS, только для dev-контура: пропускает ровно три пути, остальное отдаёт 404,
не доходя до приложения. Туннель поднимается на этот порт, а не на 8000.

Почему allowlist, а не «запретить /api». Под `/api` лежат и операции
конструктора (закрывать), и то, что обязано быть доступно снаружи: вызовы
mini app из браузера (BR-007). «Закрыть /api» — сломать mini app; «открыть
всё» — отдать управление. Список — единственный способ разделить.

Плата за строгость: новый **рантайм**-эндпоинт молча окажется недоступен
снаружи, пока его не добавят в ``ALLOWED``. Это выбрано осознанно — ошибка
в безопасную сторону; ADR-0018 предлагает снять её отдельным префиксом
(`/public`) для рантайм-путей.

Запуск::

    uv run python scripts/dev_perimeter_proxy.py            # 127.0.0.1:8001 → :8000
    ./cloudflared.exe tunnel --url http://localhost:8001    # наружу — только вебхуки

Порт по умолчанию — 8001, рядом с ядром (8000), а не 8080: на машине с
несколькими проектами 8080 обычно уже занят, и bind падает с `WinError 10013`.
Хуже молчаливого падения то, что туннель тогда уедет на **чужой** сервис, —
поэтому порт свой, а не «общепринятый».

Проверка периметра (обязательна после каждой правки, ADR-0018 «Риски»)::

    curl -s -o /dev/null -w "%{http_code}\n" https://<туннель>/api/bots            # ждём 404
    curl -s -o /dev/null -w "%{http_code}\n" -X POST https://<туннель>/webhooks/max/<id>

Второй запрос обязателен: «всё отдаёт 404» — это и правильно настроенный
периметр, и туннель, случайно уехавший на чужой сервис. Разрешённый путь
должен вернуть ответ **приложения** (для несуществующего бота — 404 с телом
ядра, для живого — 200), а не глухой отказ периметра.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger("perimeter")

#: Идентификатор бота в пути: hex uuid без дефисов, но не сужаем сверх нужного.
_ID = r"[A-Za-z0-9_-]{1,64}"

#: Публичный периметр — ровно то, что перечислено в ADR-0018.
#: Ключ — HTTP-метод, значение — разрешённые пути.
ALLOWED: dict[str, tuple[re.Pattern[str], ...]] = {
    "POST": (
        # Платформа шлёт update. Аутентификация — WEBHOOK_SECRET
        # (X-Telegram-Bot-Api-Secret-Token / X-Max-Bot-Api-Secret).
        re.compile(rf"^/webhooks/(?:telegram|max)/{_ID}$"),
        # Браузер mini app. Аутентификация — init data платформы (BR-007).
        re.compile(rf"^/api/bots/{_ID}/miniapp/auth$"),
        re.compile(rf"^/api/bots/{_ID}/miniapp/result$"),
    ),
    # Предполётный запрос браузера к тем же путям mini app: без него
    # POST из браузера не состоится. Тела не несёт, управлять ничем не может.
    "OPTIONS": (re.compile(rf"^/api/bots/{_ID}/miniapp/(?:auth|result)$"),),
}

#: Заголовки соединения — их нельзя переносить между двумя разными соединениями.
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    }
)

#: Ограничение тела: вебхук платформы — это JSON на килобайты, не файл.
MAX_BODY_BYTES = 2 * 1024 * 1024


def _is_allowed(method: str, path: str) -> bool:
    """Путь сверяется без query-строки: `?`-хвост не должен обходить правило."""
    bare = path.split("?", 1)[0].split("#", 1)[0]
    return any(pattern.match(bare) for pattern in ALLOWED.get(method.upper(), ()))


class PerimeterHandler(BaseHTTPRequestHandler):
    """Проксирует разрешённое в upstream, всё прочее закрывает 404."""

    protocol_version = "HTTP/1.1"
    upstream: str = "http://127.0.0.1:8000"

    # Родительский логгер пишет в stderr в своём формате — уводим в logging.
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — сигнатура stdlib
        logger.debug("%s %s", self.address_string(), format % args)

    def _handle(self) -> None:
        method = self.command
        if not _is_allowed(method, self.path):
            # 404, а не 403: отказ не должен подтверждать, что маршрут существует.
            # WARNING — чтобы перебор путей по туннелю был виден в логе.
            logger.warning("Закрыто периметром: %s %s", method, self.path.split("?", 1)[0])
            self._respond(404, b'{"detail":"Not Found"}', {"Content-Type": "application/json"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            logger.warning("Тело %d байт больше лимита %d — отказ", length, MAX_BODY_BYTES)
            self._respond(413, b'{"detail":"Payload too large"}', {"Content-Type": "application/json"})
            return
        body = self.rfile.read(length) if length else None

        request = urllib.request.Request(f"{self.upstream}{self.path}", data=body, method=method)
        for name, value in self.headers.items():
            if name.lower() not in _HOP_BY_HOP:
                request.add_header(name, value)

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                headers = {k: v for k, v in response.headers.items() if k.lower() not in _HOP_BY_HOP}
                self._respond(response.status, payload, headers)
        except urllib.error.HTTPError as exc:
            # Ошибка приложения — это ответ приложения, его и отдаём платформе как есть.
            payload = exc.read()
            headers = {k: v for k, v in exc.headers.items() if k.lower() not in _HOP_BY_HOP}
            self._respond(exc.code, payload, headers)
        except OSError as exc:
            # Ядро не поднято или упало: платформе честный 502, а не тишина.
            logger.error("Upstream %s недоступен: %s", self.upstream, exc)
            self._respond(502, b'{"detail":"Upstream unavailable"}', {"Content-Type": "application/json"})

    def _respond(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    # Периметр обязан закрывать и те методы, которых нет в списке, — иначе
    # GET /api/bots уехал бы в приложение просто потому, что мы его не описали.
    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle
    do_PATCH = _handle
    do_DELETE = _handle
    do_HEAD = _handle
    do_OPTIONS = _handle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Периметр dev-контура: наружу только вебхуки и mini app")
    parser.add_argument("--port", type=int, default=8001, help="порт периметра (его и отдаём туннелю)")
    parser.add_argument("--host", default="127.0.0.1", help="интерфейс периметра")
    parser.add_argument("--upstream", default="http://127.0.0.1:8000", help="адрес ядра")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    PerimeterHandler.upstream = args.upstream.rstrip("/")

    server = ThreadingHTTPServer((args.host, args.port), PerimeterHandler)
    allowed = sum(len(patterns) for patterns in ALLOWED.values())
    logger.info(
        "Периметр на http://%s:%d → %s; открыто путей: %d, остальное 404",
        args.host,
        args.port,
        PerimeterHandler.upstream,
        allowed,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Периметр остановлен")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
