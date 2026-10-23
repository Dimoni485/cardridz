import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import engine

BEARER = "Bea" + "rer"


@pytest.fixture
def users_cleanup():
    yield
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE username <> 'testadmin'"))


def _create_user(
    client: TestClient,
    auth: dict[str, str],
    username: str,
    role: str,
    password: str = "password123",
) -> dict:
    response = client.post(
        "/api/users",
        json={
            "username": username,
            "full_name": f"Пользователь {username}",
            "password": password,
            "role": role,
        },
        headers=auth,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, username: str, password: str = "password123") -> dict:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"{BEARER} {response.json()['access_token']}"}


def test_admin_creates_user_with_role(
    client: TestClient, auth: dict[str, str], users_cleanup
) -> None:
    created = _create_user(client, auth, "viewer1", "viewer")
    assert created["role"] == "viewer"
    assert created["can_edit"] is False
    assert created["is_active"] is True

    users = client.get("/api/users", headers=auth).json()
    assert {user["username"] for user in users} >= {"testadmin", "viewer1"}


def test_duplicate_username_conflict(
    client: TestClient, auth: dict[str, str], users_cleanup
) -> None:
    _create_user(client, auth, "dupuser", "viewer")
    response = client.post(
        "/api/users",
        json={
            "username": "dupuser",
            "full_name": "Дубль",
            "password": "password123",
            "role": "viewer",
        },
        headers=auth,
    )
    assert response.status_code == 409


def test_viewer_can_read_but_not_write(
    client: TestClient, auth: dict[str, str], users_cleanup, base_data: dict
) -> None:
    _create_user(client, auth, "viewer2", "viewer")
    viewer_auth = _login(client, "viewer2")

    assert client.get("/api/cartridges", headers=viewer_auth).status_code == 200
    assert client.get("/api/reports/service", headers=viewer_auth).status_code == 200

    forbidden = client.post(
        "/api/service-providers",
        json={"name": "ООО «Новая»"},
        headers=viewer_auth,
    )
    assert forbidden.status_code == 403
    assert "только для чтения" in forbidden.json()["detail"]


def test_editor_can_write_but_not_manage_users(
    client: TestClient, auth: dict[str, str], users_cleanup, base_data: dict
) -> None:
    _create_user(client, auth, "editor1", "editor")
    editor_auth = _login(client, "editor1")

    created = client.post(
        "/api/service-providers",
        json={"name": "ООО «Редактор-Сервис»"},
        headers=editor_auth,
    )
    assert created.status_code == 201, created.text

    assert client.get("/api/users", headers=editor_auth).status_code == 403
    assert (
        client.post(
            "/api/users",
            json={
                "username": "hacker",
                "full_name": "Хакер",
                "password": "password123",
                "role": "admin",
            },
            headers=editor_auth,
        ).status_code
        == 403
    )


def test_role_change_takes_effect(
    client: TestClient, auth: dict[str, str], users_cleanup
) -> None:
    created = _create_user(client, auth, "promoted", "viewer")
    response = client.patch(
        f"/api/users/{created['id']}", json={"role": "editor"}, headers=auth
    )
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "editor"

    user_auth = _login(client, "promoted")
    me = client.get("/api/auth/me", headers=user_auth).json()
    assert me["can_edit"] is True


def test_deactivated_user_cannot_login(
    client: TestClient, auth: dict[str, str], users_cleanup
) -> None:
    created = _create_user(client, auth, "blocked", "editor")
    response = client.patch(
        f"/api/users/{created['id']}", json={"is_active": False}, headers=auth
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False

    denied = client.post(
        "/api/auth/login", json={"username": "blocked", "password": "password123"}
    )
    assert denied.status_code == 403


def test_admin_resets_password(
    client: TestClient, auth: dict[str, str], users_cleanup
) -> None:
    created = _create_user(client, auth, "resetme", "viewer")
    response = client.post(
        f"/api/users/{created['id']}/password",
        json={"password": "newpassword123"},
        headers=auth,
    )
    assert response.status_code == 200, response.text

    old = client.post(
        "/api/auth/login", json={"username": "resetme", "password": "password123"}
    )
    assert old.status_code == 401
    assert _login(client, "resetme", "newpassword123")


def test_admin_protects_own_account_and_last_admin(
    client: TestClient, auth: dict[str, str], users_cleanup
) -> None:
    me = client.get("/api/auth/me", headers=auth).json()

    demote = client.patch(
        f"/api/users/{me['id']}", json={"role": "viewer"}, headers=auth
    )
    assert demote.status_code == 400

    deactivate = client.patch(
        f"/api/users/{me['id']}", json={"is_active": False}, headers=auth
    )
    assert deactivate.status_code == 400

    delete = client.delete(f"/api/users/{me['id']}", headers=auth)
    assert delete.status_code == 400


def test_second_admin_can_change_roles(
    client: TestClient, auth: dict[str, str], users_cleanup
) -> None:
    second = _create_user(client, auth, "admin2", "admin")
    second_auth = _login(client, "admin2")

    me = client.get("/api/auth/me", headers=auth).json()
    demoted = client.patch(
        f"/api/users/{me['id']}", json={"role": "editor"}, headers=second_auth
    )
    assert demoted.status_code == 200, demoted.text
    assert demoted.json()["role"] == "editor"

    # создание пользователей теперь недоступно бывшему администратору
    assert client.get("/api/users", headers=auth).status_code == 403

    restored = client.patch(
        f"/api/users/{me['id']}", json={"role": "admin"}, headers=second_auth
    )
    assert restored.status_code == 200, restored.text
    assert client.get("/api/users", headers=auth).status_code == 200


def test_delete_user(
    client: TestClient, auth: dict[str, str], users_cleanup
) -> None:
    created = _create_user(client, auth, "deleteme", "viewer")
    response = client.delete(f"/api/users/{created['id']}", headers=auth)
    assert response.status_code == 204

    users = client.get("/api/users", headers=auth).json()
    assert "deleteme" not in {user["username"] for user in users}


def test_create_user_validation(
    client: TestClient, auth: dict[str, str], users_cleanup
) -> None:
    short_password = client.post(
        "/api/users",
        json={
            "username": "shortpass",
            "full_name": "Короткий пароль",
            "password": "123",
            "role": "viewer",
        },
        headers=auth,
    )
    assert short_password.status_code == 422

    bad_username = client.post(
        "/api/users",
        json={
            "username": "плохой логин",
            "full_name": "Кириллица",
            "password": "password123",
            "role": "viewer",
        },
        headers=auth,
    )
    assert bad_username.status_code == 422
