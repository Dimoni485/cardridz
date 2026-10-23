-- Cardridz: журнал ремонтов принтеров в сторонних сервисных организациях.
-- Идемпотентная миграция для уже существующей базы.

BEGIN;

CREATE TABLE IF NOT EXISTS printer_repairs (
    id SERIAL PRIMARY KEY,
    printer_id INTEGER NOT NULL REFERENCES printers(id) ON DELETE RESTRICT,
    service_provider_id INTEGER REFERENCES service_providers(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'in_service',
    sent_at TIMESTAMPTZ NOT NULL,
    expected_return_date DATE,
    returned_at TIMESTAMPTZ,
    document_no VARCHAR(100),
    cost NUMERIC(12, 2),
    result VARCHAR(30),
    legal_entity_id INTEGER REFERENCES legal_entities(id) ON DELETE SET NULL,
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    comment TEXT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_printer_repairs_printer_id
    ON printer_repairs (printer_id);
CREATE INDEX IF NOT EXISTS ix_printer_repairs_service_provider_id
    ON printer_repairs (service_provider_id);

ALTER TABLE printers ADD COLUMN IF NOT EXISTS service_provider_id INTEGER;
ALTER TABLE printers ADD COLUMN IF NOT EXISTS service_since TIMESTAMPTZ;
ALTER TABLE printers ADD COLUMN IF NOT EXISTS expected_return_date DATE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY (c.conkey)
        WHERE t.relname = 'printers'
          AND c.contype = 'f'
          AND a.attname = 'service_provider_id'
    ) THEN
        ALTER TABLE printers
            ADD CONSTRAINT fk_printers_service_provider
            FOREIGN KEY (service_provider_id)
            REFERENCES service_providers(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_printers_service_provider_id
    ON printers (service_provider_id);

INSERT INTO service_providers
    (name, inn, contact_person, phone, email, notes, is_active)
VALUES
    ('ООО «ОфисТехСервис»', '7706666666', 'Михаил Орлов',
     '+7 (495) 200-30-30', 'repair@officeservice.example',
     'Ремонт принтеров', TRUE)
ON CONFLICT (name) DO NOTHING;

INSERT INTO printer_repairs
    (printer_id, service_provider_id, status, sent_at,
     expected_return_date, document_no, legal_entity_id, department_id, comment)
SELECT
    p.id,
    sp.id,
    'in_service',
    now(),
    (now() + interval '7 days')::date,
    '—',
    d.legal_entity_id,
    e.department_id,
    'Открытый ремонт перенесён из статуса принтера'
FROM printers p
JOIN service_providers sp ON sp.name = 'ООО «ОфисТехСервис»'
LEFT JOIN employees e ON e.id = p.employee_id
LEFT JOIN departments d ON d.id = e.department_id
WHERE p.status = 'repair'
  AND NOT EXISTS (
      SELECT 1 FROM printer_repairs r
      WHERE r.printer_id = p.id AND r.status = 'in_service'
  );

UPDATE printers p
SET service_provider_id = r.service_provider_id,
    service_since = r.sent_at,
    expected_return_date = r.expected_return_date
FROM printer_repairs r
WHERE r.printer_id = p.id
  AND r.status = 'in_service'
  AND p.service_provider_id IS NULL;

COMMIT;
