from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import anyio
import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.chaves import Chaves, carregar_chaves
from app.core.config import Settings
from app.db.session import Fabrica, criar_engine, criar_fabrica
from app.services.notificacoes import Publicador
from app.services.tempo_real import CentralTempoReal

if TYPE_CHECKING:
    from app.integrations.met import MetCliente


@dataclass
class Recursos:
    settings: Settings
    chaves: Chaves
    engine: AsyncEngine
    fabrica: Fabrica
    http: httpx.AsyncClient
    met: "MetCliente"
    publicador: Publicador
    central: CentralTempoReal
    lotes_bloqueados: set[int] = field(default_factory=set)
    contas_demo: list = field(default_factory=list)


@asynccontextmanager
async def abrir_recursos(
    settings: Settings, *, transporte_http=None, publicador=None, iniciar_worker=True
) -> AsyncIterator[Recursos]:
    chaves = carregar_chaves(settings)
    from app.integrations.met import MetCliente
    from app.services.itens import CacheMetBanco

    engine = criar_engine(settings)
    try:
        fabrica = criar_fabrica(engine)
        async with httpx.AsyncClient(
            transport=transporte_http,
            timeout=httpx.Timeout(5.0, connect=3.0),
            follow_redirects=False,
            headers={"User-Agent": "casa-de-leiloes/0.1 (teste tecnico)"},
        ) as http:
            central = CentralTempoReal(settings.ws_max_conexoes, settings.ws_tamanho_fila)
            recursos = Recursos(
                settings,
                chaves,
                engine,
                fabrica,
                http,
                MetCliente(http, CacheMetBanco(fabrica), settings.met_base_url),
                publicador if publicador is not None else central,
                central,
            )
            async with anyio.create_task_group() as grupo:
                if settings.seed_demo:
                    from app.demo.seed import garantir_demonstracao, laco_demonstracao

                    with anyio.move_on_after(60):
                        await garantir_demonstracao(recursos)
                    grupo.start_soon(laco_demonstracao, recursos)
                if iniciar_worker:
                    from app.services.encerramento import laco_encerramento

                    grupo.start_soon(laco_encerramento, recursos)
                try:
                    yield recursos
                finally:
                    central.encerrar_todas(1012)
                    grupo.cancel_scope.cancel()
    finally:
        await engine.dispose()
