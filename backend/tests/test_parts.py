import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def part(client: TestClient, auth: dict[str, str], base_data: dict) -> dict:
    response = client.post(
        "/api/parts",
        json={
            "name": "Ролик подачи",
            "kind": "roller",
            "vendor": "HP",
            "article": "RC2-1234",
            "min_stock": 1,
            "printer_model_ids": [base_data["printer_model"]["id"]],
        },
        headers=auth,
    )
    assert response.status_code == 201, response.text
    return response.json()


def make_unit(
    client: TestClient, auth: dict[str, str], part_id: int, inventory_no: str
) -> dict:
    response = client.post(
        f"/api/parts/{part_id}/units",
        json={"inventory_no": inventory_no, "purchase_price": 1200},
        headers=auth,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_part_crud_and_counts(
    client: TestClient, auth: dict[str, str], base_data: dict, part: dict
) -> None:
    assert part["name"] == "Ролик подачи"
    assert part["printer_models"][0]["id"] == base_data["printer_model"]["id"]
    assert part["units_total"] == 0

    unit = make_unit(client, auth, part["id"], "PART-001")
    assert unit["status"] == "in_stock"
    assert unit["part"]["name"] == "Ролик подачи"

    duplicate = client.post(
        f"/api/parts/{part['id']}/units",
        json={"inventory_no": "PART-001"},
        headers=auth,
    )
    assert duplicate.status_code == 409

    detail = client.get(f"/api/parts/{part['id']}", headers=auth).json()
    assert detail["units_total"] == 1
    assert detail["units_in_stock"] == 1
    assert detail["units_installed"] == 0

    forbidden = client.delete(f"/api/parts/{part['id']}", headers=auth)
    assert forbidden.status_code == 409

    updated = client.patch(
        f"/api/parts/{part['id']}", json={"min_stock": 3}, headers=auth
    )
    assert updated.status_code == 200
    assert updated.json()["min_stock"] == 3


def test_install_flag_and_remove(
    client: TestClient, auth: dict[str, str], base_data: dict, part: dict
) -> None:
    unit = make_unit(client, auth, part["id"], "PART-002")
    printer_id = base_data["printer"]["id"]

    installed = client.post(
        f"/api/part-units/{unit['id']}/install",
        json={"printer_id": printer_id, "comment": "замена по регламенту"},
        headers=auth,
    )
    assert installed.status_code == 200, installed.text
    body = installed.json()
    assert body["status"] == "installed"
    assert body["printer"]["id"] == printer_id
    assert body["installed_at"] is not None

    again = client.post(
        f"/api/part-units/{unit['id']}/install",
        json={"printer_id": printer_id},
        headers=auth,
    )
    assert again.status_code == 409

    history = client.get(
        "/api/part-installations?open_only=true", headers=auth
    ).json()
    assert len(history) == 1
    assert history[0]["printer"]["id"] == printer_id
    assert history[0]["part"]["name"] == "Ролик подачи"
    assert history[0]["removed_at"] is None

    flagged = client.patch(
        f"/api/part-units/{unit['id']}",
        json={"needs_replacement": True},
        headers=auth,
    )
    assert flagged.status_code == 200
    assert flagged.json()["needs_replacement"] is True

    attention = client.get(
        "/api/part-installations?needs_replacement=true", headers=auth
    ).json()
    assert len(attention) == 1
    assert attention[0]["needs_replacement"] is True

    detail = client.get(f"/api/parts/{part['id']}", headers=auth).json()
    assert detail["needs_replacement"] == 1
    assert detail["units_installed"] == 1

    removed = client.post(
        f"/api/part-units/{unit['id']}/remove",
        json={"comment": "изношен"},
        headers=auth,
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "in_stock"
    assert removed.json()["printer"] is None
    assert removed.json()["needs_replacement"] is False

    closed = client.get("/api/part-installations", headers=auth).json()
    assert closed[0]["removed_at"] is not None

    delete = client.delete(f"/api/part-units/{unit['id']}", headers=auth)
    assert delete.status_code == 409


def test_remove_with_write_off(
    client: TestClient, auth: dict[str, str], base_data: dict, part: dict
) -> None:
    unit = make_unit(client, auth, part["id"], "PART-003")
    client.post(
        f"/api/part-units/{unit['id']}/install",
        json={"printer_id": base_data["printer"]["id"]},
        headers=auth,
    )

    response = client.post(
        f"/api/part-units/{unit['id']}/remove",
        json={"write_off": True},
        headers=auth,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "written_off"


def test_part_request_lifecycle(
    client: TestClient, auth: dict[str, str], base_data: dict, part: dict
) -> None:
    second = client.post(
        "/api/parts",
        json={"name": "Термоплёнка", "kind": "fuser"},
        headers=auth,
    ).json()

    created = client.post(
        "/api/part-requests",
        json={
            "printer_id": base_data["printer"]["id"],
            "needed_by": "2026-11-01",
            "comment": "плановое ТО",
            "lines": [
                {"part_id": part["id"], "qty": 2, "note": "запас"},
                {"part_id": second["id"], "qty": 1},
            ],
        },
        headers=auth,
    )
    assert created.status_code == 201, created.text
    request = created.json()
    assert request["number"] == "ЗЧ-0001"
    assert request["status"] == "draft"
    assert request["printer"]["id"] == base_data["printer"]["id"]
    assert len(request["lines"]) == 2

    updated = client.patch(
        f"/api/part-requests/{request['id']}",
        json={"lines": [{"part_id": part["id"], "qty": 5}]},
        headers=auth,
    )
    assert updated.status_code == 200
    assert updated.json()["lines"][0]["qty"] == 5

    submitted = client.post(
        f"/api/part-requests/{request['id']}/submit", headers=auth
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["submitted_at"] is not None

    again = client.post(f"/api/part-requests/{request['id']}/submit", headers=auth)
    assert again.status_code == 409

    ordered = client.post(
        f"/api/part-requests/{request['id']}/order", headers=auth
    )
    assert ordered.json()["status"] == "ordered"

    received = client.post(
        f"/api/part-requests/{request['id']}/receive", headers=auth
    )
    assert received.json()["status"] == "received"

    cancel = client.post(f"/api/part-requests/{request['id']}/cancel", headers=auth)
    assert cancel.status_code == 409

    delete = client.delete(f"/api/part-requests/{request['id']}", headers=auth)
    assert delete.status_code == 409

    draft = client.post(
        "/api/part-requests",
        json={"printer_id": base_data["printer"]["id"], "lines": [{"part_id": part["id"]}]},
        headers=auth,
    ).json()
    cancelled = client.post(
        f"/api/part-requests/{draft['id']}/cancel", headers=auth
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    filtered = client.get(
        "/api/part-requests?status_filter=received", headers=auth
    ).json()
    assert [item["number"] for item in filtered] == ["ЗЧ-0001"]


def test_part_request_validation(
    client: TestClient, auth: dict[str, str], base_data: dict, part: dict
) -> None:
    unknown_printer = client.post(
        "/api/part-requests",
        json={"printer_id": 9999, "lines": [{"part_id": part["id"]}]},
        headers=auth,
    )
    assert unknown_printer.status_code == 404

    unknown_part = client.post(
        "/api/part-requests",
        json={
            "printer_id": base_data["printer"]["id"],
            "lines": [{"part_id": 9999, "qty": 1}],
        },
        headers=auth,
    )
    assert unknown_part.status_code == 404

    no_lines = client.post(
        "/api/part-requests",
        json={"printer_id": base_data["printer"]["id"], "lines": []},
        headers=auth,
    )
    assert no_lines.status_code == 422
