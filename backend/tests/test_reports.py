from datetime import date, timedelta

from fastapi.testclient import TestClient
from tests.conftest import do_operation, make_cartridge


def test_summary_and_stock(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    model_id = base_data["cartridge_model"]["id"]
    first = make_cartridge(client, auth, model_id, "CRT-T1")
    make_cartridge(client, auth, model_id, "CRT-T2")
    do_operation(
        client,
        auth,
        first["id"],
        "issue",
        employee_id=base_data["employee"]["id"],
    )

    summary = client.get("/api/reports/summary", headers=auth).json()
    assert summary["total_cartridges"] == 2
    assert summary["total_models"] == 1
    assert summary["total_printers"] == 1
    assert summary["total_employees"] == 1
    assert summary["by_status"]["in_stock"] == 1
    assert summary["by_status"]["issued"] == 1
    assert summary["by_status"]["written_off"] == 0
    assert len(summary["low_stock"]) == 1
    assert summary["low_stock"][0]["shortage"] == 1
    assert summary["recent_operations"][0]["type"] == "issue"

    stock = client.get("/api/reports/stock", headers=auth).json()
    assert stock["totals"]["total"] == 2
    assert stock["totals"]["in_stock"] == 1
    assert stock["totals"]["issued"] == 1
    row = stock["rows"][0]
    assert row["model_id"] == model_id
    assert row["in_stock"] == 1
    assert row["issued"] == 1
    assert row["total"] == 2


def test_operations_report(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-T1"
    )
    do_operation(
        client,
        auth,
        cartridge["id"],
        "issue",
        employee_id=base_data["employee"]["id"],
    )

    today = date.today()
    report = client.get(
        f"/api/reports/operations?date_from={today}&date_to={today}", headers=auth
    ).json()
    assert report["total_operations"] == 2
    assert report["total_cost"] == 0.0
    types = {item["type"]: item["count"] for item in report["by_type"]}
    assert types == {"receipt": 1, "issue": 1}

    yesterday = today - timedelta(days=1)
    empty = client.get(
        f"/api/reports/operations?date_from={yesterday}&date_to={yesterday}",
        headers=auth,
    ).json()
    assert empty["total_operations"] == 0

    invalid = client.get(
        f"/api/reports/operations?date_from={today}&date_to={yesterday}", headers=auth
    )
    assert invalid.status_code == 400


def test_employees_report(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    model_id = base_data["cartridge_model"]["id"]
    cartridge = make_cartridge(client, auth, model_id, "CRT-T1")
    do_operation(
        client,
        auth,
        cartridge["id"],
        "issue",
        employee_id=base_data["employee"]["id"],
    )
    installed = make_cartridge(client, auth, model_id, "CRT-T2")
    do_operation(
        client,
        auth,
        installed["id"],
        "install",
        printer_id=base_data["printer"]["id"],
    )

    report = client.get("/api/reports/employees", headers=auth).json()
    row = report["rows"][0]
    assert row["department"] == "IT-отдел"
    assert row["legal_entity"] == "ООО «Тест»"
    assert row["issued"] == 1
    assert row["installed_at_printers"] == 1
    assert row["total"] == 2


def test_operations_list_and_filters(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-T1"
    )
    do_operation(
        client,
        auth,
        cartridge["id"],
        "issue",
        employee_id=base_data["employee"]["id"],
    )

    all_operations = client.get("/api/operations", headers=auth).json()
    assert all_operations["total"] == 2

    issues = client.get("/api/operations?type=issue", headers=auth).json()
    assert issues["total"] == 1
    assert issues["items"][0]["type"] == "issue"
    assert issues["items"][0]["cartridge"]["inventory_no"] == "CRT-T1"

    by_cartridge = client.get(
        f"/api/operations?cartridge_id={cartridge['id']}", headers=auth
    ).json()
    assert by_cartridge["total"] == 2

    page = client.get("/api/operations?limit=1", headers=auth).json()
    assert page["total"] == 2
    assert len(page["items"]) == 1


def test_usage_report(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    model_id = base_data["cartridge_model"]["id"]
    first = make_cartridge(client, auth, model_id, "CRT-U1")
    do_operation(
        client,
        auth,
        first["id"],
        "issue",
        employee_id=base_data["employee"]["id"],
    )

    second = make_cartridge(client, auth, model_id, "CRT-U2")
    do_operation(
        client,
        auth,
        second["id"],
        "issue",
        employee_id=base_data["employee"]["id"],
    )
    do_operation(
        client,
        auth,
        second["id"],
        "send_refill",
        service_provider_id=base_data["service_provider"]["id"],
    )
    do_operation(client, auth, second["id"], "refill_done", cost=700)

    month = date.today().strftime("%Y-%m")
    report_response = client.get(
        f"/api/reports/usage?month={month}", headers=auth
    )
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()

    assert report["totals"]["issued_count"] == 2
    assert report["totals"]["cartridges_cost"] == 3000.0
    assert report["totals"]["service_cost"] == 700.0
    assert report["totals"]["total_cost"] == 3700.0

    assert len(report["rows"]) == 1
    row = report["rows"][0]
    assert row["legal_entity_name"] == "ООО «Тест»"
    assert row["department_name"] == "IT-отдел"
    assert row["issued_count"] == 2
    assert row["cartridges_cost"] == 3000.0
    assert row["service_cost"] == 700.0
    assert row["total_cost"] == 3700.0

    assert len(report["by_legal_entity"]) == 1
    entity = report["by_legal_entity"][0]
    assert entity["legal_entity_name"] == "ООО «Тест»"
    assert entity["total_cost"] == 3700.0

    invalid = client.get("/api/reports/usage?month=2026-13", headers=auth)
    assert invalid.status_code == 422


def test_usage_report_previous_month_is_empty(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-U3"
    )
    do_operation(
        client,
        auth,
        cartridge["id"],
        "issue",
        employee_id=base_data["employee"]["id"],
    )
    previous_month = date.today().replace(day=1) - timedelta(days=1)
    report = client.get(
        f"/api/reports/usage?month={previous_month.strftime('%Y-%m')}", headers=auth
    ).json()
    assert report["rows"] == []
    assert report["totals"]["total_cost"] == 0.0


def test_service_report(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-SR1"
    )
    expected = (date.today() - timedelta(days=1)).isoformat()
    do_operation(
        client,
        auth,
        cartridge["id"],
        "send_refill",
        service_provider_id=base_data["service_provider"]["id"],
        expected_return_date=expected,
        document_no="ЗП-77",
    )

    month = date.today().strftime("%Y-%m")
    report = client.get(f"/api/reports/service?month={month}", headers=auth).json()

    row = report["rows"][0]
    assert row["provider_name"] == "ООО «Сервис-Тест»"
    assert row["sent_count"] == 1
    assert row["returned_count"] == 0
    assert row["outstanding_count"] == 1
    assert report["totals"]["sent_count"] == 1
    assert report["totals"]["outstanding_count"] == 1

    assert len(report["outstanding"]) == 1
    outstanding = report["outstanding"][0]
    assert outstanding["inventory_no"] == "CRT-SR1"
    assert outstanding["expected_return_date"] == expected
    assert outstanding["overdue"] is True
    assert outstanding["provider_name"] == "ООО «Сервис-Тест»"

    do_operation(client, auth, cartridge["id"], "refill_done", cost=650)
    report = client.get(f"/api/reports/service?month={month}", headers=auth).json()
    row = report["rows"][0]
    assert row["returned_count"] == 1
    assert row["cost"] == 650.0
    assert row["outstanding_count"] == 0
    assert report["outstanding"] == []
