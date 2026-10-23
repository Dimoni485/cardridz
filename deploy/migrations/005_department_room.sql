-- Номер кабинета у отдела. Идемпотентно: повторный запуск безопасен.

ALTER TABLE departments
    ADD COLUMN IF NOT EXISTS room VARCHAR(50);
