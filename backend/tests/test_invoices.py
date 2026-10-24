from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.routes import invoices as invoices_module
from app.models.enums import InvoiceLineKind
from app.services.invoice_parser import parse_invoice_text
from tests.conftest import do_operation, make_cartridge

HEADER = (
    "Поставщик: ИНН 3702262718 КПП 370201001 Общество с ограниченной "
    'ответственностью "КОМТРЕЙД" 153006, г. Иваново, 15-й Проезд'
)
BUYER = (
    "Покупатель: ИНН 3704006406 КПП 370001001 Общество с ограниченной "
    'ответственностью "ИвМашТорг" 155048, Ивановская обл'
)


def invoice_text(
    items: list[tuple[str, int, str]],
    number: str = "7760",
    issued: str = "31.08.2026",
) -> str:
    rows: list[str] = []
    total = Decimal("0")
    for index, (title, qty, price) in enumerate(items, start=1):
        line_total = Decimal(price) * qty
        total += line_total
        rows.append(f"{index} {title} {qty} шт {price} {line_total}")
    return "\n".join(
        [
            "Внимание! Оплата данного счета означает согласие с условиями поставки.",
            HEADER,
            BUYER,
            f"Счет № {number} от {issued}",
            "№ Товар Кол-во Ед. Цена Сумма",
            *rows,
            f"Итого: {total}",
            f"НДС 5%: {round(total * Decimal('0.05') / Decimal('1.05'), 2)}",
            f"Всего наименований {len(rows)}, на сумму {total} руб.",
        ]
    )


def upload(
    client: TestClient,
    auth: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    text: str,
) -> dict:
    monkeypatch.setattr(
        invoices_module,
        "parse_invoice_pdf",
        lambda data: parse_invoice_text(text),
    )
    response = client.post(
        "/api/invoices",
        files={"file": ("invoice.pdf", b"%PDF-1.4 test", "application/pdf")},
        headers=auth,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_parser_normalizes_codes_and_validates_totals() -> None:
    parsed = parse_invoice_text(
        invoice_text(
            [
                ("Восстановление картриджа СЕ390 А", 1, "2379.80"),
                ("Заправка картриджа CF280 Х", 2, "1612.35"),
            ]
        )
    )

    assert [line.kind for line in parsed.lines] == [
        InvoiceLineKind.RESTORE,
        InvoiceLineKind.REFILL,
    ]
    assert [line.target_raw for line in parsed.lines] == ["CE390A", "CF280X"]
    assert parsed.total == Decimal("5604.50")
    assert parsed.problems == []
    assert parsed.supplier_inn == "3702262718"
    assert parsed.buyer_inn == "3704006406"


def test_parser_reports_broken_totals() -> None:
    text = invoice_text([("Заправка картриджа CF259A", 2, "100.00")])
    text = text.replace("Итого: 200.00", "Итого: 210.00")

    problems = parse_invoice_text(text).problems

    assert problems and "не совпадает" in problems[0]


def test_upload_suggests_matches(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text(
            [
                ("Заправка картриджа CF259A", 1, "391.61"),
                ("Ремонт аппарата HP LaserJet Pro M404dn", 1, "4050.00"),
            ]
        ),
    )

    assert invoice["status"] == "draft"
    assert invoice["number"] == "7760"
    assert invoice["matched_lines"] == 2
    assert invoice["lines"][0]["cartridge_model"]["id"] == base_data["cartridge_model"]["id"]
    assert invoice["lines"][1]["printer"]["id"] == base_data["printer"]["id"]


def test_apply_creates_operations_and_repair(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_cartridge(client, auth, base_data["cartridge_model"]["id"], "CRT-T1")
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text(
            [
                ("Заправка картриджа CF259A", 1, "391.61"),
                ("Ремонт аппарата HP LaserJet Pro M404dn", 1, "4050.00"),
            ]
        ),
    )

    response = client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["operations_created"] == 2
    assert result["repairs_created"] == 1
    assert result["cartridges_created"] == 0
    assert result["applied_lines"] == 2

    cartridges = client.get(
        f"/api/cartridges?model_id={base_data['cartridge_model']['id']}", headers=auth
    ).json()["items"]
    assert len(cartridges) == 1
    assert cartridges[0]["refill_count"] == 1
    assert cartridges[0]["status"] == "in_stock"

    operations = client.get(
        f"/api/cartridges/{cartridges[0]['id']}/operations", headers=auth
    ).json()
    refills = [op for op in operations if op["type"] == "refill_done"]
    assert len(refills) == 1
    assert refills[0]["cost"] == 372.96
    assert refills[0]["document_no"] == "Счёт № 7760"
    assert refills[0]["service_provider"]["name"] == "ООО «КОМТРЕЙД»"
    assert refills[0]["department"]["name"] == "Основной отдел"

    repairs = client.get(
        f"/api/printers/{base_data['printer']['id']}/repairs", headers=auth
    ).json()
    assert len(repairs) == 1
    assert repairs[0]["status"] == "returned"
    assert repairs[0]["cost"] == 3857.14
    assert repairs[0]["result"] == "repaired"

    detail = client.get(f"/api/invoices/{invoice['id']}", headers=auth).json()
    assert detail["status"] == "applied"
    assert detail["applied_lines"] == 2

    forbidden = client.patch(
        f"/api/invoices/{invoice['id']}/lines/{invoice['lines'][0]['id']}",
        json={"skipped": True},
        headers=auth,
    )
    assert forbidden.status_code == 409


def test_apply_requires_matching_printer(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text([("Ремонт аппарата HP LJ 9999", 1, "4050.00")]),
    )
    assert invoice["matched_lines"] == 0
    assert invoice["lines"][0]["printer"] is None

    response = client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)

    assert response.status_code == 400
    assert "1" in response.json()["detail"]


