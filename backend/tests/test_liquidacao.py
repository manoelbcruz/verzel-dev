from functools import partial

import anyio
import httpx
import pytest
from sqlalchemy import func, select, text, update

from app.core.erros import ErroIntegridade
from app.db.transacao import leitura_consistente
from app.main import create_app
from app.models import CarteiraRegistro, EventoLote, Lancamento, Liquidacao, Lote, Reserva
from app.services import liquidacao
from app.services.auditoria import auditar_lote
from app.services.encerramento import encerrar_vencidos
from app.services.lances import dar_lance
from tests.apoio import (
    conferir_reconciliacao,
    criar_lote,
    criar_usuario,
    envelhecer_lote,
    simultaneos,
)

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


async def preparar_arremate(recursos):
    leiloeiro = await criar_usuario(recursos, "leiloeiro")
    usuario = await criar_usuario(recursos, saldo=1000)
    lote = await criar_lote(recursos, leiloeiro, segundos=60)
    await dar_lance(recursos, usuario, lote.id, 100, "arremate-lance")
    interno = await envelhecer_lote(recursos, lote.id)
    return lote, interno, leiloeiro, usuario


async def test_arremate_atomico_e_idempotente(recursos):
    lote, interno, leiloeiro, usuario = await preparar_arremate(recursos)
    assert await liquidacao.encerrar_lote(recursos, interno)
    assert not await liquidacao.encerrar_lote(recursos, interno)
    async with recursos.fabrica() as s, s.begin():
        saldos = dict(
            (
                await s.execute(
                    select(CarteiraRegistro.usuario_id, CarteiraRegistro.saldo_centavos)
                )
            ).all()
        )
        assert saldos[usuario.id] == 900 and saldos[leiloeiro.id] == 100
        assert await s.scalar(select(func.count()).select_from(Reserva)) == 0
        paga = (await s.execute(select(Liquidacao.__table__))).mappings().one()
        assert paga["resultado"] == "arrematado" and paga["comprovante_codigo"]
        valores = (
            await s.scalars(
                select(Lancamento.valor_centavos).where(Lancamento.liquidacao_id == paga["id"])
            )
        ).all()
        assert sorted(valores) == [-100, 100]
        assert await s.scalar(select(Lote.status).where(Lote.id == interno)) == "encerrado"
        assert (
            await s.scalar(
                select(func.count())
                .select_from(EventoLote)
                .where(EventoLote.tipo == "encerramento")
            )
            == 1
        )
    assert (await auditar_lote(recursos, lote.id)).veredito == "integro"
    await conferir_reconciliacao(recursos)


async def test_sem_lances(recursos):
    lote = await criar_lote(recursos)
    interno = await envelhecer_lote(recursos, lote.id)
    assert await liquidacao.encerrar_lote(recursos, interno)
    async with recursos.fabrica() as s, s.begin():
        assert await s.scalar(select(Liquidacao.resultado)) == "sem_lances"
        assert await s.scalar(select(func.count()).select_from(Lancamento)) == 0
    assert (await auditar_lote(recursos, lote.id)).veredito == "integro"
    await conferir_reconciliacao(recursos)


async def test_dois_workers_uma_liquidacao(recursos):
    lote, _, _, _ = await preparar_arremate(recursos)
    await simultaneos(partial(encerrar_vencidos, recursos), partial(encerrar_vencidos, recursos))
    async with recursos.fabrica() as s, s.begin():
        assert await s.scalar(select(func.count()).select_from(Liquidacao)) == 1
        assert (
            await s.scalar(
                select(func.count())
                .select_from(Lancamento)
                .where(Lancamento.liquidacao_id.is_not(None))
            )
            == 2
        )
    assert (await auditar_lote(recursos, lote.id)).veredito == "integro"
    await conferir_reconciliacao(recursos)


async def test_falha_depois_debito_credito_reverte_tudo(recursos, monkeypatch):
    _, interno, leiloeiro, usuario = await preparar_arremate(recursos)

    def falhar():
        raise RuntimeError("falha injetada após movimentar carteiras")

    monkeypatch.setattr(liquidacao, "gerar_codigo_comprovante", falhar)
    with pytest.raises(RuntimeError, match="falha injetada"):
        await liquidacao.encerrar_lote(recursos, interno)
    async with recursos.fabrica() as s, s.begin():
        saldos = dict(
            (
                await s.execute(
                    select(CarteiraRegistro.usuario_id, CarteiraRegistro.saldo_centavos)
                )
            ).all()
        )
        assert saldos[usuario.id] == 1000 and saldos[leiloeiro.id] == 0
        assert await s.scalar(select(Reserva.valor_centavos)) == 100
        assert await s.scalar(select(Lote.status).where(Lote.id == interno)) == "publicado"
        assert await s.scalar(select(func.count()).select_from(Liquidacao)) == 0
        assert (
            await s.scalar(
                select(func.count())
                .select_from(EventoLote)
                .where(EventoLote.tipo == "encerramento")
            )
            == 0
        )
    await conferir_reconciliacao(recursos)


