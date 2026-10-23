from fastapi import APIRouter, Depends

from app.api.deps import enforce_write_access
from app.api.routes import (
    auth,
    cartridge_models,
    cartridges,
    departments,
    employees,
    legal_entities,
    operations,
    printer_models,
    printers,
    reports,
    service_providers,
    users,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)

protected_router = APIRouter(dependencies=[Depends(enforce_write_access)])
protected_router.include_router(legal_entities.router)
protected_router.include_router(departments.router)
protected_router.include_router(employees.router)
protected_router.include_router(printer_models.router)
protected_router.include_router(cartridge_models.router)
protected_router.include_router(printers.router)
protected_router.include_router(service_providers.router)
protected_router.include_router(cartridges.router)
protected_router.include_router(operations.router)
protected_router.include_router(reports.router)
protected_router.include_router(users.router)
api_router.include_router(protected_router)
