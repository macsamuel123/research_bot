"""Create the test database if it is missing. Usage: python -m app.testdb <database-url>."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def ensure_database(url: str) -> None:
    target = make_url(url)
    name = target.database
    if not name:
        raise ValueError("database URL has no database name")
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
            ).scalar()
            if not exists:
                quoted = conn.dialect.identifier_preparer.quote(name)
                conn.execute(text(f"CREATE DATABASE {quoted}"))
    finally:
        admin.dispose()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m app.testdb <database-url>", file=sys.stderr)
        return 2
    ensure_database(argv[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