async def test_adulteracao_bloqueia_sem_mover_dinheiro(recursos):
    _, interno, _, usuario = await preparar_arremate(recursos)
    async with recursos.fabrica() as s, s.begin():
        await s.execute(
            update(EventoLote)
            .where(EventoLote.lote_id == interno, EventoLote.tipo == "lance")
            .values(valor_centavos=101)
        )
    with pytest.raises(ErroIntegridade):
        await liquidacao.encerrar_lote(recursos, interno)
    async with recursos.fabrica() as s, s.begin():
        assert (
            await s.scalar(
                select(CarteiraRegistro.saldo_centavos).where(
                    CarteiraRegistro.usuario_id == usuario.id
                )
            )
            == 1000
        )
        assert await s.scalar(select(func.count()).select_from(Liquidacao)) == 0
    await conferir_reconciliacao(recursos)


async def test_worker_lifespan(recursos):
    lote = await criar_lote(recursos)
    await envelhecer_lote(recursos, lote.id)
    settings = recursos.settings.model_copy(update={"encerramento_intervalo_s": 0.2})
    app = create_app(settings, transporte_http=httpx.MockTransport(lambda r: httpx.Response(500)))
    async with app.router.lifespan_context(app):
        with anyio.fail_after(5):
            while True:
                async with recursos.fabrica() as s, s.begin():
                    estado = await s.scalar(select(Lote.status).where(Lote.public_id == lote.id))
                if estado == "encerrado":
                    break
                await anyio.sleep(0.1)
    # O context manager só termina depois de cancelar e aguardar a tarefa.
    await conferir_reconciliacao(recursos)


@pytest.mark.parametrize("segurar", [False, True])
async def test_encerramento_preguicoso_espera_trava(recursos, cliente, segurar):
    lote = await criar_lote(recursos)
    interno = await envelhecer_lote(recursos, lote.id)
    respostas = []

    async def consultar():
        respostas.append(await cliente.get(f"/api/lotes/{lote.id}"))

    if segurar:
        async with anyio.create_task_group() as grupo:
            async with recursos.fabrica() as s, s.begin():
                await s.execute(select(Lote.id).where(Lote.id == interno).with_for_update())
                grupo.start_soon(consultar)
                await anyio.sleep(1)
                assert not respostas
    else:
        await consultar()
    assert respostas[0].status_code == 200
    assert respostas[0].json()["resultado"]["situacao"] == "sem_lances"
    await conferir_reconciliacao(recursos)


async def test_leitura_consistente_isolamento(recursos):
    async with leitura_consistente(recursos.fabrica) as s:
        assert await s.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        assert await s.scalar(text("SHOW transaction_read_only")) == "on"


async def test_carteira_divergente_tem_contexto_proprio_e_preserva_reserva(recursos, caplog):
    from app.core.erros import ErroCarteiraDivergente
    from app.services.consultas import detalhar_lote

    lote, interno, leiloeiro, usuario = await preparar_arremate(recursos)
    async with recursos.fabrica() as s, s.begin():
        await s.execute(
            update(CarteiraRegistro)
            .where(CarteiraRegistro.usuario_id == leiloeiro.id)
            .values(saldo_centavos=5)
        )
    with pytest.raises(ErroCarteiraDivergente) as erro:
        await liquidacao.encerrar_lote(recursos, interno)
    assert erro.value.lote_id == lote.id and erro.value.carteira_id == leiloeiro.id
    assert interno in recursos.lotes_bloqueados
    assert (await auditar_lote(recursos, lote.id)).veredito == "integro"
    detalhe = await detalhar_lote(recursos, lote.id)
    assert detalhe.fase == "encerrado" and detalhe.resultado is None
    criticos = [r.getMessage() for r in caplog.records if r.levelname == "CRITICAL"]
    assert len(criticos) == 1
    assert "carteira divergente do razão" in criticos[0]
    assert str(lote.id) in criticos[0] and f"carteira {leiloeiro.id}" in criticos[0]
    assert leiloeiro.nome not in criticos[0] and leiloeiro.email not in criticos[0]
    async with recursos.fabrica() as s, s.begin():
        assert (
            await s.scalar(
                select(CarteiraRegistro.saldo_centavos).where(
                    CarteiraRegistro.usuario_id == usuario.id
                )
            )
            == 1000
        )
        assert (
            await s.scalar(
                select(CarteiraRegistro.saldo_centavos).where(
                    CarteiraRegistro.usuario_id == leiloeiro.id
                )
            )
            == 5
        )
        assert (
            await s.scalar(select(Reserva.valor_centavos).where(Reserva.lote_id == interno)) == 100
        )
        assert await s.scalar(select(func.count()).select_from(Liquidacao)) == 0
