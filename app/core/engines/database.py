from contextlib import asynccontextmanager

from sqlalchemy import ChunkedIteratorResult, Delete, Result, Select, Update, func, select
from sqlalchemy.dialects.postgresql import Insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.core.models.base import Base


class Transaction:
    def __init__(self, engine: AsyncEngine | None = None):
        self.engine = (
            engine
            if engine is not None
            else create_async_engine(
                url=settings.database_url,
                echo=False,
                echo_pool=False,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
            )
        )
        self.async_session = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        self._session: AsyncSession | None = None

    @asynccontextmanager
    async def atomic(self):
        if self._session is None:
            try:
                async with self.async_session() as session:
                    self._session = session
                    async with session.begin():
                        yield
            finally:
                self._session = None
        else:
            async with self._session.begin_nested():
                yield

    async def execute(self, stmt: Insert | Update | Delete | Select) -> ChunkedIteratorResult:
        if self._session is None:
            async with self.atomic():
                result: ChunkedIteratorResult = await self._session.execute(stmt)
        else:
            result: ChunkedIteratorResult = await self._session.execute(stmt)
        return result

    async def is_exists(self, stmt: Insert | Update | Delete | Select) -> bool:
        result = await self.execute(stmt)
        result = result.one_or_none()  # noqa
        return True if result else False

    async def select_one(self, stmt: Select, scalars: bool = False) -> Base | None:
        """Выполняет и возвращает результат выражения."""
        if self._session is None:
            async with self.atomic():
                result: Result = await self._session.execute(stmt)
        else:
            result: Result = await self._session.execute(stmt)
        if scalars:
            return result.scalars().one_or_none()
        else:
            return result.one_or_none()

    async def scalars(self, stmt: Select):
        """Возвращает список сущностей по выборке (пустой список, если ничего не нашлось)."""
        if self._session is None:
            async with self.atomic():
                result: ChunkedIteratorResult = await self._session.execute(stmt)
        else:
            result: ChunkedIteratorResult = await self._session.execute(stmt)
        return result.scalars().all()

    async def count(self, stmt: Select):
        data_to_count = stmt.cte('data_to_count')
        count_query = select(func.count()).select_from(data_to_count)
        result = await self.execute(count_query)
        result: list = [u._asdict() for u in result.all()]  # noqa
        return result[0].get('count') if result else 0

    async def execute_all(
        self, stmt_list: [Insert | Update | Delete | Select]
    ) -> [ChunkedIteratorResult]:
        async with self.atomic():
            return [await self.execute(stmt) for stmt in stmt_list]