def test_model_is_auto_created_and_can_be_changed(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text([("Восстановление картриджа СЕ278 А", 1, "949.61")]),
    )
    line = invoice["lines"][0]

    assert line["cartridge_model"]["name"] == "CE278A"
    assert invoice["matched_lines"] == 1

    models = client.get("/api/cartridge-models", headers=auth).json()
    created = [item for item in models if item["name"] == "CE278A"]
    assert len(created) == 1
    assert created[0]["vendor"] == "HP"
    assert created[0]["refillable"] is True

    changed = client.patch(
        f"/api/invoices/{invoice['id']}/lines/{line['id']}",
        json={"cartridge_model_id": base_data["cartridge_model"]["id"]},
        headers=auth,
    )
    assert changed.status_code == 200, changed.text
    assert (
        changed.json()["lines"][0]["cartridge_model"]["name"] == "CF259A"
    )


def test_auto_match_endpoint_restores_matches(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text(
            [
                ("Восстановление картриджа CE278A", 1, "949.61"),
                ("Заправка картриджа CF259A", 1, "391.61"),
            ]
        ),
    )
    assert invoice["matched_lines"] == 2

    for line in invoice["lines"]:
        cleared = client.patch(
            f"/api/invoices/{invoice['id']}/lines/{line['id']}",
            json={"cartridge_model_id": None},
            headers=auth,
        )
        assert cleared.status_code == 200, cleared.text
    assert cleared.json()["matched_lines"] == 0

    response = client.post(
        f"/api/invoices/{invoice['id']}/auto-match", headers=auth
    )

    assert response.status_code == 200, response.text
    assert response.json()["matched_lines"] == 2


def test_auto_match_keeps_skipped_lines(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text(
            [
                ("Восстановление картриджа CE278A", 1, "949.61"),
                ("Восстановление картриджа CE285A", 1, "949.61"),
            ]
        ),
    )
    second = invoice["lines"][1]
    client.patch(
        f"/api/invoices/{invoice['id']}/lines/{second['id']}",
        json={"skipped": True, "cartridge_model_id": None},
        headers=auth,
    )
    client.patch(
        f"/api/invoices/{invoice['id']}/lines/{invoice['lines'][0]['id']}",
        json={"cartridge_model_id": None},
        headers=auth,
    )

    response = client.post(
        f"/api/invoices/{invoice['id']}/auto-match", headers=auth
    )

    body = response.json()
    assert body["matched_lines"] == 1
    assert body["skipped_lines"] == 1
    assert body["lines"][1]["cartridge_model"] is None


def test_manual_skipping_and_apply(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text(
            [
                ("Восстановление картриджа CE278A", 1, "949.61"),
                ("Заправка картриджа CF259A", 1, "391.61"),
            ]
        ),
    )
    assert invoice["matched_lines"] == 2

    skipped = client.patch(
        f"/api/invoices/{invoice['id']}/lines/{invoice['lines'][1]['id']}",
        json={"skipped": True},
        headers=auth,
    )
    assert skipped.status_code == 200
    assert skipped.json()["skipped_lines"] == 1

    result = client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["skipped_lines"] == 1
    assert body["applied_lines"] == 1
    assert body["cartridges_created"] == 1
    assert body["operations_created"] == 2

    cartridges = client.get("/api/cartridges?q=CE278A", headers=auth).json()["items"]
    assert [item["inventory_no"] for item in cartridges] == ["CE278A-001"]


