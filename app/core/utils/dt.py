from datetime import date, datetime, timedelta

from app.core.enums import EDateTimeFormat
from app.core.exceptions import ValidationException


def dt_to_str(value, dt_format: str = EDateTimeFormat.DEFAULT_DATETIME_FMT.value) -> str:
    if isinstance(value, datetime | date):
        return value.strftime(dt_format)
    else:
        raise ValidationException(
            detail='Значение должно быть корректной датой или датой-временем'
        )


def dt_to_str_report_format(value: datetime) -> str:
    return value.strftime(EDateTimeFormat.DEFAULT_REPORT_DATETIME_FMT.value) if value else ''


def get_past_date_str(days: int, dt_format: str = EDateTimeFormat.DEFAULT_DATETIME_FMT.value):
    dt = datetime.now() - timedelta(days=days)
    return dt_to_str(value=dt, dt_format=dt_format)
