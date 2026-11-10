"""Schema invariants: migrations match models (INV-13) and money is integer (INV-1)."""

from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, text

from app.models import Base


def test_models_match_migrations(migrated_db: Engine) -> None:
    with migrated_db.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_no_float_or_numeric_columns(migrated_db: Engine) -> None:
    with migrated_db.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name, column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND data_type IN ('real', 'double precision', 'numeric')"
            )
        ).all()
    assert rows == []


def test_child_rows_cascade_on_research_delete(migrated_db: Engine) -> None:
    with migrated_db.connect() as conn:
        rules = dict(
            conn.execute(
                text(
                    "SELECT tc.table_name || '.' || kcu.column_name, rc.delete_rule "
                    "FROM information_schema.referential_constraints rc "
                    "JOIN information_schema.table_constraints tc "
                    "  ON tc.constraint_name = rc.constraint_name "
                    "JOIN information_schema.key_column_usage kcu "
                    "  ON kcu.constraint_name = rc.constraint_name"
                )
            ).all()
        )
    assert rules == {
        "message.research_id": "CASCADE",
        "finding.research_id": "CASCADE",
        "run.research_id": "CASCADE",
        "finding.run_id": "SET NULL",
    }
