import logging

import anyio
from sqlalchemy import BigInteger, all_, func, select
from sqlalchemy.dialects.postgresql import array

from app.core.erros import ErroIntegridade
from app.models import Lote
from app.services.liquidacao import encerrar_lote

logger = logging.getLogger(__name__)


async def encerrar_vencidos(recursos) -> int:
    async with recursos.fabrica() as s, s.begin():
        consulta = select(Lote.id).where(
            Lote.status == "publicado", Lote.fim_em <= func.clock_timestamp()
        )
        if recursos.lotes_bloqueados:
            consulta = consulta.where(
                Lote.id != all_(array(sorted(recursos.lotes_bloqueados), type_=BigInteger))
            )
        candidatos = (await s.scalars(consulta.order_by(Lote.fim_em).limit(50))).all()
    total = 0
    for lote_id in candidatos:
        try:
            total += await encerrar_lote(recursos, lote_id)
        except ErroIntegridade:
            # encerrar_lote registra uma única vez e retira o lote das próximas buscas.
            continue
        except Exception:
            logger.exception("Falha ao encerrar lote interno %s", lote_id)
    return total


async def laco_encerramento(recursos):
    while True:
        try:
            await encerrar_vencidos(recursos)
        except Exception:
            logger.exception("Falha na rodada de encerramento")
        await anyio.sleep(recursos.settings.encerramento_intervalo_s)
