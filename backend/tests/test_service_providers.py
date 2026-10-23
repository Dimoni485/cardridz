from fastapi.testclient import TestClient
from tests.conftest import do_operation, make_cartridge


def test_service_provider_crud(
    client: TestClient, auth: dict[str, str]
) -> None:
    created = client.post(
        "/api/service-providers",
        json={
            "name": "ООО «Ремонт-Плюс»",
            "inn": "7708888888",
            "contact_person": "Пётр Сидоров",
            "phone": "+7 (495) 300-10-10",
        },
        headers=auth,
    )
    assert created.status_code == 201, created.text
    provider = created.json()

    duplicate = client.post(
        "/api/service-providers",
        json={"name": "ООО «Ремонт-Плюс»"},
        headers=auth,
    )
    assert duplicate.status_code == 409

    updated = client.patch(
        f"/api/service-providers/{provider['id']}",
        json={"contact_person": "Пётр Петров", "is_active": False},
        headers=auth,
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    filtered = client.get(
        "/api/service-providers?active_only=true", headers=auth
    ).json()
    assert filtered == []

    deleted = client.delete(f"/api/service-providers/{provider['id']}", headers=auth)
    assert deleted.status_code == 204


def test_provider_required_for_send(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-SP0"
    )
    response = client.post(
        f"/api/cartridges/{cartridge['id']}/operations",
        json={"type": "send_refill"},
        headers=auth,
    )
    assert response.status_code == 422
    assert "сервисную организацию" in response.json()["detail"]


def test_write_off_from_service_keeps_provider(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-SP1"
    )
    do_operation(
        client,
        auth,
        cartridge["id"],
        "send_restore",
        service_provider_id=base_data["service_provider"]["id"],
    )
    written_off = do_operation(client, auth, cartridge["id"], "write_off")
    assert written_off["to_status"] == "written_off"
    assert written_off["result"] == "unrepairable"
    assert (
        written_off["service_provider"]["id"]
        == base_data["service_provider"]["id"]
    )

    detail = client.get(f"/api/cartridges/{cartridge['id']}", headers=auth).json()
    assert detail["service_provider"] is None


def test_provider_in_use_cannot_be_deleted(
    client: TestClient, auth: dict[str, str], base_data: dict
) -> None:
    cartridge = make_cartridge(
        client, auth, base_data["cartridge_model"]["id"], "CRT-SP2"
    )
    do_operation(
        client,
        auth,
        cartridge["id"],
        "send_refill",
        service_provider_id=base_data["service_provider"]["id"],
    )
    blocked = client.delete(
        f"/api/service-providers/{base_data['service_provider']['id']}", headers=auth
    )
    assert blocked.status_code == 409
