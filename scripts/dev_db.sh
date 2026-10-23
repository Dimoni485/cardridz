#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PG_BIN="${PG_BIN:-/usr/lib/postgresql/17/bin}"
DATA_DIR="${PGDATA_DIR:-$ROOT_DIR/.pgdata}"
PORT="${PG_PORT:-5433}"
SOCKET_DIR="${PG_SOCKET_DIR:-/tmp}"
LOG_FILE="$DATA_DIR/server.log"

usage() {
  cat <<EOF
Локальный кластер PostgreSQL для разработки.

Использование: $(basename "$0") <команда>

Команды:
  init     инициализировать кластер и создать базы cardridz, cardridz_test
  start    запустить сервер
  stop     остановить сервер
  status   показать состояние
  psql     открыть psql к базе cardridz

Переменные: PG_BIN, PGDATA_DIR, PG_PORT (по умолчанию 5433), PG_SOCKET_DIR.
EOF
}

require_bin() {
  if [ ! -x "$PG_BIN/pg_ctl" ]; then
    echo "Не найден PostgreSQL в $PG_BIN. Укажите PG_BIN." >&2
    exit 1
  fi
}

is_running() {
  "$PG_BIN/pg_ctl" -D "$DATA_DIR" status >/dev/null 2>&1
}

start() {
  require_bin
  if [ ! -d "$DATA_DIR" ]; then
    echo "Кластер не инициализирован. Выполните: $(basename "$0") init" >&2
    exit 1
  fi
  if is_running; then
    echo "PostgreSQL уже запущен на порту $PORT"
    return 0
  fi
  "$PG_BIN/pg_ctl" -D "$DATA_DIR" \
    -o "-p $PORT -k $SOCKET_DIR -c listen_addresses=127.0.0.1" \
    -l "$LOG_FILE" start
  echo "PostgreSQL запущен: 127.0.0.1:$PORT (сокет: $SOCKET_DIR)"
}

init() {
  require_bin
  if [ -d "$DATA_DIR" ]; then
    echo "Каталог $DATA_DIR уже существует."
    start
    return 0
  fi
  "$PG_BIN/initdb" -D "$DATA_DIR" -U postgres --auth=trust -E UTF8 --locale=C.UTF-8
  start
  sleep 1
  for db in cardridz cardridz_test; do
    if ! "$PG_BIN/psql" -h 127.0.0.1 -p "$PORT" -U postgres -tAc \
      "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1; then
      "$PG_BIN/createdb" -h 127.0.0.1 -p "$PORT" -U postgres "$db"
      echo "Создана база $db"
    fi
  done
}

stop() {
  require_bin
  if [ ! -d "$DATA_DIR" ]; then
    echo "Кластер не инициализирован." >&2
    exit 1
  fi
  if ! is_running; then
    echo "PostgreSQL не запущен"
    return 0
  fi
  "$PG_BIN/pg_ctl" -D "$DATA_DIR" stop -m fast
}

status() {
  require_bin
  if [ ! -d "$DATA_DIR" ]; then
    echo "Кластер не инициализирован."
    return 1
  fi
  "$PG_BIN/pg_ctl" -D "$DATA_DIR" status
}

case "${1:-}" in
  init) init ;;
  start) start ;;
  stop) stop ;;
  status) status ;;
  psql) "$PG_BIN/psql" -h 127.0.0.1 -p "$PORT" -U postgres -d cardridz ;;
  *) usage; exit 1 ;;
esac
