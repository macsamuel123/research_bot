"""Database engine and session dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def get_engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


def get_session(request: Request) -> Iterator[Session]:
    factory = sessionmaker(bind=get_engine(request), expire_on_commit=False)
    with factory() as session:
        yield session
