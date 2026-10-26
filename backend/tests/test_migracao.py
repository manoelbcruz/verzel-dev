import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, create_engine, text

from alembic import command
from app.db.base import Base

pytestmark = pytest.mark.pg


def test_migracao_reversivel_e_metadata(banco_teste):
    config = Config("alembic.ini")
    config.attributes.update(database_url=banco_teste, configurar_logging=False)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(banco_teste)
    try:
        with engine.connect() as conexao:
            assert compare_metadata(MigrationContext.configure(conexao), Base.metadata) == []
            nomes = set(
                conexao.scalars(text("SELECT conname FROM pg_constraint WHERE contype = 'c'"))
            )
            esperados = {
                c.name
                for t in Base.metadata.tables.values()
                for c in t.constraints
                if isinstance(c, CheckConstraint)
            }
            assert None not in esperados
            assert esperados <= nomes
    finally:
        engine.dispose()