def test_duplicate_upload_rejected(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = invoice_text([("Заправка картриджа CF259A", 1, "391.61")])
    upload(client, auth, monkeypatch, text)

    monkeypatch.setattr(
        invoices_module,
        "parse_invoice_pdf",
        lambda data: parse_invoice_text(text),
    )
    response = client.post(
        "/api/invoices",
        files={"file": ("invoice.pdf", b"%PDF-1.4 test", "application/pdf")},
        headers=auth,
    )

    assert response.status_code == 409
    assert "уже загружен" in response.json()["detail"]


def test_reuses_cartridges_between_lines(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_cartridge(client, auth, base_data["cartridge_model"]["id"], "CRT-T1")
    make_cartridge(client, auth, base_data["cartridge_model"]["id"], "CRT-T2")
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text(
            [
                ("Восстановление картриджа CF259A", 2, "949.61"),
                ("Заправка картриджа CF259A", 2, "391.61"),
            ]
        ),
    )

    response = client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cartridges_created"] == 0
    assert body["operations_created"] == 8

    detail = client.get(f"/api/invoices/{invoice['id']}", headers=auth).json()
    assert detail["lines"][0]["applied_note"].endswith("CRT-T1, CRT-T2")
    assert detail["lines"][1]["applied_note"].endswith("CRT-T1, CRT-T2")

def test_cartridge_in_service_is_closed_by_invoice(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = client.post(
        "/api/service-providers",
        json={"name": "ООО «КОМТРЕЙД»", "inn": "3702262718"},
        headers=auth,
    ).json()
    in_service = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-S1"
    )
    do_operation(
        client,
        auth,
        in_service["id"],
        "send_refill",
        service_provider_id=provider["id"],
        expected_return_date="2026-09-05",
    )
    stock = make_cartridge(client, auth, base_data["cartridge_model"]["id"], "CRT-S2")

    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text([("Заправка картриджа CF259A", 1, "391.61")]),
    )
    response = client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operations_created"] == 1
    assert body["cartridges_created"] == 0

    closed = client.get(f"/api/cartridges/{in_service['id']}", headers=auth).json()
    assert closed["status"] == "in_stock"
    assert closed["refill_count"] == 1
    assert closed["service_provider"] is None

    untouched = client.get(f"/api/cartridges/{stock['id']}", headers=auth).json()
    assert untouched["status"] == "in_stock"
    assert untouched["refill_count"] == 0

    detail = client.get(f"/api/invoices/{invoice['id']}", headers=auth).json()
    assert "закрыто после обслуживания: 1" in detail["lines"][0]["applied_note"]

    operations = client.get(
        f"/api/cartridges/{in_service['id']}/operations", headers=auth
    ).json()
    assert sorted(op["type"] for op in operations) == [
        "receipt",
        "refill_done",
        "send_refill",
    ]


def test_in_service_cartridge_must_match_line_kind(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    in_service = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-S1"
    )
    do_operation(
        client,
        auth,
        in_service["id"],
        "send_refill",
        service_provider_id=base_data["service_provider"]["id"],
        expected_return_date="2026-09-05",
    )
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text([("Восстановление картриджа CF259A", 1, "949.61")]),
    )

    line = invoice["lines"][0]
    response = client.patch(
        f"/api/invoices/{invoice['id']}/lines/{line['id']}/slots/"
        f"{line['slots'][0]['id']}",
        json={"cartridge_id": in_service["id"]},
        headers=auth,
    )

    assert response.status_code == 409
    assert "нельзя использовать" in response.json()["detail"]

