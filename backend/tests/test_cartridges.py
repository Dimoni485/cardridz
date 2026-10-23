from fastapi.testclient import TestClient
from tests.conftest import do_operation, make_cartridge


def test_cartridge_created_as_receipt(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-T1"
    )
    assert cartridge["status"] == "in_stock"
    assert cartridge["purchase_price"] == 1500.0
    assert cartridge["refill_count"] == 0
    assert cartridge["model"]["name"] == "CF259A"

    operations = client.get(
        f"/api/cartridges/{cartridge['id']}/operations", headers=auth
    ).json()
    assert len(operations) == 1
    assert operations[0]["type"] == "receipt"
    assert operations[0]["to_status"] == "in_stock"
    assert operations[0]["cost"] == 1500.0

    duplicate = client.post(
        "/api/cartridges",
        json={"inventory_no": "CRT-T1", "model_id": base_data["cartridge_model"]["id"]},
        headers=auth,
    )
    assert duplicate.status_code == 409

    unknown_model = client.post(
        "/api/cartridges",
        json={"inventory_no": "CRT-T2", "model_id": 9999},
        headers=auth,
    )
    assert unknown_model.status_code == 404


def test_full_lifecycle(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-T1"
    )
    cartridge_id = cartridge["id"]
    employee_id = base_data["employee"]["id"]
    printer_id = base_data["printer"]["id"]

    issue = do_operation(
        client, auth, cartridge_id, "issue", employee_id=employee_id
    )
    assert (issue["from_status"], issue["to_status"]) == ("in_stock", "issued")
    assert issue["employee"]["id"] == employee_id

    installed = do_operation(
        client, auth, cartridge_id, "install", printer_id=printer_id
    )
    assert (installed["from_status"], installed["to_status"]) == (
        "issued",
        "installed",
    )
    assert installed["printer"]["id"] == printer_id

    uninstalled = do_operation(client, auth, cartridge_id, "uninstall")
    assert uninstalled["to_status"] == "in_stock"
    assert uninstalled["printer"]["id"] == printer_id

    sent = do_operation(
        client,
        auth,
        cartridge_id,
        "send_refill",
        document_no="ЗП-1",
        service_provider_id=base_data["service_provider"]["id"],
        expected_return_date="2026-12-31",
    )
    assert sent["to_status"] == "in_refill"
    assert sent["service_provider"]["id"] == base_data["service_provider"]["id"]
    assert sent["expected_return_date"] == "2026-12-31"

    in_service = client.get(f"/api/cartridges/{cartridge_id}", headers=auth).json()
    assert in_service["service_provider"]["name"] == "ООО «Сервис-Тест»"
    assert in_service["expected_return_date"] == "2026-12-31"
    assert in_service["service_since"] is not None

    refilled = do_operation(client, auth, cartridge_id, "refill_done", cost=700)
    assert refilled["to_status"] == "in_stock"
    assert refilled["cost"] == 700.0
    assert refilled["result"] == "refilled"
    assert refilled["service_provider"]["id"] == base_data["service_provider"]["id"]

    detail = client.get(f"/api/cartridges/{cartridge_id}", headers=auth).json()
    assert detail["refill_count"] == 1
    assert detail["service_provider"] is None
    assert detail["expected_return_date"] is None
    assert detail["service_since"] is None

    written_off = do_operation(client, auth, cartridge_id, "write_off")
    assert written_off["to_status"] == "written_off"

    do_operation(client, auth, cartridge_id, "write_off", expected=409)
    do_operation(client, auth, cartridge_id, "issue", expected=409, employee_id=employee_id)

    history = client.get(
        f"/api/cartridges/{cartridge_id}/operations", headers=auth
    ).json()
    assert len(history) == 7
    assert [item["type"] for item in history][0] == "write_off"


def test_invalid_transitions(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-T1"
    )
    cartridge_id = cartridge["id"]

    do_operation(client, auth, cartridge_id, "return", expected=409)
    do_operation(client, auth, cartridge_id, "uninstall", expected=409)
    do_operation(client, auth, cartridge_id, "refill_done", expected=409)
    do_operation(client, auth, cartridge_id, "install", expected=422)
    do_operation(client, auth, cartridge_id, "issue", expected=422)
    do_operation(client, auth, cartridge_id, "receipt", expected=400)

    inactive = client.patch(
        f"/api/employees/{base_data['employee']['id']}",
        json={"is_active": False},
        headers=auth,
    )
    assert inactive.status_code == 200
    do_operation(
        client,
        auth,
        cartridge_id,
        "issue",
        expected=409,
        employee_id=base_data["employee"]["id"],
    )


def test_non_refillable_model_cannot_be_sent_to_refill(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    model = client.post(
        "/api/cartridge-models",
        json={"vendor": "HP", "name": "CF258X", "refillable": False},
        headers=auth,
    ).json()
    cartridge = make_cartridge(client, auth, model["id"], "CRT-NR1")
    do_operation(client, auth, cartridge["id"], "send_refill", expected=409)


def test_cartridge_delete_rules(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-T1"
    )
    deleted = client.delete(f"/api/cartridges/{cartridge['id']}", headers=auth)
    assert deleted.status_code == 204

    used = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-T2"
    )
    do_operation(
        client,
        auth,
        used["id"],
        "issue",
        employee_id=base_data["employee"]["id"],
    )
    blocked = client.delete(f"/api/cartridges/{used['id']}", headers=auth)
    assert blocked.status_code == 409


def test_cartridge_filters_and_pagination(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    model_id = base_data["cartridge_model"]["id"]
    make_cartridge(client, auth, model_id, "CRT-T1")
    second = make_cartridge(client, auth, model_id, "CRT-T2")
    make_cartridge(client, auth, model_id, "CRT-T3")
    do_operation(
        client,
        auth,
        second["id"],
        "issue",
        employee_id=base_data["employee"]["id"],
    )

    issued = client.get("/api/cartridges?status=issued", headers=auth).json()
    assert issued["total"] == 1
    assert issued["items"][0]["inventory_no"] == "CRT-T2"

    search = client.get("/api/cartridges?q=CF259A", headers=auth).json()
    assert search["total"] == 3

    page = client.get(
        "/api/cartridges?skip=1&limit=1&status=in_stock", headers=auth
    ).json()
    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert page["items"][0]["inventory_no"] == "CRT-T1"


def test_issue_attribution_to_entity_and_department(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-ATTR"
    )
    issued = do_operation(
        client, auth, cartridge["id"], "issue", employee_id=base_data["employee"]["id"]
    )
    assert issued["department"]["id"] == base_data["department"]["id"]
    assert issued["legal_entity"]["id"] == base_data["legal_entity"]["id"]

    returned = do_operation(client, auth, cartridge["id"], "return")
    assert returned["department"]["id"] == base_data["department"]["id"]

    sent = do_operation(
        client,
        auth,
        cartridge["id"],
        "send_refill",
        service_provider_id=base_data["service_provider"]["id"],
    )
    assert sent["department"]["id"] == base_data["department"]["id"]
    assert sent["service_provider"]["id"] == base_data["service_provider"]["id"]

    refilled = do_operation(client, auth, cartridge["id"], "refill_done", cost=500)
    assert refilled["department"]["id"] == base_data["department"]["id"]
    assert refilled["legal_entity"]["id"] == base_data["legal_entity"]["id"]
    assert refilled["service_provider"]["id"] == base_data["service_provider"]["id"]
    assert refilled["result"] == "refilled"
