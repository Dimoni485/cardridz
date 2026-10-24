import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres@127.0.0.1:5433/cardridz_test",
)
os.environ["JWT_SECRET"] = "test-secret"
os.environ["ADMIN_USERNAME"] = "testadmin"
os.environ["ADMIN_PASSWORD"] = "testpass"
os.environ["SEED_DEMO"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_db():
    yield
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE invoice_lines, invoices, operations, cartridges, "
                "printer_repairs, printers, "
                "cartridge_model_printer_model, cartridge_models, "
                "printer_models, employees, departments, legal_entities, "
                "service_providers RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture(scope="session")
def client(_schema):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "testpass"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def base_data(client: TestClient, auth: dict[str, str]) -> dict:
    printer_model = client.post(
        "/api/printer-models",
        json={"vendor": "HP", "name": "LaserJet Pro M404dn"},
        headers=auth,
    ).json()
    cartridge_model = client.post(
        "/api/cartridge-models",
        json={
            "vendor": "HP",
            "name": "CF259A",
            "printer_model_ids": [printer_model["id"]],
            "min_stock": 2,
            "refillable": True,
        },
        headers=auth,
    ).json()
    legal_entity = client.post(
        "/api/legal-entities",
        json={"name": "ООО «Тест»", "inn": "7700000000"},
        headers=auth,
    ).json()
    department = client.post(
        "/api/departments",
        json={"legal_entity_id": legal_entity["id"], "name": "IT-отдел"},
        headers=auth,
    ).json()
    service_provider = client.post(
        "/api/service-providers",
        json={"name": "ООО «Сервис-Тест»", "inn": "7709999999"},
        headers=auth,
    ).json()
    employee = client.post(
        "/api/employees",
        json={
            "full_name": "Тестов Тест Тестович",
            "department_id": department["id"],
        },
        headers=auth,
    ).json()
    printer = client.post(
        "/api/printers",
        json={
            "inventory_no": "PRN-T1",
            "model_id": printer_model["id"],
            "department_id": department["id"],
            "employee_id": employee["id"],
            "location": "каб. 1",
        },
        headers=auth,
    ).json()
    return {
        "legal_entity": legal_entity,
        "department": department,
        "printer_model": printer_model,
        "cartridge_model": cartridge_model,
        "employee": employee,
        "printer": printer,
        "service_provider": service_provider,
    }


def make_cartridge(
    client: TestClient, auth: dict[str, str], model_id: int, inventory_no: str = "CRT-T1"
) -> dict:
    response = client.post(
        "/api/cartridges",
        json={
            "inventory_no": inventory_no,
            "model_id": model_id,
            "purchase_price": 1500,
            "purchase_date": "2026-01-10",
        },
        headers=auth,
    )
    assert response.status_code == 201, response.text
    return response.json()


def do_operation(
    client: TestClient,
    auth: dict[str, str],
    cartridge_id: int,
    op_type: str,
    expected: int = 201,
    **payload,
) -> dict:
    response = client.post(
        f"/api/cartridges/{cartridge_id}/operations",
        json={"type": op_type, **payload},
        headers=auth,
    )
    assert response.status_code == expected, response.text
    return response.json()
