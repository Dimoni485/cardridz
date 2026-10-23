from sqlalchemy.orm import selectinload

from app.models import Cartridge, Department, Employee, Operation, Printer

EMPLOYEE_LOADS = (
    selectinload(Employee.department).selectinload(Department.legal_entity),
)

CARTRIDGE_LOADS = (
    selectinload(Cartridge.model),
    selectinload(Cartridge.employee)
    .selectinload(Employee.department)
    .selectinload(Department.legal_entity),
    selectinload(Cartridge.printer).selectinload(Printer.model),
    selectinload(Cartridge.printer)
    .selectinload(Printer.employee)
    .selectinload(Employee.department)
    .selectinload(Department.legal_entity),
    selectinload(Cartridge.service_provider),
)

OPERATION_LOADS = (
    selectinload(Operation.cartridge).selectinload(Cartridge.model),
    selectinload(Operation.employee)
    .selectinload(Employee.department)
    .selectinload(Department.legal_entity),
    selectinload(Operation.printer).selectinload(Printer.model),
    selectinload(Operation.printer)
    .selectinload(Printer.employee)
    .selectinload(Employee.department)
    .selectinload(Department.legal_entity),
    selectinload(Operation.legal_entity),
    selectinload(Operation.department).selectinload(Department.legal_entity),
    selectinload(Operation.service_provider),
    selectinload(Operation.user),
)
