#!/bin/sh
# Периодический pg_dump с ротацией — сервис pg-backup в compose.yaml.
# Restore и проверка — memory-bank/ops/runbooks/backup-restore.md.
# Формат -Fc (custom): сжатие + выборочное восстановление pg_restore.
set -eu

: "${PGHOST:=postgres}"
: "${PGUSER:=metabot}"
: "${PGDATABASE:=metabot}"
: "${BACKUP_DIR:=/backups}"
: "${BACKUP_INTERVAL:=86400}"   # секунды между дампами (сутки)
: "${BACKUP_KEEP_DAYS:=7}"      # храним ровно столько дампов, старше — удаляем

# Чистый выход по сигналу контейнера: docker stop шлёт SIGTERM PID 1, без trap он
# игнорируется и контейнер добивается SIGKILL (осиротевший *.part с ПДн).
trap 'exit 0' TERM INT

mkdir -p "$BACKUP_DIR"
# Осиротевшие недописанные дампы от прошлого SIGKILL/ребута: их не матчит ротация
# по *.dump — снимаем при старте, чтобы ПДн не копились бессрочно.
rm -f "$BACKUP_DIR"/*.part 2>/dev/null || true

while :; do
    stamp="$(date -u +%Y%m%d-%H%M%S)"
    target="$BACKUP_DIR/$PGDATABASE-$stamp.dump"
    tmp="$target.part"
    # В дампе НЕТ токенов ботов (секреты живут в .secrets/, не в PG), но
    # session.variables — потенциальные ПДн: каталог бэкапов = чувствительные данные.
    if pg_dump -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -Fc -f "$tmp"; then
        mv "$tmp" "$target"
        echo "pg_backup: OK $target ($(du -h "$target" | cut -f1))"
        # -mtime +(N-1): удаляем дампы старше N суток -> на диске остаётся ровно N.
        find "$BACKUP_DIR" -name "*.dump" -type f -mtime "+$((BACKUP_KEEP_DAYS - 1))" -delete
    else
        rm -f "$tmp"
        echo "pg_backup: FAILED $stamp" >&2
    fi
    sleep "$BACKUP_INTERVAL"
done
