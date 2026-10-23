-- Роли пользователей: admin (полный доступ + управление пользователями),
-- editor (чтение и редактирование), viewer (только чтение).
-- Идемпотентно: повторный запуск безопасен.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role VARCHAR(16) NOT NULL DEFAULT 'viewer';

-- Существующие учётные записи получают полный доступ, чтобы не потерять
-- возможность администрирования после обновления.
UPDATE users SET role = 'admin' WHERE role = 'viewer';

CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);
