import copy
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, insert, select, update

from app.core.erros import ErroIntegridade, Recusa
from app.models import (
    CarteiraRegistro,
    ChaveIdempotencia,
    EventoLote,
    Lancamento,
    Liquidacao,
    Lote,
    Midia,
    Reserva,
)
from app.services.auditoria import auditar_lote
from app.services.consultas import carregar_dados
from app.services.encerramento import encerrar_vencidos
from app.services.lances import dar_lance
from app.services.liquidacao import encerrar_lote
from app.services.lotes import cancelar_lote
from tests.apoio import criar_lote, criar_usuario, envelhecer_lote, id_interno

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


async def historico(recursos, encerrado=False):
    dono = await criar_usuario(recursos, "leiloeiro")
    a, b = [await criar_usuario(recursos, saldo=1000) for _ in range(2)]
    lote = await criar_lote(recursos, dono, segundos=60)
    await dar_lance(recursos, a, lote.id, 100, "auditoria-01")
    await dar_lance(recursos, b, lote.id, 110, "auditoria-02")
    interno = await id_interno(recursos, lote.id)
    if encerrado:
        await envelhecer_lote(recursos, lote.id)
        await encerrar_lote(recursos, interno)
    assert (await auditar_lote(recursos, lote.id)).veredito == "integro"
    return lote, interno, dono, a, b


