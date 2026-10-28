import logging

from sqlalchemy import func, select

from app.core.erros import Recusa
from app.db.transacao import leitura_consistente
from app.models import CarteiraRegistro, EventoLote, Lancamento, Liquidacao, Lote, Midia, Reserva
from app.schemas.carteira import Carteira
from app.schemas.comprovantes import Comprovante
from app.schemas.lotes import (
    LoteDetalhe,
    LotePainel,
    LoteResumo,
    PainelLeiloeiro,
    Participacao,
    Vitrine,
)
from app.services.cadeia import pseudonimo
from app.services.regras import calcular_fase
from app.services.verificacao import DadosAuditoria

logger = logging.getLogger(__name__)


async def carregar_dados(s, lote) -> DadosAuditoria:
    midia = (
        await s.execute(
            select(
                Midia.sha256,
                func.encode(func.sha256(Midia.dados), "hex").label("sha256_calculado"),
            ).where(Midia.id == lote["midia_id"])
        )
    ).one()
    eventos = (
        (
            await s.execute(
                select(EventoLote.__table__)
                .where(EventoLote.lote_id == lote["id"])
                .order_by(EventoLote.seq)
            )
        )
        .mappings()
        .all()
    )
    reserva = (
        (await s.execute(select(Reserva.__table__).where(Reserva.lote_id == lote["id"])))
        .mappings()
        .one_or_none()
    )
    liquidacao = (
        (await s.execute(select(Liquidacao.__table__).where(Liquidacao.lote_id == lote["id"])))
        .mappings()
        .one_or_none()
    )
    lancamentos = []
    if liquidacao is not None:
        lancamentos = (
            (
                await s.execute(
                    select(Lancamento.__table__).where(Lancamento.liquidacao_id == liquidacao["id"])
                )
            )
            .mappings()
            .all()
        )
    return DadosAuditoria(
        dict(lote),
        midia.sha256,
        midia.sha256_calculado,
        list(eventos),
        reserva,
        liquidacao,
        list(lancamentos),
    )


def consulta_resumos():
    encerrado_em = (
        select(func.max(EventoLote.instante))
        .where(EventoLote.lote_id == Lote.id, EventoLote.tipo == "encerramento")
        .correlate(Lote)
        .scalar_subquery()
    )
    return (
        select(
            Lote.__table__,
            Midia.sha256.label("midia_sha256"),
            Liquidacao.resultado.label("resultado_situacao"),
            Liquidacao.valor_centavos.label("resultado_valor"),
            Liquidacao.vencedor_id.label("resultado_vencedor_id"),
            Liquidacao.vencedor_pseudonimo.label("resultado_pseudonimo"),
            Liquidacao.comprovante_codigo,
            encerrado_em.label("encerrado_em"),
        )
        .join(Midia, Lote.midia_id == Midia.id)
        .outerjoin(Liquidacao, Liquidacao.lote_id == Lote.id)
    )


def cancelavel(lote, agora, usuario):
    return bool(
        usuario
        and usuario.id == lote["leiloeiro_id"]
        and lote["status"] == "publicado"
        and lote["fim_em"] > agora
        and lote["total_lances"] == 0
    )


def montar_resumo(lote, agora, usuario=None, *, detalhe=False):
    resultado = None
    if lote["resultado_situacao"] is not None and lote["encerrado_em"] is not None:
        codigo = None
        if (
            detalhe
            and usuario
            and usuario.id in {lote["resultado_vencedor_id"], lote["leiloeiro_id"]}
        ):
            codigo = lote["comprovante_codigo"]
        resultado = {
            "situacao": lote["resultado_situacao"],
            "valor_centavos": lote["resultado_valor"],
            "vencedor_pseudonimo": lote["resultado_pseudonimo"],
            "encerrado_em": lote["encerrado_em"],
            "comprovante_codigo": codigo,
        }
    return LoteResumo(
        id=lote["public_id"],
        titulo=lote["titulo"],
        imagem_url=f"/api/midias/{lote['midia_sha256']}",
        fase=calcular_fase(lote["status"], lote["inicio_em"], lote["fim_em"], agora),
        inicio_em=lote["inicio_em"],
        fim_em=lote["fim_em"],
        lance_inicial_centavos=lote["lance_inicial_centavos"],
        lance_atual_centavos=lote["lance_atual_centavos"],
        total_lances=lote["total_lances"],
        resultado=resultado,
    )


