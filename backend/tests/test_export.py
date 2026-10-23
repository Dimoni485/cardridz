from datetime import date
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from tests.conftest import do_operation, make_cartridge


def _prepare_data(client: TestClient, auth: dict[str, str], base_data: dict) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-X1"
    )
    do_operation(
        client,
        auth,
        cartridge["id"],
        "issue",
        employee_id=base_data["employee"]["id"],
    )
    do_operation(
        client,
        auth,
        cartridge["id"],
        "send_refill",
        service_provider_id=base_data["service_provider"]["id"],
    )
    do_operation(client, auth, cartridge["id"], "refill_done", cost=700)

    printer_id = base_data["printer"]["id"]
    response = client.post(
        f"/api/printers/{printer_id}/repairs",
        json={"service_provider_id": base_data["service_provider"]["id"]},
        headers=auth,
    )
    assert response.status_code == 201, response.text
    repair_id = response.json()["id"]
    closed = client.post(
        f"/api/printers/{printer_id}/repairs/{repair_id}/close",
        json={"result": "repaired", "cost": 3000},
        headers=auth,
    )
    assert closed.status_code == 200, closed.text


def test_service_export_xlsx(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    _prepare_data(client, auth, base_data)
    today = date.today().isoformat()

    response = client.get(
        f"/api/reports/service-export?date_from={today}&date_to={today}",
        headers=auth,
    )
    assert response.status_code == 200, response.text
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "cardridz-service-" in response.headers["content-disposition"]

    workbook = load_workbook(BytesIO(response.content))
    assert workbook.sheetnames == [
        "Обслуживание",
        "Итого по юрлицам",
        "Итого по отделам",
        "Итого по сервисным организациям",
    ]

    detail = workbook["Обслуживание"]
    assert detail["A1"].value == "Отчёт по обслуживанию картриджей и принтеров"
    assert detail["A4"].value == "Дата"
    assert detail["B4"].value == "Юрлицо"
    assert detail["C4"].value == "Отдел"
    assert detail["E4"].value == "Модель"
    assert detail["G4"].value == "Вид обслуживания"
    assert detail["J4"].value == "Стоимость, ₽"

    rows = list(detail.iter_rows(min_row=5, max_row=6, values_only=True))
    assert len(rows) == 2
    objects = {row[3]: row for row in rows}
    assert objects["Картридж"][6] == "Заправка"
    assert objects["Принтер"][6] == "Ремонт"
    assert objects["Картридж"][1] == "ООО «Тест»"
    assert objects["Картридж"][2] == "IT-отдел"
    assert objects["Картридж"][9] == 700
    assert objects["Принтер"][9] == 3000

    assert detail["A7"].value == "Итого за период"
    assert detail["J7"].value == 3700

    summary = workbook["Итого по юрлицам"]
    assert str(summary["A5"].value) == "ООО «Тест»"
    assert summary["B5"].value == 700
    assert summary["C5"].value == 0
    assert summary["D5"].value == 3000
    assert summary["E5"].value == 3700
    assert summary["A6"].value == "Итого"
    assert summary["E6"].value == 3700

    departments = workbook["Итого по отделам"]
    assert str(departments["A5"].value) == "ООО «Тест»"
    assert departments["B5"].value == "IT-отдел"
    assert departments["C5"].value == 700
    assert departments["E5"].value == 3000
    assert departments["F5"].value == 3700
    assert departments["A6"].value == "Итого"
    assert departments["C6"].value == 700
    assert departments["E6"].value == 3000
    assert departments["F6"].value == 3700

    providers = workbook["Итого по сервисным организациям"]
    assert str(providers["A5"].value) == "ООО «Сервис-Тест»"
    assert providers["B5"].value == 700
    assert providers["C5"].value == 0
    assert providers["D5"].value == 3000
    assert providers["E5"].value == 3700
    assert providers["A6"].value == "Итого"
    assert providers["E6"].value == 3700


def test_service_export_invalid_period(
    client: TestClient, auth: dict[str, str]
) -> None:
    response = client.get(
        "/api/reports/service-export?date_from=2026-10-10&date_to=2026-10-01",
        headers=auth,
    )
    assert response.status_code == 400