@pytest.mark.parametrize(
    "mutacao,codigo,encerrado",
    [
        ("valor", "mac_invalido", False),
        ("licitante", "pseudonimo_divergente", False),
        ("pseudonimo", "pseudonimo_divergente", False),
        ("meio", "sequencia_quebrada", False),
        ("ultimo", "cabeca_invalida", False),
        ("cabeca_falsa", "cabeca_invalida", False),
        ("insercao", "mac_invalido", False),
        ("insercao", "gramatica_invalida", True),
        ("lance_atual_centavos", "projecao_divergente", False),
        ("lider_id", "projecao_divergente", False),
        ("fim_em", "projecao_divergente", False),
        ("lance_atual_centavos", "projecao_divergente", True),
        ("lider_id", "projecao_divergente", True),
        ("fim_em", "projecao_divergente", True),
        ("titulo", "mac_invalido", False),
        ("atributos", "mac_invalido", False),
        ("midia", "midia_divergente", False),
        ("liquidacao_valor", "mac_invalido", True),
        ("liquidacao_vencedor", "mac_invalido", True),
        ("liquidacao_ausente", "liquidacao_divergente", True),
        ("lancamento_ausente", "liquidacao_divergente", True),
        ("reserva", "reserva_divergente", False),
        ("outro_lote", "mac_invalido", False),
    ],
)
async def test_adulteracao_sql(recursos, mutacao, codigo, encerrado):
    lote, interno, dono, a, b = await historico(recursos, encerrado)
    outro = await criar_lote(recursos, dono) if mutacao == "outro_lote" else None
    outro_id = await id_interno(recursos, outro.id) if outro else None
    async with recursos.fabrica() as s, s.begin():
        dados_lote = (
            (await s.execute(select(Lote.__table__).where(Lote.id == interno))).mappings().one()
        )
        seq = dados_lote["cabeca_seq"]
        evento = EventoLote.lote_id == interno
        match mutacao:
            case "valor":
                await s.execute(
                    update(EventoLote).where(evento, EventoLote.seq == 2).values(valor_centavos=101)
                )
            case "licitante":
                await s.execute(
                    update(EventoLote).where(evento, EventoLote.seq == 2).values(licitante_id=b.id)
                )
            case "pseudonimo":
                await s.execute(
                    update(EventoLote).where(evento, EventoLote.seq == 2).values(pseudonimo="outro")
                )
            case "meio":
                await s.execute(delete(EventoLote).where(evento, EventoLote.seq == 2))
            case "ultimo" | "cabeca_falsa":
                await s.execute(delete(EventoLote).where(evento, EventoLote.seq == seq))
                if mutacao == "cabeca_falsa":
                    mac = await s.scalar(
                        select(EventoLote.mac).where(evento, EventoLote.seq == seq - 1)
                    )
                    await s.execute(
                        update(Lote)
                        .where(Lote.id == interno)
                        .values(cabeca_seq=seq - 1, cabeca_assinatura=mac)
                    )
            case "insercao":
                falso = dict(
                    (
                        await s.execute(
                            select(EventoLote.__table__).where(evento, EventoLote.seq == 3)
                        )
                    )
                    .mappings()
                    .one()
                )
                falso.pop("id")
                falso.update(seq=seq + 1, mac=bytes(32))
                await s.execute(insert(EventoLote.__table__).values(**falso))
            case "lance_atual_centavos":
                await s.execute(
                    update(Lote).where(Lote.id == interno).values(lance_atual_centavos=105)
                )
            case "lider_id":
                await s.execute(update(Lote).where(Lote.id == interno).values(lider_id=a.id))
            case "fim_em":
                await s.execute(
                    update(Lote)
                    .where(Lote.id == interno)
                    .values(fim_em=dados_lote["fim_em"] + timedelta(seconds=1))
                )
            case "titulo" | "atributos":
                await s.execute(
                    update(Lote)
                    .where(Lote.id == interno)
                    .values(
                        **{
                            mutacao: "Outra obra"
                            if mutacao == "titulo"
                            else {"artista": "Outra pessoa"}
                        }
                    )
                )
            case "midia":
                await s.execute(
                    update(Midia)
                    .where(Midia.id == dados_lote["midia_id"])
                    .values(dados=b"adulterada")
                )
            case "liquidacao_valor":
                await s.execute(
                    update(Liquidacao)
                    .where(Liquidacao.lote_id == interno)
                    .values(valor_centavos=111)
                )
            case "liquidacao_vencedor":
                await s.execute(
                    update(Liquidacao).where(Liquidacao.lote_id == interno).values(vencedor_id=a.id)
                )
            case "liquidacao_ausente" | "lancamento_ausente":
                liquidacao_id = await s.scalar(
                    select(Liquidacao.id).where(Liquidacao.lote_id == interno)
                )
                consulta = delete(Lancamento).where(Lancamento.liquidacao_id == liquidacao_id)
                if mutacao == "lancamento_ausente":
                    consulta = consulta.where(Lancamento.tipo == "arremate_debito")
                await s.execute(consulta)
                if mutacao == "liquidacao_ausente":
                    await s.execute(delete(Liquidacao).where(Liquidacao.id == liquidacao_id))
            case "reserva":
                await s.execute(
                    update(Reserva).where(Reserva.lote_id == interno).values(valor_centavos=111)
                )
            case "outro_lote":
                await s.execute(delete(EventoLote).where(evento))
                await s.execute(
                    update(EventoLote).where(EventoLote.lote_id == outro_id).values(lote_id=interno)
                )
    relatorio = await auditar_lote(recursos, lote.id)
    assert relatorio.veredito == "adulterado"
    assert relatorio.falha.codigo == codigo


@pytest.mark.parametrize("mutacao", ["projecao", "remocao"])
async def test_lance_nao_lava_projecao_ou_remocao(recursos, mutacao):
    lote, interno, _, a, _ = await historico(recursos)
    async with recursos.fabrica() as s, s.begin():
        if mutacao == "projecao":
            await s.execute(update(Lote).where(Lote.id == interno).values(lance_atual_centavos=50))
        else:
            await s.execute(
                delete(EventoLote).where(EventoLote.lote_id == interno, EventoLote.seq == 3)
            )
            await s.execute(update(Lote).where(Lote.id == interno).values(cabeca_seq=2))
        antes = await s.scalar(select(func.count()).select_from(EventoLote))
        chaves = await s.scalar(select(func.count()).select_from(ChaveIdempotencia))
    with pytest.raises(Recusa) as erro:
        await dar_lance(recursos, a, lote.id, 120, "nao-lavar-projecao")
    assert erro.value.codigo == "lote_adulterado"
    async with recursos.fabrica() as s, s.begin():
        assert await s.scalar(select(func.count()).select_from(EventoLote)) == antes
        assert await s.scalar(select(func.count()).select_from(ChaveIdempotencia)) == chaves