async def ler_detalhe(recursos, public_id, usuario=None):
    async with leitura_consistente(recursos.fabrica) as s:
        agora = await s.scalar(select(func.clock_timestamp()))
        lote = (
            (await s.execute(consulta_resumos().where(Lote.public_id == public_id)))
            .mappings()
            .one_or_none()
        )
        if lote is None:
            raise Recusa("lote_nao_encontrado")
        eventos = (
            (
                await s.execute(
                    select(EventoLote.__table__)
                    .where(EventoLote.lote_id == lote["id"], EventoLote.tipo == "lance")
                    .order_by(EventoLote.seq)
                )
            )
            .mappings()
            .all()
        )
        maiores = {}
        for evento in eventos:
            uid = evento["licitante_id"]
            maiores[uid] = max(maiores.get(uid, 0), evento["valor_centavos"])
        participacao = None
        if usuario and usuario.papel == "licitante" and usuario.id in maiores:
            ordem = sorted(maiores, key=lambda uid: maiores[uid], reverse=True)
            participacao = {
                "meu_pseudonimo": pseudonimo(recursos.chaves.privacidade, public_id, usuario.id),
                "ganhando": lote["lider_id"] == usuario.id,
                "meu_maior_lance_centavos": maiores[usuario.id],
                "posicao": ordem.index(usuario.id) + 1,
                "total_participantes": len(maiores),
            }
        resposta = LoteDetalhe(
            **montar_resumo(lote, agora, usuario, detalhe=True).model_dump(),
            atributos=lote["atributos"],
            incremento_centavos=lote["incremento_centavos"],
            fim_original_em=lote["fim_original_em"],
            proximo_lance_minimo_centavos=(
                lote["lance_inicial_centavos"]
                if lote["lider_id"] is None
                else lote["lance_atual_centavos"] + lote["incremento_centavos"]
            ),
            lider_pseudonimo=pseudonimo(recursos.chaves.privacidade, public_id, lote["lider_id"])
            if lote["lider_id"] is not None
            else None,
            versao=lote["cabeca_seq"],
            servidor_agora=agora,
            lances=[
                {
                    "seq": e["seq"],
                    "pseudonimo": e["pseudonimo"],
                    "valor_centavos": e["valor_centavos"],
                    "instante": e["instante"],
                    "prorrogou": e["fim_novo"] > e["fim_anterior"],
                }
                for e in eventos
            ],
            minha_participacao=participacao,
            cancelavel=cancelavel(lote, agora, usuario),
        )
        return resposta, lote, agora


async def detalhar_lote(recursos, public_id, usuario=None):
    resposta, lote, agora = await ler_detalhe(recursos, public_id, usuario)
    if lote["status"] == "publicado" and lote["fim_em"] <= agora:
        from app.services.liquidacao import encerrar_lote

        try:
            await encerrar_lote(recursos, lote["id"], esperar=True)
            resposta, _, _ = await ler_detalhe(recursos, public_id, usuario)
        except Exception:
            logger.exception("Falha no encerramento preguiçoso do lote %s", public_id)
    return resposta


async def vitrine(recursos, q=None):
    async with leitura_consistente(recursos.fabrica) as s:
        agora = await s.scalar(select(func.clock_timestamp()))
        consulta = consulta_resumos().where(Lote.status != "cancelado")
        if q:
            termo = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            consulta = consulta.where(Lote.titulo.ilike(f"%{termo}%", escape="\\"))
        listas = {}
        for nome, filtro, ordem in [
            (
                "ao_vivo",
                (Lote.status == "publicado") & (Lote.inicio_em <= agora) & (Lote.fim_em > agora),
                Lote.fim_em,
            ),
            ("agendados", (Lote.status == "publicado") & (Lote.inicio_em > agora), Lote.inicio_em),
            (
                "encerrados",
                (Lote.status == "encerrado") | (Lote.fim_em <= agora),
                Lote.fim_em.desc(),
            ),
        ]:
            lotes = (await s.execute(consulta.where(filtro).order_by(ordem).limit(50))).mappings()
            listas[nome] = [montar_resumo(lote, agora) for lote in lotes]
        return Vitrine(servidor_agora=agora, **listas)


async def painel(recursos, usuario):
    async with leitura_consistente(recursos.fabrica) as s:
        agora = await s.scalar(select(func.clock_timestamp()))
        lotes = (
            (
                await s.execute(
                    consulta_resumos()
                    .where(Lote.leiloeiro_id == usuario.id)
                    .order_by(Lote.id.desc())
                )
            )
            .mappings()
            .all()
        )
        total = await s.scalar(
            select(func.coalesce(func.sum(Lancamento.valor_centavos), 0)).where(
                Lancamento.usuario_id == usuario.id, Lancamento.tipo == "arremate_credito"
            )
        )
        return PainelLeiloeiro(
            total_recebido_centavos=int(total),
            lotes=[
                LotePainel(
                    **montar_resumo(lote, agora, usuario, detalhe=True).model_dump(),
                    cancelavel=cancelavel(lote, agora, usuario),
                )
                for lote in lotes
            ],
        )


