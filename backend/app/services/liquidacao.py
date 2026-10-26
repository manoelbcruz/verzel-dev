import logging
import secrets

from sqlalchemy import delete, func, insert, select, update

from app.core.erros import ErroCarteiraDivergente, ErroIntegridade
from app.db.transacao import executar_comando, preparar_escrita
from app.models import CarteiraRegistro, Lancamento, Liquidacao, Lote, Reserva
from app.services.cadeia import pseudonimo
from app.services.consultas import carregar_dados
from app.services.lotes import anexar_evento, nova_cabeca
from app.services.notificacoes import EventoDominio, publicar_depois_do_commit
from app.services.verificacao import conferir_ponta

logger = logging.getLogger(__name__)


def gerar_codigo_comprovante():
    return secrets.token_urlsafe(16)


async def encerrar_lote(recursos, lote_id, *, esperar=False) -> bool:
    if lote_id in recursos.lotes_bloqueados:
        return False

    async def comando():
        async with recursos.fabrica() as s, s.begin():
            await preparar_escrita(s)
            lote = (
                (
                    await s.execute(
                        select(Lote.__table__)
                        .where(
                            Lote.id == lote_id,
                            Lote.status == "publicado",
                            Lote.fim_em <= func.clock_timestamp(),
                        )
                        .with_for_update(skip_locked=not esperar)
                    )
                )
                .mappings()
                .one_or_none()
            )
            if lote is None:
                return False, []
            lider = lote["lider_id"]
            usuarios = sorted({lider, lote["leiloeiro_id"]}) if lider is not None else []
            carteiras = {}
            for usuario_id in usuarios:
                carteiras[usuario_id] = await s.scalar(
                    select(CarteiraRegistro.saldo_centavos)
                    .where(CarteiraRegistro.usuario_id == usuario_id)
                    .with_for_update()
                )
            agora = await s.scalar(select(func.clock_timestamp()))
            dados = await carregar_dados(s, lote)
            conferir_ponta(dados, recursos.chaves)
            for usuario_id in usuarios:
                razao = int(
                    await s.scalar(
                        select(func.coalesce(func.sum(Lancamento.valor_centavos), 0)).where(
                            Lancamento.usuario_id == usuario_id
                        )
                    )
                )
                if carteiras[usuario_id] != razao:
                    raise ErroCarteiraDivergente(lote["public_id"], usuario_id)
            liquidacao = {
                "lote_id": lote_id,
                "resultado": "sem_lances",
                "vencedor_id": None,
                "vencedor_pseudonimo": None,
                "valor_centavos": None,
                "comprovante_codigo": None,
            }
            if lider is not None:
                valor = lote["lance_atual_centavos"]
                await s.execute(
                    update(CarteiraRegistro)
                    .where(CarteiraRegistro.usuario_id == lider)
                    .values(saldo_centavos=carteiras[lider] - valor, atualizada_em=agora)
                )
                await s.execute(
                    update(CarteiraRegistro)
                    .where(CarteiraRegistro.usuario_id == lote["leiloeiro_id"])
                    .values(
                        saldo_centavos=carteiras[lote["leiloeiro_id"]] + valor, atualizada_em=agora
                    )
                )
                await s.execute(delete(Reserva).where(Reserva.lote_id == lote_id))
                codigo = gerar_codigo_comprovante()
                liquidacao.update(
                    resultado="arrematado",
                    vencedor_id=lider,
                    valor_centavos=valor,
                    vencedor_pseudonimo=pseudonimo(
                        recursos.chaves.privacidade, lote["public_id"], lider
                    ),
                    comprovante_codigo=codigo,
                )
            liquidacao = (
                (
                    await s.execute(
                        insert(Liquidacao.__table__)
                        .values(**liquidacao)
                        .returning(Liquidacao.__table__)
                    )
                )
                .mappings()
                .one()
            )
            if lider is not None:
                await s.execute(
                    insert(Lancamento),
                    [
                        {
                            "usuario_id": lider,
                            "tipo": "arremate_debito",
                            "valor_centavos": -valor,
                            "liquidacao_id": liquidacao["id"],
                        },
                        {
                            "usuario_id": lote["leiloeiro_id"],
                            "tipo": "arremate_credito",
                            "valor_centavos": valor,
                            "liquidacao_id": liquidacao["id"],
                        },
                    ],
                )
            fim_final = (
                dados.eventos[-1]["fim_novo"] if lider is not None else lote["fim_original_em"]
            )
            evento = await anexar_evento(
                s,
                lote,
                {"tipo": "encerramento", "instante": agora},
                recursos.chaves,
                dados.midia_sha256,
                liquidacao=liquidacao,
                fim_final=fim_final,
            )
            await s.execute(
                update(Lote)
                .where(Lote.id == lote_id)
                .values(status="encerrado", **nova_cabeca(lote, evento, recursos.chaves))
            )
            eventos = [
                EventoDominio(
                    "lote_encerrado",
                    lote["public_id"],
                    evento["seq"],
                    {
                        "situacao": liquidacao["resultado"],
                        "valor_centavos": liquidacao["valor_centavos"],
                        "vencedor_pseudonimo": liquidacao["vencedor_pseudonimo"],
                    },
                )
            ]
            if usuarios:
                eventos.append(
                    EventoDominio("carteira_atualizada", usuarios_afetados=tuple(usuarios))
                )
        return True, eventos

    try:
        encerrou, eventos = await executar_comando(comando)
    except ErroIntegridade as exc:
        if lote_id not in recursos.lotes_bloqueados:
            recursos.lotes_bloqueados.add(lote_id)
            if isinstance(exc, ErroCarteiraDivergente):
                logger.critical(
                    "Encerramento bloqueado: carteira divergente do razão; lote %s, carteira %s",
                    exc.lote_id,
                    exc.carteira_id,
                )
            else:
                async with recursos.fabrica() as s, s.begin():
                    public_id = await s.scalar(select(Lote.public_id).where(Lote.id == lote_id))
                logger.critical("Liquidação bloqueada por integridade do lote %s", public_id)
        raise
    publicar_depois_do_commit(recursos.publicador, eventos)
    return encerrou
