# Развёртывание Cardridz в Docker

## Состав

- `app` — FastAPI + собранный React SPA (один контейнер, порт 8000 внутри).
- `db` — PostgreSQL 17, том `cardridz_pgdata`, наружу порт не публикуется.

Наружу открывается только приложение: `${APP_PORT}:8000` (по умолчанию 8081).

## Первичное развёртывание

```bash
# на сервере
mkdir -p /opt/cardridz
cd /opt/cardridz

# скопируйте исходники (rsync/scp/git), затем:
cp deploy/.env.example .env
chmod 600 .env
# отредактируйте .env: пароли, JWT_SECRET, ADMIN_PASSWORD

docker compose up -d --build
docker compose ps
curl -s http://127.0.0.1:8081/api/health
```

Логин администратора — `ADMIN_USERNAME` / `ADMIN_PASSWORD` из `.env`
(применяется только при создании учётной записи в пустой БД).

## Обновление

```bash
cd /opt/cardridz
# обновите файлы проекта (кроме .env)
docker compose build
# примените все миграции по порядку (они идемпотентны)
for f in deploy/migrations/*.sql; do
  docker compose exec -T db psql -U cardridz -d cardridz \
    -v ON_ERROR_STOP=1 < "$f"
done
docker compose up -d
docker compose ps
```

Схема БД создаётся автоматически при старте. При изменении структуры существующих
таблиц `create_all` их не изменяет — применяйте SQL-миграции из `deploy/migrations`
(они идемпотентны). `002_service_providers.sql` добавляет справочник сервисных
организаций и поля передачи картриджей, `003_printer_repairs.sql` — журнал
ремонтов принтеров и текущие поля сервиса у принтера, `004_user_roles.sql` —
роли пользователей (`admin` / `editor` / `viewer`), `005_department_room.sql` —
номер кабинета у отдела, `006_printer_department.sql` — привязка принтера к
отделу с заполнением по ответственному сотруднику. Миграции заполняют данные
для уже существующих записей, в том числе выдают существующим учётным записям
роль администратора.

## Управление

```bash
docker compose logs -f app        # логи приложения
docker compose logs -f db         # логи БД
docker compose restart app        # перезапуск
docker compose down               # остановить (данные сохраняются)
```

## Резервная копия и восстановление

```bash
# бэкап
docker compose exec -T db \
  pg_dump -U cardridz -d cardridz -Fc > backup-$(date +%F).dump

# восстановление
docker compose exec -T db \
  pg_restore -U cardridz -d cardridz --clean --if-exists < backup-2026-10-23.dump
```

## Демо-данные

`SEED_DEMO=true` заполняет базу примерами только при первом запуске
(если справочник моделей пуст). Чтобы начать с чистых данных, удалите
демонстрационные записи, не трогая учётные записи пользователей:

```bash
# 1. резервная копия
mkdir -p backups
docker compose exec -T db pg_dump -U cardridz -d cardridz \
  | gzip > backups/cardridz-$(date +%F-%H%M)-before-clean.sql.gz

# 2. выключите демо-данные, чтобы они не создались снова
sed -i 's/^SEED_DEMO=.*/SEED_DEMO=false/' .env

# 3. очистите бизнес-данные (пользователи остаются)
docker compose exec -T db psql -U cardridz -d cardridz -c \
  "TRUNCATE TABLE operations, printer_repairs, cartridges, printers, \
   cartridge_model_printer_model, cartridge_models, printer_models, \
   employees, departments, legal_entities, service_providers RESTART IDENTITY CASCADE;"

# 4. пересоздайте контейнер приложения, чтобы применился новый .env
docker compose up -d --force-recreate app
```

## Смена порта

Измените `APP_PORT` в `.env` и выполните `docker compose up -d`.
Порты 80, 443, 445, 8080 на сервере заняты другими сервисами.
