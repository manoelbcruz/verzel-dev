from functools import partial

import anyio
import pytest
from sqlalchemy import func, select, text

from app.core.erros import Recusa
from app.models import EventoLote, Lancamento, Lote, Reserva
from app.services.auditoria import auditar_lote
from app.services.carteira import depositar
from app.services.consultas import consultar_carteira, ler_detalhe
from app.services.encerramento import encerrar_vencidos
from app.services.lances import dar_lance
from app.services.lotes import cancelar_lote
from tests.apoio import conferir_reconciliacao, criar_lote, criar_usuario, simultaneos

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


async def test_seis_primeiros_lances(recursos):
    lote = await criar_lote(recursos)
    usuarios = [await criar_usuario(recursos, saldo=1000) for _ in range(6)]
    respostas = await simultaneos(
        *[
            partial(dar_lance, recursos, usuario, lote.id, 100, f"primeiro-{i}")
            for i, usuario in enumerate(usuarios)
        ]
    )
    assert sum(not isinstance(r, Recusa) for r in respostas) == 1
    assert [r.codigo for r in respostas if isinstance(r, Recusa)] == ["abaixo_do_minimo"] * 5
    async with recursos.fabrica() as s, s.begin():
        assert await s.scalar(select(func.count()).select_from(Reserva)) == 1
        assert await s.scalar(select(Lote.total_lances).where(Lote.public_id == lote.id)) == 1
    assert (await auditar_lote(recursos, lote.id)).veredito == "integro"
    await conferir_reconciliacao(recursos)


async def test_saldo_disputado_em_dois_lotes(recursos):
    usuario = await criar_usuario(recursos, saldo=100)
    lotes = [await criar_lote(recursos, inicial=80) for _ in range(2)]
    respostas = await simultaneos(
        *[
            partial(dar_lance, recursos, usuario, lote.id, 80, f"saldo-lote-{i}")
            for i, lote in enumerate(lotes)
        ]
    )
    assert sum(not isinstance(r, Recusa) for r in respostas) == 1
    assert [r.codigo for r in respostas if isinstance(r, Recusa)] == ["saldo_insuficiente"]
    assert (await consultar_carteira(recursos, usuario)).comprometido_centavos == 80
    await conferir_reconciliacao(recursos)


async def test_lideres_cruzados_vinte_rodadas(recursos):
    a, b = [await criar_usuario(recursos, saldo=10000) for _ in range(2)]
    x, y = [await criar_lote(recursos) for _ in range(2)]
    await dar_lance(recursos, a, x.id, 100, "inicial-x")
    await dar_lance(recursos, b, y.id, 100, "inicial-y")

    async def contar_deadlocks():
        async with recursos.fabrica() as s, s.begin():
            await s.execute(text("SELECT pg_stat_clear_snapshot()"))
            return await s.scalar(
                text("SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()")
            )

    deadlocks_antes = await contar_deadlocks()
    for rodada in range(20):
        proximo_x, proximo_y = (b, a) if rodada % 2 == 0 else (a, b)
        valor = 110 + rodada * 10
        respostas = await simultaneos(
            partial(dar_lance, recursos, proximo_x, x.id, valor, f"cruzado-x-{rodada}"),
            partial(dar_lance, recursos, proximo_y, y.id, valor, f"cruzado-y-{rodada}"),
        )
        assert all(not isinstance(r, Recusa) for r in respostas)
        await conferir_reconciliacao(recursos)
    # Dá tempo à publicação das estatísticas cumulativas antes da leitura em outra transação.
    await anyio.sleep(1.1)
    assert await contar_deadlocks() - deadlocks_antes == 0
    async with recursos.fabrica() as s, s.begin():
        for lote, lider in ((x, a), (y, b)):
            estado = (
                await s.execute(
                    select(Lote.lider_id, Lote.total_lances, Lote.lance_atual_centavos).where(
                        Lote.public_id == lote.id
                    )
                )
            ).one()
            assert tuple(estado) == (lider.id, 21, 300)


async def test_reserva_liberada_imediatamente(recursos):
    a, b = [await criar_usuario(recursos, saldo=100) for _ in range(2)]
    x, y = [await criar_lote(recursos, inicial=80) for _ in range(2)]
    await dar_lance(recursos, a, x.id, 80, "reserva-a")
    await dar_lance(recursos, b, x.id, 90, "reserva-b")
    assert (await dar_lance(recursos, a, y.id, 90, "nova-reserva")).status_http == 201
    await conferir_reconciliacao(recursos)


