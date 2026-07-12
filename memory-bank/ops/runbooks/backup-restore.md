---
status: active
version: "1.0"
updated: 2026-07-12
verified_commit: ""
owner: ""
---

# Runbook: бэкап и восстановление PostgreSQL

Дев/сингл-сервер контур: сервис `pg-backup` в [compose.yaml](../../../compose.yaml)
раз в `BACKUP_INTERVAL` (сутки) делает `pg_dump -Fc` в `./backups/` на хосте и
удаляет дампы старше `BACKUP_KEEP_DAYS` (7). Скрипт —
[ops/backup/pg_backup.sh](../../../ops/backup/pg_backup.sh).
Прод-уровень (PITR/WAL-архив, offsite-копия) — открытый пункт
[deployment.md](../../architecture/deployment.md).

**Каталог `backups/` содержит ПДн** (`session.variables` до ретеншена BR-008):
он в `.gitignore`, наружу не копировать, доступ — как к самой БД. Токенов ботов
в дампах нет — секреты живут в `.secrets/`, не в PostgreSQL; поэтому полное
восстановление сервера = дамп БД **плюс** каталог `.secrets/` (бэкапится
отдельно и только в защищённое хранилище).

## Проверить, что бэкапы делаются

```bash
docker compose logs pg-backup --tail 5   # ожидаем строки "pg_backup: OK ..."
ls -lh backups/                          # свежий *.dump не старше суток
```

## Восстановление (полное, на пустую БД)

```bash
# 1. Остановить API и pg-backup — чтобы никто не писал в БД и свежий дамп не стал
#    снимком полувосстановленной базы во время процедуры
docker compose stop api pg-backup

# 2. Пересоздать БД и залить дамп (--clean не нужен: база свежая).
#    --force роняет чужие подключения (иначе dropdb упадёт «being accessed»)
docker compose exec postgres dropdb  -U metabot --if-exists --force metabot
docker compose exec postgres createdb -U metabot metabot
docker compose exec -T postgres pg_restore -U metabot -d metabot < backups/<файл>.dump

# 3. Поднять API и pg-backup (миграции прогонятся на старте и подтвердят схему)
docker compose start api pg-backup

# 4. Смоук: healthcheck + карточка любого бота
curl -s http://127.0.0.1:8000/healthchecks/
```

После восстановления боты продолжают работать без перерегистрации вебхуков
(URL не менялся); если восстановление шло на НОВЫЙ хост — задать
`WEBHOOK_BASE_URL` и повторить `POST /api/bots/{id}/publish` для каждого бота
(публикация идемпотентна и перерегистрирует вебхук, ADR-0014).

## Периодическая проверка восстановимости

Раз в месяц (или перед крупным релизом) прогонять восстановление последнего
дампа во временную БД — бэкап, который ни разу не восстанавливали, бэкапом
не считается:

```bash
docker compose exec postgres createdb -U metabot restore_check
docker compose exec -T postgres pg_restore -U metabot -d restore_check < backups/<свежий>.dump
docker compose exec postgres psql -U metabot -d restore_check -c "SELECT count(*) FROM bot;"
docker compose exec postgres dropdb -U metabot restore_check
```

## Инциденты

Потеря данных/подозрение на порчу — фиксируй по
[incident-template.md](incident-template.md); до разбора не перезаписывай
каталог `backups/` (останови `pg-backup`: `docker compose stop pg-backup`).
