from datetime import date

from fastapi.testclient import TestClient


def test_printer_department_crud(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    department = base_data["department"]
    entity = base_data["legal_entity"]

    printer = client.post(
        "/api/printers",
        json={
            "inventory_no": "PRN-D1",
            "model_id": base_data["printer_model"]["id"],
            "department_id": department["id"],
        },
        headers=auth,
    )
    assert printer.status_code == 201, printer.text
    data = printer.json()
    assert data["department"]["name"] == "IT-отдел"
    assert data["department"]["legal_entity"]["name"] == "ООО «Тест»"

    filtered = client.get(
        f"/api/printers?legal_entity_id={entity['id']}", headers=auth
    )
    assert [item["inventory_no"] for item in filtered.json()] == ["PRN-D1", "PRN-T1"]

    by_department = client.get(
        f"/api/printers?department_id={department['id']}", headers=auth
    )
    assert {item["inventory_no"] for item in by_department.json()} == {
        "PRN-D1",
        "PRN-T1",
    }

    cleared = client.patch(
        f"/api/printers/{data['id']}", json={"department_id": None}, headers=auth
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["department"] is None

    unknown = client.post(
        "/api/printers",
        json={
            "inventory_no": "PRN-D2",
            "model_id": base_data["printer_model"]["id"],
            "department_id": 9999,
        },
        headers=auth,
    )
    assert unknown.status_code == 404


def test_repair_uses_printer_department(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    entity = base_data["legal_entity"]
    department = base_data["department"]
    provider = base_data["service_provider"]

    # второй отдел того же юрлица
    other = client.post(
        "/api/departments",
        json={"legal_entity_id": entity["id"], "name": "Склад", "room": "каб. 8"},
        headers=auth,
    ).json()

    printer = client.post(
        "/api/printers",
        json={
            "inventory_no": "PRN-D3",
            "model_id": base_data["printer_model"]["id"],
            "department_id": other["id"],
            "employee_id": base_data["employee"]["id"],
        },
        headers=auth,
    ).json()

    repair = client.post(
        f"/api/printers/{printer['id']}/repairs",
        json={"service_provider_id": provider["id"], "cost": 1000},
        headers=auth,
    )
    assert repair.status_code == 201, repair.text
    body = repair.json()
    assert body["department"]["name"] == "Склад"
    assert body["legal_entity"]["name"] == "ООО «Тест»"

    closed = client.post(
        f"/api/printers/{printer['id']}/repairs/{body['id']}/close",
        json={"result": "repaired", "cost": 2500},
        headers=auth,
    )
    assert closed.status_code == 200, closed.text

    report = client.get(
        f"/api/reports/usage?month={date.today().strftime('%Y-%m')}", headers=auth
    ).json()
    department_rows = {
        (row["legal_entity_name"], row["department_name"]): row
        for row in report["rows"]
    }
    repair_row = department_rows[("ООО «Тест»", "Склад")]
    assert repair_row["repair_cost"] == 2500

    entity_rows = {row["legal_entity_name"]: row for row in report["by_legal_entity"]}
    assert entity_rows["ООО «Тест»"]["repair_cost"] == 2500
