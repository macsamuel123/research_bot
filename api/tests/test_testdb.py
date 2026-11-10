from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.testdb import ensure_database


@pytest.mark.criterion("M1-C8")
def test_ensure_database_is_idempotent(test_db_url: str) -> None:
    name = "research_testdb_probe"
    url = make_url(test_db_url).set(database=name).render_as_string(hide_password=False)
    admin = create_engine(
        make_url(test_db_url).set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        ensure_database(url)
        ensure_database(url)
        with admin.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}
                ).scalar()
                == 1
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        admin.dispose()
