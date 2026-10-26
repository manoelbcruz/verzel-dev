from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.integrations.met import RegistroCache
from app.models import CacheMetRegistro


class CacheMetBanco:
    def __init__(self, fabrica):
        self.fabrica = fabrica

    async def obter(self, chave):
        async with self.fabrica() as s, s.begin():
            linha = (
                (
                    await s.execute(
                        select(CacheMetRegistro.__table__).where(CacheMetRegistro.chave == chave)
                    )
                )
                .mappings()
                .one_or_none()
            )
            return RegistroCache(linha["dados"], linha["obtido_em"]) if linha else None

    async def guardar(self, chave, dados):
        async with self.fabrica() as s, s.begin():
            registro = {"chave": chave, "dados": dados, "obtido_em": datetime.now(UTC)}
            await s.execute(
                insert(CacheMetRegistro)
                .values(**registro)
                .on_conflict_do_update(
                    index_elements=[CacheMetRegistro.chave],
                    set_={"dados": registro["dados"], "obtido_em": registro["obtido_em"]},
                )
            )
