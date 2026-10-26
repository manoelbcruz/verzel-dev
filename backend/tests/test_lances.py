from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.erros import Recusa
from app.models import ChaveIdempotencia, EventoLote, Lote
from app.services.consultas import consultar_carteira
from app.services.lances import dar_lance
from app.services.lotes import cancelar_lote
from tests.apoio import conferir_reconciliacao, criar_lote, criar_usuario, envelhecer_lote

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


@pytest.mark.parametrize("segundos,prorrogou", [(60, True), (3600, False)])
async def test_lance_prorrogacao_real(recursos, segundos, prorrogou):
    usuario = await criar_usuario(recursos, saldo=1000)
    lote = await criar_lote(recursos, segundos=segundos)
    aceito = await dar_lance(recursos, usuario, lote.id, 100, "lance-aceito")
    assert aceito.resposta["prorrogou"] is prorrogou
    async with recursos.fabrica() as s, s.begin():
        evento = (
            (await s.execute(select(EventoLote.__table__).where(EventoLote.tipo == "lance")))
            .mappings()
            .one()
        )
        fim = await s.scalar(select(Lote.fim_em).where(Lote.public_id == lote.id))
        assert fim == (evento["instante"] + timedelta(seconds=120) if prorrogou else lote.fim_em)
    await conferir_reconciliacao(recursos)


async def test_recusas_detalhes_e_reavaliacao_chave(recursos):
    dono = await criar_usuario(recursos, "leiloeiro")
    a, b = [await criar_usuario(recursos, saldo=100) for _ in range(2)]
    lote = await criar_lote(recursos, dono)
    with pytest.raises(Recusa) as erro:
        await dar_lance(recursos, a, lote.id, 99, "mesma-chave")
    assert erro.value.codigo == "abaixo_do_minimo" and erro.value.detalhes == {
        "minimo_centavos": 100
    }
    assert (await dar_lance(recursos, a, lote.id, 100, "mesma-chave")).status_http == 201
    for usuario, valor, codigo, detalhes in [
        (a, 110, "ja_esta_ganhando", {}),
        (b, 109, "abaixo_do_minimo", {"minimo_centavos": 110}),
        (b, 110, "saldo_insuficiente", {"disponivel_centavos": 100}),
        (dono, 110, "papel_nao_permitido", {}),
    ]:
        with pytest.raises(Recusa) as erro:
            await dar_lance(recursos, usuario, lote.id, valor, "recusa-negocio")
        assert erro.value.codigo == codigo and erro.value.detalhes == detalhes
    async with recursos.fabrica() as s, s.begin():
        assert (
            await s.scalar(
                select(func.count())
                .select_from(ChaveIdempotencia)
                .where(ChaveIdempotencia.chave == "recusa-negocio")
            )
            == 0
        )
    assert (await consultar_carteira(recursos, a)).disponivel_centavos == 0
    await conferir_reconciliacao(recursos)


@pytest.mark.parametrize(
    "estado,codigo",
    [
        ("agendado", "lote_nao_iniciado"),
        ("cancelado", "lote_cancelado"),
        ("vencido", "lote_encerrado"),
    ],
)
async def test_recusas_de_estado(recursos, estado, codigo):
    dono = await criar_usuario(recursos, "leiloeiro")
    usuario = await criar_usuario(recursos, saldo=1000)
    async with recursos.fabrica() as s, s.begin():
        agora = await s.scalar(select(func.clock_timestamp()))
    lote = await criar_lote(
        recursos, dono, inicio=agora + timedelta(minutes=1) if estado == "agendado" else None
    )
    if estado == "cancelado":
        await cancelar_lote(recursos, dono, lote.id)
    if estado == "vencido":
        await envelhecer_lote(recursos, lote.id)
    with pytest.raises(Recusa) as erro:
        await dar_lance(recursos, usuario, lote.id, 100, "lance-estado")
    assert erro.value.codigo == codigo
    await conferir_reconciliacao(recursos)
