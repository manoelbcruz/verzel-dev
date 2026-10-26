import random
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import anyio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.erros import Recusa
from app.db.session import Fabrica


async def preparar_escrita(session: AsyncSession) -> None:
    await session.execute(text("SET LOCAL lock_timeout = '3s'"))


@asynccontextmanager
async def leitura_consistente(fabrica: Fabrica) -> AsyncIterator[AsyncSession]:
    async with fabrica() as session, session.begin():
        await session.connection(
            execution_options={"isolation_level": "REPEATABLE READ", "postgresql_readonly": True}
        )
        yield session


async def executar_comando[T](fn: Callable[[], Awaitable[T]], tentativas: int = 3) -> T:
    for tentativa in range(tentativas):
        try:
            return await fn()
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) not in {"40P01", "55P03"}:
                raise
            if tentativa == tentativas - 1:
                raise Recusa("servico_ocupado") from exc
            await anyio.sleep(0.05 * 2**tentativa + random.uniform(0, 0.05))
    raise ValueError("tentativas deve ser positivo")
