from sqlalchemy import func, insert, select, update

from app.core.config import LIMITE_SALDO_DEPOSITO
from app.core.erros import Recusa
from app.db.transacao import executar_comando, preparar_escrita
from app.models import CarteiraRegistro, Lancamento
from app.schemas.carteira import Carteira, DepositoEntrada
from app.services import idempotencia
from app.services.auth import exigir_papel
from app.services.consultas import ler_carteira
from app.services.notificacoes import EventoDominio, publicar_depois_do_commit


async def depositar(recursos, licitante, valor, chave) -> Carteira:
    exigir_papel(licitante, "licitante")
    DepositoEntrada(valor_centavos=valor)

    async def comando():
        async with recursos.fabrica() as s, s.begin():
            await preparar_escrita(s)
            id_chave, repeticao = await idempotencia.iniciar(
                s, licitante.id, "deposito", chave, idempotencia.impressao("deposito", valor)
            )
            if repeticao:
                return repeticao
            saldo = await s.scalar(
                select(CarteiraRegistro.saldo_centavos)
                .where(CarteiraRegistro.usuario_id == licitante.id)
                .with_for_update()
            )
            if saldo + valor > LIMITE_SALDO_DEPOSITO:
                raise Recusa("limite_saldo")
            await s.execute(
                update(CarteiraRegistro)
                .where(CarteiraRegistro.usuario_id == licitante.id)
                .values(saldo_centavos=saldo + valor, atualizada_em=func.clock_timestamp())
            )
            await s.execute(
                insert(Lancamento).values(
                    usuario_id=licitante.id, tipo="deposito", valor_centavos=valor
                )
            )
            resposta = await idempotencia.concluir(s, id_chave, await ler_carteira(s, licitante.id))
        return resposta

    resposta = await executar_comando(comando)
    if not resposta.repetida:
        publicar_depois_do_commit(
            recursos.publicador,
            [EventoDominio("carteira_atualizada", usuarios_afetados=(licitante.id,))],
        )
    return idempotencia.materializar(resposta, Carteira)