def test_line_department_overrides_default(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accounting = client.post(
        "/api/departments",
        json={
            "legal_entity_id": base_data["legal_entity"]["id"],
            "name": "Бухгалтерия",
        },
        headers=auth,
    ).json()
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text([("Заправка картриджа CF259A", 1, "391.61")]),
    )
    line = invoice["lines"][0]

    matched = client.patch(
        f"/api/invoices/{invoice['id']}/lines/{line['id']}",
        json={"department_id": accounting["id"]},
        headers=auth,
    )
    assert matched.status_code == 200, matched.text
    assert matched.json()["lines"][0]["department"]["id"] == accounting["id"]
    assert matched.json()["legal_entity"]["id"] == base_data["legal_entity"]["id"]

    response = client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)
    assert response.status_code == 200, response.text

    cartridges = client.get(
        f"/api/cartridges?model_id={base_data['cartridge_model']['id']}", headers=auth
    ).json()["items"]
    assert len(cartridges) == 1
    operations = client.get(
        f"/api/cartridges/{cartridges[0]['id']}/operations", headers=auth
    ).json()
    done = next(op for op in operations if op["type"] == "refill_done")
    assert done["department"]["id"] == accounting["id"]
    assert done["department"]["legal_entity"]["id"] == base_data["legal_entity"]["id"]


def test_line_department_must_match_invoice_entity(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other_entity = client.post(
        "/api/legal-entities",
        json={"name": "ООО «Другое»", "inn": "7711111111"},
        headers=auth,
    ).json()
    other_department = client.post(
        "/api/departments",
        json={"legal_entity_id": other_entity["id"], "name": "Склад"},
        headers=auth,
    ).json()
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text([("Заправка картриджа CF259A", 1, "391.61")]),
    )
    client.patch(
        f"/api/invoices/{invoice['id']}",
        json={"legal_entity_id": base_data["legal_entity"]["id"]},
        headers=auth,
    )

    response = client.patch(
        f"/api/invoices/{invoice['id']}/lines/{invoice['lines'][0]['id']}",
        json={"department_id": other_department["id"]},
        headers=auth,
    )

    assert response.status_code == 400
    assert "другому юрлицу" in response.json()["detail"]

def test_slots_created_for_each_unit(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text([("Заправка картриджа CF259A", 3, "391.61")]),
    )

    slots = invoice["lines"][0]["slots"]
    assert [slot["position"] for slot in slots] == [1, 2, 3]
    assert all(slot["cartridge"] is None for slot in slots)


def test_each_slot_matched_and_attributed_separately(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accounting = client.post(
        "/api/departments",
        json={
            "legal_entity_id": base_data["legal_entity"]["id"],
            "name": "Бухгалтерия",
        },
        headers=auth,
    ).json()
    it_department = base_data["department"]
    first = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-M1"
    )
    second = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-M2"
    )
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text([("Заправка картриджа CF259A", 2, "391.61")]),
    )
    line = invoice["lines"][0]
    client.patch(
        f"/api/invoices/{invoice['id']}",
        json={"legal_entity_id": base_data["legal_entity"]["id"]},
        headers=auth,
    )

    assignments = (
        (line["slots"][0]["id"], first["id"], accounting["id"]),
        (line["slots"][1]["id"], second["id"], it_department["id"]),
    )
    for slot_id, cartridge_id, department_id in assignments:
        response = client.patch(
            f"/api/invoices/{invoice['id']}/lines/{line['id']}/slots/{slot_id}",
            json={"cartridge_id": cartridge_id, "department_id": department_id},
            headers=auth,
        )
        assert response.status_code == 200, response.text

    detail = client.get(f"/api/invoices/{invoice['id']}", headers=auth).json()
    slots = detail["lines"][0]["slots"]
    assert slots[0]["cartridge"]["inventory_no"] == "CRT-M1"
    assert slots[0]["department"]["id"] == accounting["id"]
    assert slots[1]["cartridge"]["inventory_no"] == "CRT-M2"
    assert slots[1]["department"]["id"] == it_department["id"]

    response = client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)

    assert response.status_code == 200, response.text
    assert response.json()["operations_created"] == 4

    first_done = [
        op
        for op in client.get(
            f"/api/cartridges/{first['id']}/operations", headers=auth
        ).json()
        if op["type"] == "refill_done"
    ][0]
    second_done = [
        op
        for op in client.get(
            f"/api/cartridges/{second['id']}/operations", headers=auth
        ).json()
        if op["type"] == "refill_done"
    ][0]
    assert first_done["department"]["id"] == accounting["id"]
    assert second_done["department"]["id"] == it_department["id"]


def test_slot_cannot_reuse_cartridge(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-M1"
    )
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text([("Заправка картриджа CF259A", 2, "391.61")]),
    )
    line = invoice["lines"][0]
    first, second = line["slots"]

    ok = client.patch(
        f"/api/invoices/{invoice['id']}/lines/{line['id']}/slots/{first['id']}",
        json={"cartridge_id": cartridge["id"]},
        headers=auth,
    )
    assert ok.status_code == 200, ok.text

    duplicate = client.patch(
        f"/api/invoices/{invoice['id']}/lines/{line['id']}/slots/{second['id']}",
        json={"cartridge_id": cartridge["id"]},
        headers=auth,
    )

    assert duplicate.status_code == 409
    assert "уже выбран" in duplicate.json()["detail"]

