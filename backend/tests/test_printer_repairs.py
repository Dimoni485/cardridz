from datetime import date, timedelta

from fastapi.testclient import TestClient


def _send_to_repair(
    client: TestClient,
    auth: dict[str, str],
    printer_id: int,
    provider_id: int,
    expected: int = 201,
    **payload,
) -> dict:
    response = client.post(
        f"/api/printers/{printer_id}/repairs",
        json={
            "service_provider_id": provider_id,
            "expected_return_date": (date.today() + timedelta(days=7)).isoformat(),
            **payload,
        },
        headers=auth,
    )
    assert response.status_code == expected, response.text
    return response.json()


def _close_repair(
    client: TestClient,
    auth: dict[str, str],
    printer_id: int,
    repair_id: int,
    result: str = "repaired",
    cost: float | None = 5000,
) -> dict:
    response = client.post(
        f"/api/printers/{printer_id}/repairs/{repair_id}/close",
        json={"result": result, "cost": cost, "comment": "Готово"},
        headers=auth,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_printer_repair_lifecycle(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    printer_id = base_data["printer"]["id"]
    provider_id = base_data["service_provider"]["id"]

    repair = _send_to_repair(
        client,
        auth,
        printer_id,
        provider_id,
        document_no="РМ-1",
    )
    assert repair["status"] == "in_service"
    assert repair["service_provider"]["id"] == provider_id
    assert repair["document_no"] == "РМ-1"
    assert repair["department"]["name"] == "IT-отдел"

    printer = client.get(f"/api/printers/{printer_id}", headers=auth).json()
    assert printer["status"] == "repair"
    assert printer["service_provider"]["id"] == provider_id
    assert printer["service_since"] is not None
    assert printer["expected_return_date"] is not None

    duplicate = _send_to_repair(
        client, auth, printer_id, provider_id, expected=409
    )
    assert duplicate["detail"] == "Принтер уже находится в ремонте"

    blocked_update = client.patch(
        f"/api/printers/{printer_id}", json={"status": "active"}, headers=auth
    )
    assert blocked_update.status_code == 409

    history = client.get(f"/api/printers/{printer_id}/repairs", headers=auth).json()
    assert len(history) == 1

    closed = _close_repair(client, auth, printer_id, repair["id"])
    assert closed["status"] == "returned"
    assert closed["result"] == "repaired"
    assert closed["cost"] == 5000.0
    assert closed["returned_at"] is not None

    printer = client.get(f"/api/printers/{printer_id}", headers=auth).json()
    assert printer["status"] == "active"
    assert printer["service_provider"] is None
    assert printer["service_since"] is None

    again = client.post(
        f"/api/printers/{printer_id}/repairs/{repair['id']}/close",
        json={"result": "repaired", "cost": 100},
        headers=auth,
    )
    assert again.status_code == 409


def test_failed_repair_keeps_printer_in_repair(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    printer_id = base_data["printer"]["id"]
    provider_id = base_data["service_provider"]["id"]
    repair = _send_to_repair(client, auth, printer_id, provider_id)
    closed = _close_repair(
        client, auth, printer_id, repair["id"], result="unrepairable", cost=0
    )
    assert closed["status"] == "returned"
    printer = client.get(f"/api/printers/{printer_id}", headers=auth).json()
    assert printer["status"] == "repair"


def test_retired_printer_cannot_be_sent(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    printer_id = base_data["printer"]["id"]
    client.patch(f"/api/printers/{printer_id}", json={"status": "retired"}, headers=auth)
    _send_to_repair(
        client,
        auth,
        printer_id,
        base_data["service_provider"]["id"],
        expected=409,
    )


def test_printer_with_repairs_cannot_be_deleted(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    printer_id = base_data["printer"]["id"]
    _send_to_repair(
        client, auth, printer_id, base_data["service_provider"]["id"]
    )
    response = client.delete(f"/api/printers/{printer_id}", headers=auth)
    assert response.status_code == 409


def test_repair_cost_in_usage_and_service_reports(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    printer_id = base_data["printer"]["id"]
    provider_id = base_data["service_provider"]["id"]
    repair = _send_to_repair(client, auth, printer_id, provider_id)
    _close_repair(client, auth, printer_id, repair["id"], cost=3000)

    month = date.today().strftime("%Y-%m")

    usage = client.get(f"/api/reports/usage?month={month}", headers=auth).json()
    row = usage["rows"][0]
    assert row["repair_cost"] == 3000.0
    assert row["total_cost"] == row["cartridges_cost"] + row["service_cost"] + 3000.0
    assert usage["totals"]["repair_cost"] == 3000.0

    service = client.get(f"/api/reports/service?month={month}", headers=auth).json()
    provider_row = service["rows"][0]
    assert provider_row["printer_sent_count"] == 1
    assert provider_row["printer_returned_count"] == 1
    assert provider_row["printer_cost"] == 3000.0
    assert provider_row["printer_outstanding_count"] == 0
    assert service["totals"]["printer_cost"] == 3000.0
    assert service["printers_outstanding"] == []