async def test_cancelamento_nao_assina_ponta_adulterada(recursos):
    dono = await criar_usuario(recursos, "leiloeiro")
    lote = await criar_lote(recursos, dono)
    async with recursos.fabrica() as s, s.begin():
        await s.execute(
            update(Lote).where(Lote.public_id == lote.id).values(cabeca_assinatura=bytes(32))
        )
    with pytest.raises(Recusa) as erro:
        await cancelar_lote(recursos, dono, lote.id)
    assert erro.value.codigo == "lote_adulterado"


async def guardar_estado(recursos, interno):
    async with recursos.fabrica() as s, s.begin():
        lote = (await s.execute(select(Lote.__table__).where(Lote.id == interno))).mappings().one()
        dados = await carregar_dados(s, lote)
        return (
            dict(lote),
            [dict(e) for e in dados.eventos],
            dict(dados.reserva) if dados.reserva else None,
        )


async def restaurar_estado(recursos, estado):
    lote, eventos, reserva = copy.deepcopy(estado)
    interno = lote["id"]
    async with recursos.fabrica() as s, s.begin():
        liquidacao_id = await s.scalar(select(Liquidacao.id).where(Liquidacao.lote_id == interno))
        if liquidacao_id:
            await s.execute(delete(Lancamento).where(Lancamento.liquidacao_id == liquidacao_id))
            await s.execute(delete(Liquidacao).where(Liquidacao.id == liquidacao_id))
        await s.execute(delete(EventoLote).where(EventoLote.lote_id == interno))
        await s.execute(delete(Reserva).where(Reserva.lote_id == interno))
        await s.execute(update(Lote).where(Lote.id == interno).values(**lote))
        await s.execute(insert(EventoLote.__table__), eventos)
        if reserva:
            await s.execute(insert(Reserva.__table__).values(**reserva))


async def test_restauracao_sem_carteiras_nao_paga_duas_vezes(recursos):
    lote, interno, _, _, _ = await historico(recursos)
    await envelhecer_lote(recursos, lote.id)
    estado = await guardar_estado(recursos, interno)
    await encerrar_lote(recursos, interno)
    async with recursos.fabrica() as s, s.begin():
        saldos = (
            await s.execute(
                select(CarteiraRegistro.__table__).order_by(CarteiraRegistro.usuario_id)
            )
        ).all()
    await restaurar_estado(recursos, estado)
    with pytest.raises(ErroIntegridade):
        await encerrar_lote(recursos, interno)
    async with recursos.fabrica() as s, s.begin():
        assert (
            await s.execute(
                select(CarteiraRegistro.__table__).order_by(CarteiraRegistro.usuario_id)
            )
        ).all() == saldos
        assert await s.scalar(select(func.count()).select_from(Liquidacao)) == 0


async def test_lote_bloqueado_nao_ocupa_fila_nem_repete_critical(recursos, caplog):
    ruim = await criar_lote(recursos)
    ruim_id = await envelhecer_lote(recursos, ruim.id)
    bom = await criar_lote(recursos)
    await envelhecer_lote(recursos, bom.id)
    async with recursos.fabrica() as s, s.begin():
        await s.execute(update(Lote).where(Lote.id == ruim_id).values(titulo="Título adulterado"))
    assert await encerrar_vencidos(recursos) == 1
    assert await encerrar_vencidos(recursos) == 0
    assert ruim_id in recursos.lotes_bloqueados
    assert len([r for r in caplog.records if r.levelname == "CRITICAL"]) == 1
    assert (await auditar_lote(recursos, bom.id)).veredito == "integro"


async def test_limite_restauracao_completa_nao_detectada(recursos):
    """Limite aceito: restaurar um estado inteiro autenticado requer âncora externa para detectar.

    Lances só alteram reservas, não saldos; restaurar eventos, projeções, cabeça e reserva
    recompõe o estado antigo inteiro do lote. A produção precisaria de âncora externa.
    """
    lote, interno, _, a, b = await historico(recursos)
    estado = await guardar_estado(recursos, interno)
    await dar_lance(recursos, a, lote.id, 120, "restaura-03")
    await dar_lance(recursos, b, lote.id, 130, "restaura-04")
    await restaurar_estado(recursos, estado)
    assert (await auditar_lote(recursos, lote.id)).veredito == "integro"


