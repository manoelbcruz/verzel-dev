import os
import secrets

import pytest

from app.core.chaves import Chaves
from app.core.config import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def chaves():
    return Chaves(secrets.token_bytes(32), secrets.token_bytes(32))


@pytest.fixture
def settings_teste(chaves):
    return Settings(
        _env_file=None,
        chave_integridade=chaves.integridade.hex(),
        chave_privacidade=chaves.privacidade.hex(),
        cors_origins=["http://test"],
        db_pool_size=12,
        db_max_overflow=12,
    )


def pytest_collection_modifyitems(items):
    if not os.environ.get("TEST_DATABASE_URL"):
        for item in items:
            if item.get_closest_marker("pg"):
                item.add_marker(pytest.mark.skip(reason="defina TEST_DATABASE_URL"))


@pytest.fixture(scope="session")
def banco_teste():
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from alembic import command

    valor = os.environ.get("TEST_DATABASE_URL")
    if not valor:
        pytest.skip("defina TEST_DATABASE_URL")
    url = make_url(Settings(_env_file=None, database_url=valor).database_url)
    if not url.database or not url.database.endswith("_test"):
        pytest.exit("TEST_DATABASE_URL deve apontar para banco com sufixo _test", returncode=1)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conexao:
            existe = conexao.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :nome"), {"nome": url.database}
            )
            if not existe:
                nome = admin.dialect.identifier_preparer.quote(url.database)
                conexao.exec_driver_sql(f"CREATE DATABASE {nome}")
    except Exception:
        pytest.exit(
            "TEST_DATABASE_URL presente, mas PostgreSQL indisponível ou sem acesso", returncode=1
        )
    finally:
        admin.dispose()
    config = Config("alembic.ini")
    config.attributes["database_url"] = url
    config.attributes["configurar_logging"] = False
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return url


@pytest.fixture(autouse=True)
def limpar_banco(request):
    if request.node.get_closest_marker("pg"):
        from sqlalchemy import create_engine

        from app import models  # noqa: F401
        from app.db.base import Base

        url = request.getfixturevalue("banco_teste")
        engine = create_engine(url)
        try:
            with engine.begin() as conexao:
                tabelas = ", ".join(
                    engine.dialect.identifier_preparer.quote(t.name)
                    for t in Base.metadata.sorted_tables
                )
                conexao.exec_driver_sql(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE")
        finally:
            engine.dispose()


@pytest.fixture
async def recursos(settings_teste, banco_teste):
    import httpx

    from app.recursos import abrir_recursos
    from app.services.notificacoes import PublicadorMemoria
    from tests.apoio import met_simulado

    settings_teste.database_url = banco_teste.render_as_string(hide_password=False)
    async with abrir_recursos(
        settings_teste,
        transporte_http=httpx.MockTransport(met_simulado),
        publicador=PublicadorMemoria(),
        iniciar_worker=False,
    ) as abertos:
        yield abertos


@pytest.fixture
async def cliente(recursos):
    import httpx

    from app.main import create_app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(recursos=recursos)),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as cliente:
        yield cliente
