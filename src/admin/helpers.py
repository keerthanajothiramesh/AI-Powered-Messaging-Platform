"""Date/datetime parsing helpers for admin seed operations."""
from datetime import date, datetime
from typing import Optional


def parse_dt(val) -> Optional[datetime]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))


def parse_date(val) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date):
        return val
    return datetime.fromisoformat(str(val)[:10]).date()
