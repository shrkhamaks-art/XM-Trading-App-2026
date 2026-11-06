"""Database-backed fixed-window rate limiting (PostgreSQL and SQLite)."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from .models import RateLimitBucket


def enforce_rate_limit(db: Session, *, scope: str, identity: str,
                       limit: int, window_seconds: int) -> None:
    now = datetime.now(timezone.utc)
    window_id = int(now.timestamp()) // window_seconds
    key = f"{scope}:{identity[:180]}:{window_id}"
    table = RateLimitBucket.__table__
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = pg_insert(table).values(
            bucket_key=key, count=1, window_started_at=now
        ).on_conflict_do_update(
            index_elements=[table.c.bucket_key],
            set_={"count": table.c.count + 1},
        )
    elif dialect == "sqlite":
        statement = sqlite_insert(table).values(
            bucket_key=key, count=1, window_started_at=now
        ).on_conflict_do_update(
            index_elements=[table.c.bucket_key],
            set_={"count": table.c.count + 1},
        )
    else:
        raise RuntimeError(f"Rate limiter does not support database dialect: {dialect}")

    db.execute(statement)
    count = db.query(RateLimitBucket.count).filter_by(bucket_key=key).scalar()
    db.commit()
    if count is not None and count > limit:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.",
                            headers={"Retry-After": str(window_seconds)})
