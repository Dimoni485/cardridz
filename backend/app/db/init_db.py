import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    CartridgeModel,
    Department,
    Employee,
    LegalEntity,
    Printer,
    PrinterModel,
    PrinterRepair,
    ServiceProvider,
    User,
)
from app.models.enums import (
    CartridgeColor,
    CartridgeKind,
    OperationType,
    PrinterRepairStatus,
    PrinterStatus,
    ServiceResult,
    UserRole,
)
from app.schemas.cartridge import OperationCreate
from app.services.cartridge_service import create_cartridge, perform_operation

logger = logging.getLogger(__name__)


def create_schema() -> None:
    import app.models  # noqa: F401  (register all mappers)

    Base.metadata.create_all(bind=engine)


def seed_admin(db: Session) -> None:
    exists = db.scalar(select(User).where(User.username == settings.admin_username))
    if exists:
        return
    db.add(
        User(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            full_name=settings.admin_full_name,
            role=UserRole.ADMIN.value,
        )
    )
    db.commit()
    logger.warning(
        "Создан администратор '%s'. Смените пароль через переменную ADMIN_PASSWORD.",
        settings.admin_username,
    )


def _days_ago(days: int, hour: int = 10) -> datetime:
    moment = datetime.now(timezone.utc) - timedelta(days=days)
    return moment.replace(hour=hour, minute=0, second=0, microsecond=0)