def test_costs_are_net_of_vat_by_default(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text(
            [
                ("Восстановление картриджа CF259A", 3, "949.61"),
                ("Заправка картриджа CF259A", 2, "391.61"),
                ("Ремонт аппарата HP LaserJet Pro M404dn", 1, "4050.00"),
            ]
        ),
    )
    assert invoice["vat_rate"] == 5.0
    assert invoice["cost_with_vat"] is False

    response = client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operations_created"] == 10
    assert body["repairs_created"] == 1
    assert round(body["posted_cost"], 2) == 7316.23

    operations = client.get("/api/operations?limit=500", headers=auth).json()["items"]
    done = [
        op
        for op in operations
        if op["type"] in {"refill_done", "restore_done"}
    ]
    assert {op["cost"] for op in done if op["type"] == "restore_done"} == {904.39}
    assert {op["cost"] for op in done if op["type"] == "refill_done"} == {372.96}

    repairs = client.get(
        f"/api/printers/{base_data['printer']['id']}/repairs", headers=auth
    ).json()
    assert repairs[0]["cost"] == 3857.14


def test_costs_can_include_vat(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text(
            [
                ("Восстановление картриджа CF259A", 3, "949.61"),
                ("Ремонт аппарата HP LaserJet Pro M404dn", 1, "4050.00"),
            ],
            number="7761",
        ),
    )
    client.patch(
        f"/api/invoices/{invoice['id']}", json={"cost_with_vat": True}, headers=auth
    )

    response = client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)

    assert response.status_code == 200, response.text
    assert round(response.json()["posted_cost"], 2) == 6898.83

    operations = client.get("/api/operations?limit=500", headers=auth).json()["items"]
    done = [op for op in operations if op["type"] == "restore_done"]
    assert {op["cost"] for op in done} == {949.61}

    repairs = client.get(
        f"/api/printers/{base_data['printer']['id']}/repairs", headers=auth
    ).json()
    assert repairs[0]["cost"] == 4050.0


def test_unapply_restores_state(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text(
            [
                ("Заправка картриджа CF259A", 1, "391.61"),
                ("Ремонт аппарата HP LaserJet Pro M404dn", 1, "4050.00"),
            ]
        ),
    )
    apply_response = client.post(
        f"/api/invoices/{invoice['id']}/apply", headers=auth
    )
    assert apply_response.status_code == 200, apply_response.text

    cartridges = client.get(
        f"/api/cartridges?model_id={base_data['cartridge_model']['id']}", headers=auth
    ).json()["items"]
    assert len(cartridges) == 1
    cartridge_id = cartridges[0]["id"]
    assert cartridges[0]["refill_count"] == 1

    response = client.post(f"/api/invoices/{invoice['id']}/unapply", headers=auth)

    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["status"] == "draft"
    assert detail["applied_at"] is None
    assert detail["applied_lines"] == 0
    assert all(not line["applied"] for line in detail["lines"])

    remaining = client.get(
        f"/api/cartridges?model_id={base_data['cartridge_model']['id']}", headers=auth
    ).json()["items"]
    assert remaining == []

    repairs = client.get(
        f"/api/printers/{base_data['printer']['id']}/repairs", headers=auth
    ).json()
    assert repairs == []

    again = client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)
    assert again.status_code == 200, again.text


def test_unapply_blocked_by_later_operations(
    client: TestClient,
    auth: dict[str, str],
    base_data: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stock = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-U1"
    )
    invoice = upload(
        client,
        auth,
        monkeypatch,
        invoice_text([("Заправка картриджа CF259A", 1, "391.61")]),
    )
    line = invoice["lines"][0]
    client.patch(
        f"/api/invoices/{invoice['id']}/lines/{line['id']}/slots/"
        f"{line['slots'][0]['id']}",
        json={"cartridge_id": stock["id"]},
        headers=auth,
    )
    client.post(f"/api/invoices/{invoice['id']}/apply", headers=auth)
    do_operation(client, auth, stock["id"], "issue", employee_id=base_data["employee"]["id"])

    response = client.post(f"/api/invoices/{invoice['id']}/unapply", headers=auth)

    assert response.status_code == 409
    assert "CRT-U1" in response.json()["detail"]
