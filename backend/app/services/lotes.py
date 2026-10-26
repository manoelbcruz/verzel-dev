import logging
from uuid import uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.erros import ErroIntegridade, Recusa
from app.db.transacao import executar_comando, preparar_escrita
from app.integrations.imagens import MidiaBaixada, baixar_imagem
from app.models import EventoLote, Lote, Midia
from app.schemas.comum import Centavos
from app.services.auth import exigir_papel
from app.services.cadeia import ZERO_MAC, assinar_cabeca, mac_evento, sanitizar
from app.services.consultas import carregar_dados, consulta_resumos, ler_detalhe, montar_resumo
from app.services.notificacoes import EventoDominio, publicar_depois_do_commit
from app.services.regras import validar_datas
from app.services.verificacao import conferir_ponta

logger = logging.getLogger(__name__)


async def anexar_evento(s, lote, campos, chaves, midia_sha256, *, liquidacao=None, fim_final=None):
    seq = lote["cabeca_seq"] + 1 if campos["tipo"] != "publicacao" else 1
    anterior = ZERO_MAC
    if seq > 1:
        anterior = await s.scalar(
            select(EventoLote.mac).where(
                EventoLote.lote_id == lote["id"], EventoLote.seq == seq - 1
            )
        )
    evento = dict(
        (
            await s.execute(
                insert(EventoLote.__table__)
                .values(
                    lote_id=lote["id"],
                    seq=seq,
                    mac=ZERO_MAC,
                    **campos,
                )
                .returning(EventoLote.__table__)
            )
        )
        .mappings()
        .one()
    )
    evento["mac"] = mac_evento(
        lote,
        evento,
        anterior,
        midia_sha256,
        liquidacao,
        chaves,
        fim_final if fim_final is not None else lote["fim_original_em"],
    )
    await s.execute(
        update(EventoLote).where(EventoLote.id == evento["id"]).values(mac=evento["mac"])
    )
    return evento


def nova_cabeca(lote, evento, chaves):
    return {
        "cabeca_seq": evento["seq"],
        "cabeca_assinatura": assinar_cabeca(
            chaves.integridade, lote["public_id"], evento["seq"], evento["mac"]
        ),
    }


async def publicar_lote(recursos, leiloeiro, item, midia, condicoes):
    exigir_papel(leiloeiro, "leiloeiro")
    from pydantic import TypeAdapter

    validador = TypeAdapter(Centavos)
    validador.validate_python(condicoes.lance_inicial_centavos)
    validador.validate_python(condicoes.incremento_centavos)

    async def comando():
        async with recursos.fabrica() as s, s.begin():
            await preparar_escrita(s)
            agora = await s.scalar(select(func.clock_timestamp()))
            validar_datas(condicoes, agora)
            inicio, fim = condicoes.inicio_em, condicoes.fim_em
            await s.execute(
                pg_insert(Midia)
                .values(
                    sha256=midia.sha256,
                    content_type=midia.content_type,
                    tamanho_bytes=len(midia.dados),
                    dados=midia.dados,
                    origem_url=item.imagem_url_externa,
                )
                .on_conflict_do_nothing(index_elements=[Midia.sha256])
            )
            midia_id = await s.scalar(select(Midia.id).where(Midia.sha256 == midia.sha256))
            lote = (
                (
                    await s.execute(
                        insert(Lote.__table__)
                        .values(
                            public_id=uuid4(),
                            leiloeiro_id=leiloeiro.id,
                            status="publicado",
                            item_fonte="met",
                            item_id_externo=item.id_externo,
                            titulo=sanitizar(item.titulo, 300),
                            atributos={
                                sanitizar(k): sanitizar(v) for k, v in item.atributos.items()
                            },
                            midia_id=midia_id,
                            lance_inicial_centavos=condicoes.lance_inicial_centavos,
                            incremento_centavos=condicoes.incremento_centavos,
                            inicio_em=inicio,
                            fim_original_em=fim,
                            fim_em=fim,
                            cabeca_seq=1,
                            cabeca_assinatura=ZERO_MAC,
                        )
                        .returning(Lote.__table__)
                    )
                )
                .mappings()
                .one()
            )
            evento = await anexar_evento(
                s, lote, {"tipo": "publicacao", "instante": agora}, recursos.chaves, midia.sha256
            )
            await s.execute(
                update(Lote)
                .where(Lote.id == lote["id"])
                .values(**nova_cabeca(lote, evento, recursos.chaves))
            )
        return lote["public_id"]

    public_id = await executar_comando(comando)
    publicar_depois_do_commit(recursos.publicador, [EventoDominio("lote_publicado", public_id, 1)])
    resposta, _, _ = await ler_detalhe(recursos, public_id, leiloeiro)
    return resposta


async def criar_lote_do_met(recursos, leiloeiro, entrada):
    exigir_papel(leiloeiro, "leiloeiro")
    async with recursos.fabrica() as s, s.begin():
        agora = await s.scalar(select(func.clock_timestamp()))
        validar_datas(entrada, agora)
    item = await recursos.met.obter_item(entrada.item_id_externo)
    async with recursos.fabrica() as s, s.begin():
        guardada = (
            (
                await s.execute(
                    select(Midia.__table__)
                    .where(Midia.origem_url == item.imagem_url_externa)
                    .order_by(Midia.id)
                    .limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
    if guardada:
        midia = MidiaBaixada(guardada["dados"], guardada["content_type"], guardada["sha256"])
    else:
        midia = await baixar_imagem(
            recursos.http, item.imagem_url_externa, recursos.settings.imagem_max_bytes
        )
    return await publicar_lote(recursos, leiloeiro, item, midia, entrada)


async def cancelar_lote(recursos, leiloeiro, public_id):
    exigir_papel(leiloeiro, "leiloeiro")

    async def comando():
        async with recursos.fabrica() as s, s.begin():
            await preparar_escrita(s)
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
            if lote["leiloeiro_id"] != leiloeiro.id:
                raise Recusa("lote_de_outro_leiloeiro")
            agora = await s.scalar(select(func.clock_timestamp()))
            if lote["status"] == "cancelado":
                raise Recusa("lote_cancelado")
            if lote["status"] == "encerrado" or lote["fim_em"] <= agora:
                raise Recusa("lote_encerrado")
            if lote["total_lances"]:
                raise Recusa("lote_com_lances")
            dados = await carregar_dados(s, lote)
            conferir_ponta(dados, recursos.chaves)
            evento = await anexar_evento(
                s,
                lote,
                {"tipo": "cancelamento", "instante": agora},
                recursos.chaves,
                dados.midia_sha256,
            )
            await s.execute(
                update(Lote)
                .where(Lote.id == lote["id"])
                .values(status="cancelado", **nova_cabeca(lote, evento, recursos.chaves))
            )
            atualizado = (
                (await s.execute(consulta_resumos().where(Lote.id == lote["id"]))).mappings().one()
            )
            resposta = montar_resumo(atualizado, agora)
        return resposta, evento["seq"]

    try:
        resposta, versao = await executar_comando(comando)
    except ErroIntegridade:
        logger.critical("Cancelamento recusado por integridade do lote %s", public_id)
        raise
    publicar_depois_do_commit(
        recursos.publicador, [EventoDominio("lote_cancelado", public_id, versao)]
    )
    return resposta
