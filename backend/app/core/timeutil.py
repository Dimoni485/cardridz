from datetime import date, datetime, time


def local_day_start(value: date) -> datetime:
    """Начало календарного дня в локальном часовом поясе сервера."""
    return datetime.combine(value, time.min).astimezone()


def local_month_range(year: int, month: int) -> tuple[datetime, datetime]:
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    start = datetime(year, month, 1).astimezone()
    end = datetime(next_year, next_month, 1).astimezone()
    return start, end