@pytest.mark.parametrize("mutacao", ["snapshot", "lavagem", "evento_extra"])
async def test_escrita_recusa_cadeia_adulterada_sem_efeitos(recursos, mutacao):
    a, b, c = [await criar_usuario(recursos, saldo=1000) for _ in range(3)]
    lote = await criar_lote(recursos)
    await dar_lance(recursos, a, lote.id, 100, "antes-adulteracao-1")
    if mutacao == "lavagem":
        await dar_lance(recursos, b, lote.id, 500, "antes-adulteracao-2")
    interno = await id_interno(recursos, lote.id)
    async with recursos.fabrica() as s, s.begin():
        if mutacao == "snapshot":
            await s.execute(
                update(Lote)
                .where(Lote.id == interno)
                .values(titulo="Adulterado", incremento_centavos=1)
            )
        elif mutacao == "lavagem":
            await s.execute(
                update(EventoLote)
                .where(EventoLote.lote_id == interno, EventoLote.seq == 3)
                .values(valor_centavos=110)
            )
            await s.execute(update(Lote).where(Lote.id == interno).values(lance_atual_centavos=110))
            await s.execute(
                update(Reserva).where(Reserva.lote_id == interno).values(valor_centavos=110)
            )
        else:
            falso = dict(
                (
                    await s.execute(
                        select(EventoLote.__table__).where(
                            EventoLote.lote_id == interno, EventoLote.seq == 2
                        )
                    )
                )
                .mappings()
                .one()
            )
            falso.pop("id")
            falso.update(seq=3, mac=bytes(32))
            await s.execute(insert(EventoLote.__table__).values(**falso))
        eventos_antes = (
            await s.execute(
                select(EventoLote.__table__)
                .where(EventoLote.lote_id == interno)
                .order_by(EventoLote.seq)
            )
        ).all()
        reserva_antes = (
            await s.execute(select(Reserva.__table__).where(Reserva.lote_id == interno))
        ).one()
        lote_antes = (await s.execute(select(Lote.__table__).where(Lote.id == interno))).one()
        chaves_antes = (
            await s.execute(select(ChaveIdempotencia.__table__).order_by(ChaveIdempotencia.id))
        ).all()
    valor = 101 if mutacao == "snapshot" else 120
    with pytest.raises(ErroIntegridade) as erro:
        await dar_lance(recursos, c, lote.id, valor, "depois-adulteracao")
    assert erro.value.status == 409 and erro.value.codigo == "lote_adulterado"
    assert erro.value.detalhes["falha"] == (
        "cabeca_invalida" if mutacao == "evento_extra" else "mac_invalido"
    )
    async with recursos.fabrica() as s, s.begin():
        assert (
            await s.execute(
                select(EventoLote.__table__)
                .where(EventoLote.lote_id == interno)
                .order_by(EventoLote.seq)
            )
        ).all() == eventos_antes
        assert (
            await s.execute(select(Reserva.__table__).where(Reserva.lote_id == interno))
        ).one() == reserva_antes
        assert (
            await s.execute(select(Lote.__table__).where(Lote.id == interno))
        ).one() == lote_antes
        assert (
            await s.execute(select(ChaveIdempotencia.__table__).order_by(ChaveIdempotencia.id))
        ).all() == chaves_antes


async def test_carregamento_auditoria_so_traz_hash_da_midia(recursos):
    import hashlib

    from tests.apoio import PNG

    lote = await criar_lote(recursos)
    async with recursos.fabrica() as s, s.begin():
        registro = (
            (await s.execute(select(Lote.__table__).where(Lote.public_id == lote.id)))
            .mappings()
            .one()
        )
        dados = await carregar_dados(s, registro)
    assert dados.midia_sha256_calculado == hashlib.sha256(PNG).hexdigest()
    assert not hasattr(dados, "midia_dados")