def seed_demo(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(CartridgeModel)):
        return

    admin = db.scalar(select(User).where(User.username == settings.admin_username))
    if admin is None:
        return

    alpha = LegalEntity(
        name="ООО «Альфа»",
        inn="7701234567",
        notes="Головной офис",
    )
    beta = LegalEntity(
        name="ООО «Бета»",
        inn="7707654321",
        notes="Обособленное подразделение",
    )
    db.add_all([alpha, beta])
    db.flush()

    bookkeeping = Department(legal_entity=alpha, name="Бухгалтерия")
    hr = Department(legal_entity=alpha, name="Отдел кадров")
    it_department = Department(legal_entity=alpha, name="IT-отдел")
    sales = Department(legal_entity=beta, name="Отдел продаж")
    directorate = Department(legal_entity=beta, name="Дирекция")
    db.add_all([bookkeeping, hr, it_department, sales, directorate])
    db.flush()

    refill_service = ServiceProvider(
        name="ООО «РефиллСервис»",
        inn="7704444444",
        contact_person="Сергей Иванов",
        phone="+7 (495) 200-10-10",
        email="service@refill.example",
        notes="Заправка картриджей",
    )
    restore_service = ServiceProvider(
        name="ООО «Картридж-Мастер»",
        inn="7705555555",
        contact_person="Анна Петрова",
        phone="+7 (495) 200-20-20",
        email="info@cartmaster.example",
        notes="Восстановление картриджей",
    )
    office_service = ServiceProvider(
        name="ООО «ОфисТехСервис»",
        inn="7706666666",
        contact_person="Михаил Орлов",
        phone="+7 (495) 200-30-30",
        email="repair@officeservice.example",
        notes="Ремонт принтеров",
    )
    db.add_all([refill_service, restore_service, office_service])
    db.flush()

    employees = [
        Employee(
            full_name="Иванов Алексей Петрович",
            department=bookkeeping,
            position="Главный бухгалтер",
            email="ivanov@example.com",
            phone="+7 (495) 100-01-01",
        ),
        Employee(
            full_name="Смирнова Ольга Викторовна",
            department=hr,
            position="Инспектор по кадрам",
            email="smirnova@example.com",
            phone="+7 (495) 100-01-02",
        ),
        Employee(
            full_name="Кузнецов Дмитрий Сергеевич",
            department=it_department,
            position="Системный администратор",
            email="kuznetsov@example.com",
            phone="+7 (495) 100-01-03",
        ),
        Employee(
            full_name="Петрова Мария Игоревна",
            department=sales,
            position="Менеджер по продажам",
            email="petrova@example.com",
            phone="+7 (495) 100-01-04",
        ),
        Employee(
            full_name="Соколов Андрей Николаевич",
            department=directorate,
            position="Генеральный директор",
            email="sokolov@example.com",
            phone="+7 (495) 100-01-05",
        ),
    ]
    db.add_all(employees)
    db.flush()

    hp_m404 = PrinterModel(vendor="HP", name="LaserJet Pro M404dn")
    hp_m507 = PrinterModel(vendor="HP", name="LaserJet Enterprise M507dn")
    canon_lbp = PrinterModel(vendor="Canon", name="i-SENSYS LBP223dw")
    kyocera_m2040 = PrinterModel(vendor="Kyocera", name="ECOSYS M2040dn")
    brother_l2350 = PrinterModel(vendor="Brother", name="HL-L2350DW")
    printer_models = [hp_m404, hp_m507, canon_lbp, kyocera_m2040, brother_l2350]
    db.add_all(printer_models)
    db.flush()

    cf259a = CartridgeModel(
        vendor="HP",
        name="CF259A",
        kind=CartridgeKind.ORIGINAL,
        color=CartridgeColor.BLACK,
        resource_pages=3000,
        refillable=False,
        min_stock=2,
    )
    cf259a_compat = CartridgeModel(
        vendor="HP",
        name="CF259A (совместимый)",
        kind=CartridgeKind.COMPATIBLE,
        color=CartridgeColor.BLACK,
        resource_pages=3000,
        refillable=True,
        min_stock=4,
    )
    cf258x = CartridgeModel(
        vendor="HP",
        name="CF258X",
        kind=CartridgeKind.ORIGINAL,
        color=CartridgeColor.BLACK,
        resource_pages=10000,
        refillable=False,
        min_stock=0,
    )
    canon_057 = CartridgeModel(
        vendor="Canon",
        name="057",
        kind=CartridgeKind.ORIGINAL,
        color=CartridgeColor.BLACK,
        resource_pages=3100,
        refillable=True,
        min_stock=1,
    )
    tk1170 = CartridgeModel(
        vendor="Kyocera",
        name="TK-1170",
        kind=CartridgeKind.ORIGINAL,
        color=CartridgeColor.BLACK,
        resource_pages=7200,
        refillable=True,
        min_stock=0,
    )
    tn2420 = CartridgeModel(
        vendor="Brother",
        name="TN-2420",
        kind=CartridgeKind.ORIGINAL,
        color=CartridgeColor.BLACK,
        resource_pages=3000,
        refillable=True,
        min_stock=1,
    )
    cartridge_models = [cf259a, cf259a_compat, cf258x, canon_057, tk1170, tn2420]
    db.add_all(cartridge_models)
    db.flush()

    cf259a.printer_models = [hp_m404]
    cf259a_compat.printer_models = [hp_m404]
    cf258x.printer_models = [hp_m507]
    canon_057.printer_models = [canon_lbp]
    tk1170.printer_models = [kyocera_m2040]
    tn2420.printer_models = [brother_l2350]

    printers = [
        Printer(
            inventory_no="PRN-001",
            serial_no="VNC3J00001",
            model=hp_m404,
            location="каб. 101, Бухгалтерия",
            ip_address="192.168.10.11",
            employee=employees[0],
            status=PrinterStatus.ACTIVE,
        ),
        Printer(
            inventory_no="PRN-002",
            serial_no="VNC3J00002",
            model=hp_m404,
            location="каб. 102, Отдел кадров",
            ip_address="192.168.10.12",
            employee=employees[1],
            status=PrinterStatus.ACTIVE,
        ),
        Printer(
            inventory_no="PRN-003",
            serial_no="CNB9K00003",
            model=hp_m507,
            location="каб. 201, Дирекция",
            ip_address="192.168.10.21",
            employee=employees[4],
            status=PrinterStatus.ACTIVE,
        ),
        Printer(
            inventory_no="PRN-004",
            serial_no="CNL2A00004",
            model=canon_lbp,
            location="каб. 103, Отдел продаж",
            ip_address="192.168.10.13",
            employee=employees[3],
            status=PrinterStatus.ACTIVE,
        ),
        Printer(
            inventory_no="PRN-005",
            serial_no="KYM7B00005",
            model=kyocera_m2040,
            location="каб. 202, IT-отдел",
            ip_address="192.168.10.22",
            employee=employees[2],
            status=PrinterStatus.ACTIVE,
        ),
        Printer(
            inventory_no="PRN-006",
            serial_no="BRL4C00006",
            model=brother_l2350,
            location="каб. 203, IT-отдел",
            ip_address="192.168.10.23",
            employee=employees[2],
            status=PrinterStatus.REPAIR,
        ),
    ]
    db.add_all(printers)
    db.flush()

    prn002_department = printers[1].employee.department
    prn004_department = printers[3].employee.department
    prn006_department = printers[5].employee.department
    db.add_all(
        [
            PrinterRepair(
                printer=printers[1],
                service_provider=office_service,
                status=PrinterRepairStatus.RETURNED.value,
                sent_at=_days_ago(70),
                expected_return_date=(_days_ago(70) + timedelta(days=7)).date(),
                returned_at=_days_ago(65),
                document_no="РМ-11",
                cost=Decimal("4200.00"),
                result=ServiceResult.REPAIRED.value,
                legal_entity_id=prn002_department.legal_entity_id,
                department_id=prn002_department.id,
                comment="Замена узла подачи бумаги",
            ),
            PrinterRepair(
                printer=printers[3],
                service_provider=office_service,
                status=PrinterRepairStatus.RETURNED.value,
                sent_at=_days_ago(40),
                expected_return_date=(_days_ago(40) + timedelta(days=7)).date(),
                returned_at=_days_ago(10),
                document_no="РМ-15",
                cost=Decimal("3500.00"),
                result=ServiceResult.REPAIRED.value,
                legal_entity_id=prn004_department.legal_entity_id,
                department_id=prn004_department.id,
                comment="Ремонт механизма подачи",
            ),
            PrinterRepair(
                printer=printers[5],
                service_provider=office_service,
                status=PrinterRepairStatus.IN_SERVICE.value,
                sent_at=_days_ago(12),
                expected_return_date=date.today() + timedelta(days=5),
                document_no="РМ-17",
                legal_entity_id=prn006_department.legal_entity_id,
                department_id=prn006_department.id,
                comment="Не захватывает бумагу",
            ),
        ]
    )
    printers[5].service_provider_id = office_service.id
    printers[5].service_since = _days_ago(12)
    printers[5].expected_return_date = date.today() + timedelta(days=5)
    db.flush()

    def add(
        inventory_no: str,
        model: CartridgeModel,
        price: str,
        received_days_ago: int,
        operations: list[tuple[OperationType, dict, int]],
    ) -> None:
        cartridge = create_cartridge(
            db,
            inventory_no=inventory_no,
            serial_no=None,
            model_id=model.id,
            purchase_price=Decimal(price),
            purchase_date=date.today() - timedelta(days=received_days_ago),
            notes=None,
            comment="Первичный приход",
            user_id=admin.id,
            received_at=_days_ago(received_days_ago),
        )
        db.flush()
        cartridge.created_at = _days_ago(received_days_ago)
        cartridge.updated_at = _days_ago(received_days_ago)
        for op_type, kwargs, days in operations:
            perform_operation(
                db,
                cartridge,
                OperationCreate(
                    type=op_type, occurred_at=_days_ago(days), **kwargs
                ),
                admin.id,
            )

    add("CRT-0001", cf259a, "4200.00", 60, [])
    add(
        "CRT-0002",
        cf259a,
        "4200.00",
        45,
        [(OperationType.ISSUE, {"employee_id": employees[0].id}, 30)],
    )
    add(
        "CRT-0003",
        cf259a_compat,
        "1450.00",
        90,
        [(OperationType.INSTALL, {"printer_id": printers[0].id}, 70)],
    )
    add(
        "CRT-0004",
        cf259a_compat,
        "1450.00",
        85,
        [(OperationType.INSTALL, {"printer_id": printers[1].id}, 65)],
    )
    add("CRT-0005", cf259a_compat, "1450.00", 40, [])
    add(
        "CRT-0006",
        canon_057,
        "3900.00",
        75,
        [
            (OperationType.ISSUE, {"employee_id": employees[3].id}, 60),
            (
                OperationType.SEND_REFILL,
                {
                    "document_no": "ЗП-14",
                    "service_provider_id": refill_service.id,
                    "expected_return_date": (
                        _days_ago(50) + timedelta(days=7)
                    ).date(),
                },
                50,
            ),
            (
                OperationType.REFILL_DONE,
                {"cost": Decimal("700.00"), "document_no": "ЗП-14"},
                42,
            ),
        ],
    )
    add(
        "CRT-0007",
        tk1170,
        "5100.00",
        120,
        [
            (
                OperationType.SEND_REFILL,
                {
                    "document_no": "ЗП-08",
                    "service_provider_id": refill_service.id,
                    "expected_return_date": (
                        _days_ago(110) + timedelta(days=7)
                    ).date(),
                },
                110,
            ),
            (
                OperationType.REFILL_DONE,
                {"cost": Decimal("900.00"), "document_no": "ЗП-08"},
                100,
            ),
            (
                OperationType.SEND_REFILL,
                {
                    "document_no": "ЗП-21",
                    "service_provider_id": refill_service.id,
                    "expected_return_date": (
                        _days_ago(80) + timedelta(days=7)
                    ).date(),
                },
                80,
            ),
            (
                OperationType.REFILL_DONE,
                {"cost": Decimal("900.00"), "document_no": "ЗП-21"},
                72,
            ),
            (OperationType.INSTALL, {"printer_id": printers[4].id}, 60),
        ],
    )
    add("CRT-0008", tn2420, "3100.00", 35, [])
    add(
        "CRT-0009",
        tn2420,
        "3100.00",
        150,
        [
            (OperationType.INSTALL, {"printer_id": printers[5].id}, 140),
            (
                OperationType.WRITE_OFF,
                {"comment": "Не восстанавливается, повреждён фотобарабан"},
                20,
            ),
        ],
    )
    add(
        "CRT-0010",
        cf259a_compat,
        "1450.00",
        30,
        [
            (
                OperationType.SEND_REFILL,
                {
                    "document_no": "ЗП-25",
                    "service_provider_id": refill_service.id,
                    "expected_return_date": (
                        _days_ago(7) + timedelta(days=3)
                    ).date(),
                },
                7,
            )
        ],
    )
    add("CRT-0011", cf259a_compat, "1450.00", 20, [])
    add(
        "CRT-0012",
        canon_057,
        "3900.00",
        25,
        [
            (
                OperationType.SEND_RESTORE,
                {
                    "document_no": "ВС-3",
                    "service_provider_id": restore_service.id,
                    "expected_return_date": (
                        _days_ago(5) + timedelta(days=7)
                    ).date(),
                },
                5,
            )
        ],
    )
    add(
        "CRT-0013",
        cf258x,
        "8700.00",
        55,
        [(OperationType.ISSUE, {"employee_id": employees[1].id}, 15)],
    )
    add(
        "CRT-0014",
        cf258x,
        "8700.00",
        95,
        [(OperationType.INSTALL, {"printer_id": printers[2].id}, 80)],
    )
    add(
        "CRT-0015",
        cf259a_compat,
        "1450.00",
        70,
        [
            (OperationType.ISSUE, {"employee_id": employees[0].id}, 50),
            (OperationType.RETURN, {}, 45),
            (OperationType.ISSUE, {"employee_id": employees[1].id}, 12),
            (OperationType.RETURN, {}, 8),
        ],
    )
    add(
        "CRT-0016",
        canon_057,
        "3900.00",
        55,
        [
            (OperationType.ISSUE, {"employee_id": employees[3].id}, 40),
            (OperationType.INSTALL, {"printer_id": printers[3].id}, 35),
            (OperationType.UNINSTALL, {}, 20),
        ],
    )
    add(
        "CRT-0017",
        tn2420,
        "3100.00",
        30,
        [(OperationType.ISSUE, {"employee_id": employees[2].id}, 11)],
    )
    add(
        "CRT-0018",
        tk1170,
        "5100.00",
        80,
        [
            (OperationType.ISSUE, {"employee_id": employees[4].id}, 35),
            (OperationType.RETURN, {}, 30),
            (
                OperationType.SEND_REFILL,
                {
                    "document_no": "ЗП-31",
                    "service_provider_id": refill_service.id,
                    "expected_return_date": (
                        _days_ago(25) + timedelta(days=7)
                    ).date(),
                },
                25,
            ),
            (
                OperationType.REFILL_DONE,
                {"cost": Decimal("900.00"), "document_no": "ЗП-31"},
                20,
            ),
        ],
    )
    add(
        "CRT-0019",
        cf259a,
        "4200.00",
        45,
        [
            (OperationType.ISSUE, {"employee_id": employees[3].id}, 33),
            (OperationType.RETURN, {}, 28),
            (OperationType.ISSUE, {"employee_id": employees[0].id}, 10),
        ],
    )

    db.commit()
    logger.info("Демонстрационные данные созданы")


def init_db() -> None:
    create_schema()
    with SessionLocal() as db:
        seed_admin(db)
        if settings.seed_demo:
            seed_demo(db)