async def test_lance_idempotente_concorrente_e_superado(recursos):
    a, b = [await criar_usuario(recursos, saldo=1000) for _ in range(2)]
    lote = await criar_lote(recursos)
    chamada = partial(dar_lance, recursos, a, lote.id, 100, "lance-igual")
    respostas = await simultaneos(*[chamada] * 5)
    assert sum(not r.repetida for r in respostas) == 1
    assert all(r.resposta == respostas[0].resposta and r.status_http == 201 for r in respostas)
    assert (await chamada()).repetida
    await dar_lance(recursos, b, lote.id, 110, "supera-lance")
    repeticao = await chamada()
    assert repeticao.repetida and repeticao.resposta == respostas[0].resposta
    with pytest.raises(Recusa) as erro:
        await dar_lance(recursos, a, lote.id, 120, "lance-igual")
    assert erro.value.codigo == "chave_idempotencia_conflito"
    async with recursos.fabrica() as s, s.begin():
        assert (
            await s.scalar(
                select(func.count()).select_from(EventoLote).where(EventoLote.tipo == "lance")
            )
            == 2
        )
    await conferir_reconciliacao(recursos)


async def test_dez_depositos_uma_chave(recursos):
    usuario = await criar_usuario(recursos)
    respostas = await simultaneos(
        *[partial(depositar, recursos, usuario, 100, "deposito-igual")] * 10
    )
    assert all(r.resposta == respostas[0].resposta for r in respostas)
    assert sum(not r.repetida for r in respostas) == 1
    async with recursos.fabrica() as s, s.begin():
        assert await s.scalar(select(func.count()).select_from(Lancamento)) == 1
    await conferir_reconciliacao(recursos)


async def test_relogio_depois_da_trava(recursos):
    usuario = await criar_usuario(recursos, saldo=1000)
    lote = await criar_lote(recursos, segundos=1)
    resultado = []

    async def tentar():
        try:
            await dar_lance(recursos, usuario, lote.id, 100, "espera-trava")
        except Recusa as erro:
            resultado.append(erro.codigo)

    async with anyio.create_task_group() as grupo:
        async with recursos.fabrica() as s, s.begin():
            await s.execute(select(Lote.id).where(Lote.public_id == lote.id).with_for_update())
            grupo.start_soon(tentar)
            await anyio.sleep(1.5)
    assert resultado == ["lote_encerrado"]
    await conferir_reconciliacao(recursos)


@pytest.mark.parametrize("rodada", range(3))
async def test_lance_disputa_encerramento(recursos, rodada):
    usuario = await criar_usuario(recursos, saldo=1000)
    lote = await criar_lote(recursos, segundos=1)
    await anyio.sleep(0.95)
    respostas = await simultaneos(
        partial(dar_lance, recursos, usuario, lote.id, 100, f"lance-fim-{rodada}"),
        partial(encerrar_vencidos, recursos),
    )
    await anyio.sleep(0.15)
    await encerrar_vencidos(recursos)
    async with recursos.fabrica() as s, s.begin():
        estado = (
            (await s.execute(select(Lote.__table__).where(Lote.public_id == lote.id)))
            .mappings()
            .one()
        )
        if isinstance(respostas[0], Recusa):
            assert respostas[0].codigo == "lote_encerrado"
            assert estado["status"] == "encerrado" and estado["lider_id"] is None
        else:
            assert estado["status"] == "publicado" and estado["total_lances"] == 1
            assert estado["fim_em"] > lote.fim_em
    await conferir_reconciliacao(recursos)


async def test_cancelamento_disputa_primeiro_lance(recursos):
    leiloeiro = await criar_usuario(recursos, "leiloeiro")
    usuario = await criar_usuario(recursos, saldo=1000)
    lote = await criar_lote(recursos, leiloeiro)
    respostas = await simultaneos(
        partial(cancelar_lote, recursos, leiloeiro, lote.id),
        partial(dar_lance, recursos, usuario, lote.id, 100, "disputa-cancelar"),
    )
    assert sum(isinstance(r, Recusa) for r in respostas) == 1
    assert [r.codigo for r in respostas if isinstance(r, Recusa)][0] in {
        "lote_cancelado",
        "lote_com_lances",
    }
    async with recursos.fabrica() as s, s.begin():
        estado = (
            (await s.execute(select(Lote.__table__).where(Lote.public_id == lote.id)))
            .mappings()
            .one()
        )
        lances = await s.scalar(
            select(func.count())
            .select_from(EventoLote)
            .where(EventoLote.lote_id == estado["id"], EventoLote.tipo == "lance")
        )
        reservas = (
            (await s.execute(select(Reserva.__table__).where(Reserva.lote_id == estado["id"])))
            .mappings()
            .all()
        )
        if isinstance(respostas[1], Recusa):
            assert estado["status"] == "cancelado"
            assert estado["total_lances"] == lances == 0 and reservas == []
            assert estado["lider_id"] is None and estado["lance_atual_centavos"] is None
        else:
            assert estado["status"] == "publicado"
            assert estado["total_lances"] == lances == 1
            assert estado["lider_id"] == usuario.id and estado["lance_atual_centavos"] == 100
            assert len(reservas) == 1
            assert reservas[0]["usuario_id"] == usuario.id
            assert reservas[0]["valor_centavos"] == 100
    detalhe, _, _ = await ler_detalhe(recursos, lote.id, leiloeiro)
    assert detalhe.cancelavel is False
    assert (await auditar_lote(recursos, lote.id)).veredito == "integro"
    await conferir_reconciliacao(recursos)
