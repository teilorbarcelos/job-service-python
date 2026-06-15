import os
from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.shared.config.settings import settings

_engine_instance = None
_async_session_factory = None
_test_session = None


def _create_engine():
    global _engine_instance, _async_session_factory

    engine_kwargs = {
        "echo": settings.environment == "local",
        "future": True,
    }

    if "sqlite" not in settings.database_url.lower():
        engine_kwargs.update(
            {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_recycle": settings.db_pool_recycle,
                "pool_pre_ping": settings.db_pool_pre_ping,
            }
        )

    _engine_instance = create_async_engine(settings.database_url, **engine_kwargs)

    from src.infra.metrics.metric_service import metric_service

    @event.listens_for(_engine_instance.sync_engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, execmany):
        metric_service.increment_counter("db_queries_total")

    _async_session_factory = async_sessionmaker(
        bind=_engine_instance,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def get_engine():
    global _engine_instance
    if _engine_instance is None:
        _create_engine()
    return _engine_instance


def get_async_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        _create_engine()
    return _async_session_factory


async def close_engine():
    global _engine_instance, _async_session_factory
    if _engine_instance is not None:
        await _engine_instance.dispose()
        _engine_instance = None
        _async_session_factory = None


def set_test_session(session):
    global _test_session
    _test_session = session


@asynccontextmanager
async def SessionLocal():
    if _test_session:
        yield _test_session
    else:
        factory = get_async_session_factory()
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except:
                await session.rollback()
                raise
            finally:
                await session.close()


get_session = SessionLocal

IS_TEST = "PYTEST_CURRENT_TEST" in os.environ
