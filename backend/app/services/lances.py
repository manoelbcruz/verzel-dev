import logging

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.erros import ErroIntegridade, Recusa
from app.db.transacao import executar_comando, preparar_escrita
from app.models import CarteiraRegistro, Lote, Reserva
from app.schemas.lotes import LanceAceito, LanceEntrada
from app.services import idempotencia
from app.services.auth import exigir_papel
from app.services.cadeia import pseudonimo
from app.services.consultas import carregar_dados
from app.services.lotes import anexar_evento, nova_cabeca
from app.services.notificacoes import EventoDominio, publicar_depois_do_commit
from app.services.regras import avaliar_lance
from app.services.verificacao import conferir_ponta

logger = logging.getLogger(__name__)


async def dar_lance(recursos, licitante, public_id, valor, chave) -> LanceAceito:
    exigir_papel(licitante, "licitante")
    LanceEntrada(valor_centavos=valor)

    async def comando():
        async with recursos.fabrica() as s, s.begin():
            await preparar_escrita(s)
            id_chave, repeticao = await idempotencia.iniciar(
                s, licitante.id, "lance", chave, idempotencia.impressao("lance", valor, public_id)
            )
            if repeticao:
                return repeticao, []
            lote = (
                (
                    await s.execute(
                        select(Lote.__table__).where(Lote.public_id == public_id).with_for_update()
                    )
                )
                .mappings()
                .one_or_none()
            )
            if lote is None:
                raise Recusa("lote_nao_encontrado")
            usuarios = sorted(
                {licitante.id} | ({lote["lider_id"]} if lote["lider_id"] is not None else set())
            )
            carteiras = {}
            for usuario_id in usuarios:
                carteiras[usuario_id] = await s.scalar(
                    select(CarteiraRegistro.saldo_centavos)
                    .where(CarteiraRegistro.usuario_id == usuario_id)
                    .with_for_update()
                )
            agora = await s.scalar(select(func.clock_timestamp()))
            comprometido = int(
                await s.scalar(
                    select(func.coalesce(func.sum(Reserva.valor_centavos), 0)).where(
                        Reserva.usuario_id == licitante.id
                    )
                )
            )
            dados = await carregar_dados(s, lote)
            conferir_ponta(dados, recursos.chaves)
            decisao = avaliar_lance(
                lote, licitante.id, valor, carteiras[licitante.id], comprometido, agora
            )
            apelido = pseudonimo(recursos.chaves.privacidade, public_id, licitante.id)
            evento = await anexar_evento(
                s,
                lote,
                {
                    "tipo": "lance",
                    "instante": agora,
                    "licitante_id": licitante.id,
                    "pseudonimo": apelido,
                    "valor_centavos": valor,
                    "fim_anterior": lote["fim_em"],
                    "fim_novo": decisao.fim_novo,
                },
                recursos.chaves,
                dados.midia_sha256,
            )
            reserva = {"usuario_id": licitante.id, "valor_centavos": valor, "atualizada_em": agora}
            await s.execute(
                insert(Reserva)
                .values(lote_id=lote["id"], **reserva)
                .on_conflict_do_update(index_elements=[Reserva.lote_id], set_=reserva)
            )
            await s.execute(
                update(Lote)
                .where(Lote.id == lote["id"])
                .values(
                    lance_atual_centavos=valor,
                    lider_id=licitante.id,
                    total_lances=lote["total_lances"] + 1,
                    fim_em=decisao.fim_novo,
                    **nova_cabeca(lote, evento, recursos.chaves),
                )
            )
            lance = LanceAceito(
                lote_id=public_id,
                seq=evento["seq"],
                valor_centavos=evento["valor_centavos"],
                instante=evento["instante"],
                fim_em=evento["fim_novo"],
                prorrogou=decisao.prorrogou,
                lider_pseudonimo=apelido,
                proximo_lance_minimo_centavos=valor + lote["incremento_centavos"],
            )
            resposta = await idempotencia.concluir(s, id_chave, lance)
            eventos = [
                EventoDominio(
                    "lote_atualizado",
                    public_id,
                    evento["seq"],
                    {
                        **lance.model_dump(mode="json"),
                        "total_lances": lote["total_lances"] + 1,
                        "versao": evento["seq"],
                        "lance_atual_centavos": valor,
                    },
                ),
                EventoDominio("carteira_atualizada", usuarios_afetados=tuple(usuarios)),
            ]
        return resposta, eventos

    try:
        resposta, eventos = await executar_comando(comando)
    except ErroIntegridade:
        logger.critical("Lance recusado por integridade do lote %s", public_id)
        raise
    publicar_depois_do_commit(recursos.publicador, eventos)
    return idempotencia.materializar(resposta, LanceAceito)