async def ler_carteira(s, usuario_id):
    saldo = await s.scalar(
        select(CarteiraRegistro.saldo_centavos).where(CarteiraRegistro.usuario_id == usuario_id)
    )
    reservas = (
        (
            await s.execute(
                select(Lote.public_id.label("lote_id"), Lote.titulo, Reserva.valor_centavos)
                .join(Reserva, Reserva.lote_id == Lote.id)
                .where(Reserva.usuario_id == usuario_id)
                .order_by(Lote.id)
            )
        )
        .mappings()
        .all()
    )
    lancamentos = (
        (
            await s.execute(
                select(
                    Lancamento.tipo,
                    Lancamento.valor_centavos,
                    Lancamento.criado_em,
                    Lote.public_id.label("lote_id"),
                )
                .outerjoin(Liquidacao, Lancamento.liquidacao_id == Liquidacao.id)
                .outerjoin(Lote, Liquidacao.lote_id == Lote.id)
                .where(Lancamento.usuario_id == usuario_id)
                .order_by(Lancamento.id.desc())
                .limit(20)
            )
        )
        .mappings()
        .all()
    )
    comprometido = sum(r["valor_centavos"] for r in reservas)
    return Carteira(
        saldo_total_centavos=saldo,
        comprometido_centavos=comprometido,
        disponivel_centavos=saldo - comprometido,
        reservas=reservas,
        lancamentos=lancamentos,
    )


async def consultar_carteira(recursos, usuario):
    async with leitura_consistente(recursos.fabrica) as s:
        return await ler_carteira(s, usuario.id)


async def participacoes(recursos, usuario):
    async with leitura_consistente(recursos.fabrica) as s:
        agora = await s.scalar(select(func.clock_timestamp()))
        maiores = (
            select(EventoLote.lote_id, func.max(EventoLote.valor_centavos).label("maior"))
            .where(EventoLote.licitante_id == usuario.id, EventoLote.tipo == "lance")
            .group_by(EventoLote.lote_id)
            .subquery()
        )
        linhas = (
            (
                await s.execute(
                    consulta_resumos()
                    .add_columns(maiores.c.maior)
                    .join(maiores, maiores.c.lote_id == Lote.id)
                    .order_by(Lote.id.desc())
                )
            )
            .mappings()
            .all()
        )
        resultado = []
        for lote in linhas:
            ganhou = lote["resultado_vencedor_id"] == usuario.id
            if lote["status"] == "encerrado":
                situacao = "arrematado" if ganhou else "nao_arrematado"
            elif lote["fim_em"] <= agora:
                situacao = "aguardando_resultado"
            else:
                situacao = "ganhando" if lote["lider_id"] == usuario.id else "superado"
            resultado.append(
                Participacao(
                    lote=montar_resumo(lote, agora),
                    meu_maior_lance_centavos=lote["maior"],
                    meu_pseudonimo=pseudonimo(
                        recursos.chaves.privacidade, lote["public_id"], usuario.id
                    ),
                    situacao=situacao,
                    comprovante_codigo=lote["comprovante_codigo"] if ganhou else None,
                )
            )
        return resultado


async def comprovante(recursos, codigo):
    async with leitura_consistente(recursos.fabrica) as s:
        lote = (
            (
                await s.execute(
                    consulta_resumos().where(
                        Liquidacao.comprovante_codigo == codigo,
                        Liquidacao.resultado == "arrematado",
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if lote is None:
            raise Recusa("comprovante_nao_encontrado")
        evento = (
            await s.execute(
                select(EventoLote.seq, EventoLote.mac, EventoLote.instante).where(
                    EventoLote.lote_id == lote["id"], EventoLote.tipo == "encerramento"
                )
            )
        ).one_or_none()
        if evento is None:
            raise Recusa("comprovante_nao_encontrado")
        return Comprovante(
            codigo=codigo,
            lote_id=lote["public_id"],
            titulo=lote["titulo"],
            atributos=lote["atributos"],
            imagem_url=f"/api/midias/{lote['midia_sha256']}",
            valor_centavos=lote["resultado_valor"],
            vencedor_pseudonimo=lote["resultado_pseudonimo"],
            encerrado_em=evento.instante,
            evento_encerramento={"seq": evento.seq, "mac": evento.mac.hex()},
            auditoria_url=f"/api/lotes/{lote['public_id']}/auditoria",
        )
