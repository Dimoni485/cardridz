from fastapi.testclient import TestClient


def test_legal_entity_and_department_crud(
    client: TestClient, auth: dict[str, str]
) -> None:
    created = client.post(
        "/api/legal-entities",
        json={"name": "ООО «Вектор»", "inn": "7702222222"},
        headers=auth,
    )
    assert created.status_code == 201, created.text
    entity = created.json()
    assert entity["departments"] == []

    duplicate = client.post(
        "/api/legal-entities",
        json={"name": "ООО «Вектор»"},
        headers=auth,
    )
    assert duplicate.status_code == 409

    updated = client.patch(
        f"/api/legal-entities/{entity['id']}",
        json={"inn": "7702222223", "notes": "Новый контрагент"},
        headers=auth,
    )
    assert updated.status_code == 200
    assert updated.json()["inn"] == "7702222223"

    department = client.post(
        "/api/departments",
        json={
            "legal_entity_id": entity["id"],
            "name": "Склад",
            "room": "каб. 12",
        },
        headers=auth,
    )
    assert department.status_code == 201, department.text
    department_data = department.json()
    assert department_data["legal_entity"]["name"] == "ООО «Вектор»"
    assert department_data["room"] == "каб. 12"

    room_update = client.patch(
        f"/api/departments/{department_data['id']}",
        json={"room": "каб. 15"},
        headers=auth,
    )
    assert room_update.status_code == 200, room_update.text
    assert room_update.json()["room"] == "каб. 15"
    assert room_update.json()["name"] == "Склад"

    by_room = client.get("/api/departments?q=15", headers=auth)
    assert [item["name"] for item in by_room.json()] == ["Склад"]

    room_cleared = client.patch(
        f"/api/departments/{department_data['id']}",
        json={"room": None},
        headers=auth,
    )
    assert room_cleared.status_code == 200, room_cleared.text
    assert room_cleared.json()["room"] is None

    duplicate_department = client.post(
        "/api/departments",
        json={"legal_entity_id": entity["id"], "name": "Склад"},
        headers=auth,
    )
    assert duplicate_department.status_code == 409

    listed = client.get(
        f"/api/departments?legal_entity_id={entity['id']}", headers=auth
    )
    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()] == ["Склад"]

    entity_read = client.get(f"/api/legal-entities/{entity['id']}", headers=auth)
    assert [item["name"] for item in entity_read.json()["departments"]] == ["Склад"]

    blocked_entity = client.delete(
        f"/api/legal-entities/{entity['id']}", headers=auth
    )
    assert blocked_entity.status_code == 409

    deleted_department = client.delete(
        f"/api/departments/{department_data['id']}", headers=auth
    )
    assert deleted_department.status_code == 204

    deleted_entity = client.delete(f"/api/legal-entities/{entity['id']}", headers=auth)
    assert deleted_entity.status_code == 204


def test_department_validation(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    unknown_entity = client.post(
        "/api/departments",
        json={"legal_entity_id": 9999, "name": "Отдел"},
        headers=auth,
    )
    assert unknown_entity.status_code == 404

    unknown_department = client.post(
        "/api/employees",
        json={"full_name": "Без отдела", "department_id": 9999},
        headers=auth,
    )
    assert unknown_department.status_code == 404

    blocked = client.delete(
        f"/api/departments/{base_data['department']['id']}", headers=auth
    )
    assert blocked.status_code == 409
