-- Привязка принтера к отделу (и через него — к юрлицу).
-- Идемпотентно: повторный запуск безопасен.

ALTER TABLE printers
    ADD COLUMN IF NOT EXISTS department_id INTEGER
        REFERENCES departments (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_printers_department_id ON printers (department_id);

-- Заполняем отдел по ответственному сотруднику, если он известен.
UPDATE printers p
SET department_id = e.department_id
FROM employees e
WHERE p.employee_id = e.id
  AND p.department_id IS NULL
  AND e.department_id IS NOT NULL;
