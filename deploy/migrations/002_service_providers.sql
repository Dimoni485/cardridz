-- Cardridz: справочник сервисных организаций и учёт передачи в сервис.
-- Идемпотентная миграция для уже существующей базы.

BEGIN;

CREATE TABLE IF NOT EXISTS service_providers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    inn VARCHAR(12),
    contact_person VARCHAR(150),
    phone VARCHAR(50),
    email VARCHAR(150),
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_service_providers_name
    ON service_providers (name);

ALTER TABLE operations ADD COLUMN IF NOT EXISTS service_provider_id INTEGER;
ALTER TABLE operations ADD COLUMN IF NOT EXISTS expected_return_date DATE;
ALTER TABLE operations ADD COLUMN IF NOT EXISTS result VARCHAR(30);

ALTER TABLE cartridges ADD COLUMN IF NOT EXISTS service_provider_id INTEGER;
ALTER TABLE cartridges ADD COLUMN IF NOT EXISTS service_since TIMESTAMPTZ;
ALTER TABLE cartridges ADD COLUMN IF NOT EXISTS expected_return_date DATE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_operations_service_provider'
    ) THEN
        ALTER TABLE operations
            ADD CONSTRAINT fk_operations_service_provider
            FOREIGN KEY (service_provider_id)
            REFERENCES service_providers(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_cartridges_service_provider'
    ) THEN
        ALTER TABLE cartridges
            ADD CONSTRAINT fk_cartridges_service_provider
            FOREIGN KEY (service_provider_id)
            REFERENCES service_providers(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_operations_service_provider_id
    ON operations (service_provider_id);
CREATE INDEX IF NOT EXISTS ix_cartridges_service_provider_id
    ON cartridges (service_provider_id);

INSERT INTO service_providers
    (name, inn, contact_person, phone, email, notes, is_active)
VALUES
    ('ООО «РефиллСервис»', '7704444444', 'Сергей Иванов',
     '+7 (495) 200-10-10', 'service@refill.example', 'Заправка картриджей', TRUE),
    ('ООО «Картридж-Мастер»', '7705555555', 'Анна Петрова',
     '+7 (495) 200-20-20', 'info@cartmaster.example', 'Восстановление картриджей', TRUE)
ON CONFLICT (name) DO NOTHING;

UPDATE operations o
SET service_provider_id = sp.id,
    expected_return_date =
        ((o.occurred_at AT TIME ZONE 'Europe/Moscow')::date + 7)
FROM service_providers sp
WHERE sp.name = 'ООО «РефиллСервис»'
  AND o.type = 'send_refill'
  AND o.service_provider_id IS NULL;

UPDATE operations o
SET service_provider_id = sp.id,
    expected_return_date =
        ((o.occurred_at AT TIME ZONE 'Europe/Moscow')::date + 10)
FROM service_providers sp
WHERE sp.name = 'ООО «Картридж-Мастер»'
  AND o.type = 'send_restore'
  AND o.service_provider_id IS NULL;

UPDATE operations ret
SET service_provider_id = (
        SELECT s.service_provider_id
        FROM operations s
        WHERE s.cartridge_id = ret.cartridge_id
          AND s.type IN ('send_refill', 'send_restore')
          AND s.occurred_at <= ret.occurred_at
        ORDER BY s.occurred_at DESC
        LIMIT 1
    ),
    result = CASE ret.type
        WHEN 'refill_done' THEN 'refilled'
        ELSE 'restored'
    END
WHERE ret.type IN ('refill_done', 'restore_done')
  AND ret.service_provider_id IS NULL;

UPDATE cartridges c
SET service_provider_id = s.service_provider_id,
    service_since = s.occurred_at,
    expected_return_date = s.expected_return_date
FROM (
    SELECT DISTINCT ON (cartridge_id)
        cartridge_id,
        service_provider_id,
        occurred_at,
        expected_return_date
    FROM operations
    WHERE type IN ('send_refill', 'send_restore')
      AND service_provider_id IS NOT NULL
    ORDER BY cartridge_id, occurred_at DESC
) s
WHERE s.cartridge_id = c.id
  AND c.status IN ('in_refill', 'in_restore')
  AND c.service_provider_id IS NULL;

COMMIT;
