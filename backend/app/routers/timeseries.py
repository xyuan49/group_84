"""Shared date filtering for time-series endpoints."""

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import Select, func
from sqlalchemy.orm import Session


def time_window(db: Session, stmt: Select, column, start: datetime | None, end: datetime | None,
                days: int | None) -> Select:
    """Filter `stmt` to start <= column <= end, or to the last `days` days.

    `days` counts back from `end` if given, otherwise from the latest value the
    query would return. The loaded data ends on 2026-11-01, so counting back
    from today would miss it.
    """
    if days is not None and start is not None:
        raise HTTPException(status_code=422, detail="Use either start or days, not both")
    start = start.replace(tzinfo=None) if start else None
    end = end.replace(tzinfo=None) if end else None

    if end is not None:
        stmt = stmt.where(column <= end)
    if days is not None:
        # Same filters as the endpoint's query, so the window ends at the latest row it would return.
        anchor = end or db.scalar(stmt.with_only_columns(func.max(column)).order_by(None))
        if anchor is None:
            return stmt  # no rows anyway
        start = anchor - timedelta(days=days)
    if start is not None:
        stmt = stmt.where(column >= start)
    return stmt
