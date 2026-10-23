from fastapi.testclient import TestClient
from tests.conftest import do_operation, make_cartridge


def test_employee_crud(client: TestClient, auth: dict[str, str]) -> None:
    legal_entity = client.post(
        "/api/legal-entities",
        json={"name": "ООО «Ромашка»", "inn": "7701111111"},
        headers=auth,
    ).json()
    department = client.post(
        "/api/departments",
        json={"legal_entity_id": legal_entity["id"], "name": "Бухгалтерия"},
        headers=auth,
    ).json()
    other_department = client.post(
        "/api/departments",
        json={"legal_entity_id": legal_entity["id"], "name": "Отдел кадров"},
        headers=auth,
    ).json()

    created = client.post(
        "/api/employees",
        json={
            "full_name": "Иванов Иван Иванович",
            "department_id": department["id"],
            "position": "Бухгалтер",
            "email": "ivanov@example.com",
        },
        headers=auth,
    )
    assert created.status_code == 201
    employee = created.json()
    assert employee["is_active"] is True
    assert employee["department"]["name"] == "Бухгалтерия"
    assert employee["department"]["legal_entity"]["name"] == "ООО «Ромашка»"

    listed = client.get("/api/employees?q=Ромашка", headers=auth)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    by_department = client.get(
        f"/api/employees?department_id={department['id']}", headers=auth
    )
    assert len(by_department.json()) == 1

    updated = client.patch(
        f"/api/employees/{employee['id']}",
        json={"is_active": False, "position": "Старший бухгалтер"},
        headers=auth,
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert updated.json()["position"] == "Старший бухгалтер"

    moved = client.patch(
        f"/api/employees/{employee['id']}",
        json={"department_id": other_department["id"]},
        headers=auth,
    )
    assert moved.status_code == 200
    assert moved.json()["department"]["name"] == "Отдел кадров"

    active_only = client.get("/api/employees?active_only=true", headers=auth)
    assert active_only.json() == []

    deleted = client.delete(f"/api/employees/{employee['id']}", headers=auth)
    assert deleted.status_code == 204


def test_employee_in_use_cannot_be_deleted(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    employee_id = base_data["employee"]["id"]
    response = client.delete(f"/api/employees/{employee_id}", headers=auth)
    assert response.status_code == 409


def test_printer_models_and_cartridge_models(
    client: TestClient, auth: dict[str, str]
) -> None:
    printer_model = client.post(
        "/api/printer-models",
        json={"vendor": "Canon", "name": "i-SENSYS LBP223dw"},
        headers=auth,
    )
    assert printer_model.status_code == 201
    pm = printer_model.json()

    cartridge_model = client.post(
        "/api/cartridge-models",
        json={
            "vendor": "Canon",
            "name": "057",
            "color": "black",
            "kind": "original",
            "resource_pages": 3100,
            "min_stock": 1,
            "printer_model_ids": [pm["id"]],
        },
        headers=auth,
    )
    assert cartridge_model.status_code == 201, cartridge_model.text
    cm = cartridge_model.json()
    assert [item["id"] for item in cm["printer_models"]] == [pm["id"]]

    unknown_printer_model = client.post(
        "/api/cartridge-models",
        json={"vendor": "X", "name": "Y", "printer_model_ids": [9999]},
        headers=auth,
    )
    assert unknown_printer_model.status_code == 400

    updated = client.patch(
        f"/api/cartridge-models/{cm['id']}",
        json={"min_stock": 5, "printer_model_ids": []},
        headers=auth,
    )
    assert updated.status_code == 200
    assert updated.json()["min_stock"] == 5
    assert updated.json()["printer_models"] == []

    deleted_pm = client.delete(f"/api/printer-models/{pm['id']}", headers=auth)
    assert deleted_pm.status_code == 204


def test_cartridge_model_in_use_cannot_be_deleted(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    make_cartridge(client, auth, base_data["cartridge_model"]["id"])
    model_id = base_data["cartridge_model"]["id"]
    response = client.delete(f"/api/cartridge-models/{model_id}", headers=auth)
    assert response.status_code == 409


def test_printer_crud(client: TestClient, auth: dict[str, str], base_data: dict) -> None:
    printer_model_id = base_data["printer_model"]["id"]
    created = client.post(
        "/api/printers",
        json={
            "inventory_no": "PRN-T2",
            "model_id": printer_model_id,
            "location": "каб. 2",
            "ip_address": "10.0.0.5",
        },
        headers=auth,
    )
    assert created.status_code == 201, created.text
    printer = created.json()
    assert printer["model"]["id"] == printer_model_id

    duplicate = client.post(
        "/api/printers",
        json={"inventory_no": "PRN-T2", "model_id": printer_model_id},
        headers=auth,
    )
    assert duplicate.status_code == 409

    invalid_model = client.post(
        "/api/printers",
        json={"inventory_no": "PRN-T3", "model_id": 9999},
        headers=auth,
    )
    assert invalid_model.status_code == 404

    updated = client.patch(
        f"/api/printers/{printer['id']}",
        json={"status": "repair"},
        headers=auth,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "repair"

    filtered = client.get("/api/printers?status=repair", headers=auth)
    assert len(filtered.json()) == 1

    deleted = client.delete(f"/api/printers/{printer['id']}", headers=auth)
    assert deleted.status_code == 204
