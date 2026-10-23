from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.reports import (
    EmployeesReport,
    OperationsReport,
    ServiceReport,
    StockReport,
    SummaryStats,
    UsageReport,
)
from app.services import reports
from app.services.export_service import build_service_export

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary", response_model=SummaryStats)
def summary(db: Session = Depends(get_db)) -> SummaryStats:
    return reports.get_summary(db)


@router.get("/stock", response_model=StockReport)
def stock(db: Session = Depends(get_db)) -> StockReport:
    return reports.get_stock_report(db)


@router.get("/operations", response_model=OperationsReport)
def operations(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
) -> OperationsReport:
    today = date.today()
    date_to = date_to or today
    date_from = date_from or (date_to - timedelta(days=29))
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="Дата начала позже даты окончания")
    return reports.get_operations_report(db, date_from, date_to)


@router.get("/employees", response_model=EmployeesReport)
def employees(db: Session = Depends(get_db)) -> EmployeesReport:
    return reports.get_employees_report(db)


@router.get("/service", response_model=ServiceReport)
def service(
    month: str | None = Query(
        default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"
    ),
    db: Session = Depends(get_db),
) -> ServiceReport:
    if month:
        year_value, month_value = (int(part) for part in month.split("-"))
    else:
        today = date.today()
        year_value, month_value = today.year, today.month
    return reports.get_service_report(db, year_value, month_value)


@router.get("/service-export")
def export_service(
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    if date_from > date_to:
        raise HTTPException(status_code=400, detail="Дата начала позже даты окончания")
    buffer = build_service_export(db, date_from, date_to)
    filename = (
        f"cardridz-service-{date_from.isoformat()}_{date_to.isoformat()}.xlsx"
    )
    return StreamingResponse(
        buffer,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/usage", response_model=UsageReport)
def usage(
    month: str | None = Query(
        default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"
    ),
    db: Session = Depends(get_db),
) -> UsageReport:
    if month:
        year_value, month_value = (int(part) for part in month.split("-"))
    else:
        today = date.today()
        year_value, month_value = today.year, today.month
    return reports.get_usage_report(db, year_value, month_value)
