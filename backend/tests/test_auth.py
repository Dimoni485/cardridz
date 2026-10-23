from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_endpoints_require_auth(client: TestClient) -> None:
    assert client.get("/api/cartridges").status_code == 401
    assert client.get("/api/reports/summary").status_code == 401


def test_login_and_me(client: TestClient) -> None:
    bad = client.post(
        "/api/auth/login", json={"username": "testadmin", "password": "wrong"}
    )
    assert bad.status_code == 401

    response = client.post(
        "/api/auth/login", json={"username": "testadmin", "password": "testpass"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "testadmin"

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "testadmin"


def test_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/cartridges", headers={"Authorization": "Bearer broken.token.value"}
    )
    assert response.status_code == 401


def test_change_password(client: TestClient, auth: dict[str, str]) -> None:
    wrong = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong", "new_password": "newpassword1"},
        headers=auth,
    )
    assert wrong.status_code == 400

    changed = client.post(
        "/api/auth/change-password",
        json={"current_password": "testpass", "new_password": "newpassword1"},
        headers=auth,
    )
    assert changed.status_code == 200

    old_login = client.post(
        "/api/auth/login", json={"username": "testadmin", "password": "testpass"}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/auth/login", json={"username": "testadmin", "password": "newpassword1"}
    )
    assert new_login.status_code == 200

    restored = client.post(
        "/api/auth/change-password",
        json={"current_password": "newpassword1", "new_password": "testpass"},
        headers=auth,
    )
    assert restored.status_code == 200
