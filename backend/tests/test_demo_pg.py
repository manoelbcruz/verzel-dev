import secrets

import anyio
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select, text

from app.db.base import Base
from app.demo.catalogo import CATALOGO
from app.demo.seed import TRAVA_DEMO, garantir_demonstracao
from app.models import CarteiraRegistro, EventoLote, Liquidacao, Lote, Sessao, Usuario
from app.schemas.auth import CadastroEntrada
from app.services.auditoria import auditar_lote
from app.services.auth import cadastrar_usuario
from app.services.consultas import vitrine
from app.services.liquidacao import encerrar_lote
from app.services.lotes import cancelar_lote
from tests.apoio import conferir_reconciliacao, envelhecer_lote, simultaneos

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


async def contagens(recursos):
    async with recursos.fabrica() as s, s.begin():
        return {
            t.name: await s.scalar(select(func.count()).select_from(t))
            for t in Base.metadata.sorted_tables
        }


async def conferir_seed(recursos):
    async with recursos.fabrica() as s, s.begin():
        assert await s.scalar(select(func.count()).select_from(Usuario)) == 3
        assert (
            await s.scalar(
                select(func.count()).select_from(Sessao).where(Sessao.revogada_em.is_(None))
            )
            == 0
        )
        lotes = (
            await s.execute(select(Lote.item_id_externo, Lote.public_id, Lote.total_lances))
        ).all()
        assert {int(lote.item_id_externo): lote.total_lances for lote in lotes} == {
            p.item_id: len(p.lances) for p in CATALOGO
        }
        saldos = dict(
            (
                await s.execute(
                    select(Usuario.email, CarteiraRegistro.saldo_centavos).join(CarteiraRegistro)
                )
            ).all()
        )
        assert saldos["comprador1@demo.example"] == saldos["comprador2@demo.example"] == 1000000
    for lote in lotes:
        assert (await auditar_lote(recursos, lote.public_id)).veredito == "integro"
    await conferir_reconciliacao(recursos)


async def test_seed_completo_idempotente(recursos):
    resumo = await garantir_demonstracao(recursos)
    assert resumo.erro is None
    assert (resumo.usuarios_criados, resumo.depositos, resumo.lotes_criados, resumo.lances) == (
        3,
        2,
        4,
        7,
    )
    await conferir_seed(recursos)
    vitrine_inicial = await vitrine(recursos)
    assert len(vitrine_inicial.ao_vivo) == 3 and len(vitrine_inicial.agendados) == 1
    antes = await contagens(recursos)
    assert (await garantir_demonstracao(recursos)).erro is None
    assert await contagens(recursos) == antes


async def test_seed_simultaneo(recursos):
    await simultaneos(
        lambda: garantir_demonstracao(recursos), lambda: garantir_demonstracao(recursos)
    )
    await conferir_seed(recursos)


@pytest.mark.parametrize("indice", [0, 2])
async def test_reposicao_ao_vivo_e_resultado_do_curto(recursos, indice):
    await garantir_demonstracao(recursos)
    async with recursos.fabrica() as s, s.begin():
        public_id = await s.scalar(
            select(Lote.public_id).where(Lote.item_id_externo == str(CATALOGO[indice].item_id))
        )
    await encerrar_lote(recursos, await envelhecer_lote(recursos, public_id))
    resumo = await garantir_demonstracao(recursos)
    assert resumo.lotes_criados == (1 if indice == 0 else 0)
    async with recursos.fabrica() as s, s.begin():
        liquidacao = (
            await s.execute(select(Liquidacao.resultado, Liquidacao.comprovante_codigo))
        ).one()
        assert liquidacao.resultado == "arrematado" and liquidacao.comprovante_codigo
    await conferir_reconciliacao(recursos)


async def test_cancelado_reposto(recursos):
    from app.demo.seed import ResumoSeed, _usuarios

    await garantir_demonstracao(recursos)
    usuarios = await _usuarios(recursos, ResumoSeed())
    async with recursos.fabrica() as s, s.begin():
        public_id = await s.scalar(select(Lote.public_id).where(Lote.item_id_externo == "459123"))
    await cancelar_lote(recursos, usuarios["leiloeiro"], public_id)
    assert (await garantir_demonstracao(recursos)).lotes_criados == 1


@pytest.mark.parametrize("papel", ["leiloeiro", "licitante"])
async def test_conta_divergente_nao_movimenta(recursos, papel, caplog):
    await cadastrar_usuario(
        recursos,
        CadastroEntrada(
            nome="Conta existente",
            email="comprador1@demo.example",
            senha=secrets.token_urlsafe(18),
            papel=papel,
        ),
    )
    antes = await contagens(recursos)
    assert (await garantir_demonstracao(recursos)).erro == "conta_demo_divergente"
    assert await contagens(recursos) == antes
    assert not recursos.contas_demo
    assert "divergente" in caplog.text


async def test_troca_senha_demo_nao_reutiliza_contas(recursos):
    await garantir_demonstracao(recursos)
    antes = await contagens(recursos)
    recursos.settings.senha_demo = SecretStr(secrets.token_urlsafe(18))
    assert (await garantir_demonstracao(recursos)).erro == "conta_demo_divergente"
    assert not recursos.contas_demo
    assert await contagens(recursos) == antes


async def test_trava_ocupada(recursos):
    async with recursos.engine.connect() as conexao:
        assert await conexao.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": TRAVA_DEMO})
        await conexao.commit()
        try:
            antes = await contagens(recursos)
            resumo = await garantir_demonstracao(recursos)
            assert not resumo.trava_obtida and resumo.erro is None
            assert await contagens(recursos) == antes
        finally:
            await conexao.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": TRAVA_DEMO})
            await conexao.commit()


async def test_cancelamento_libera_trava_sem_engolir_cancelamento(recursos, monkeypatch):
    from app.demo import seed

    iniciou = anyio.Event()

    async def bloquear(*args):
        iniciou.set()
        await anyio.sleep_forever()

    monkeypatch.setattr(seed, "_semear", bloquear)
    retornou = False
    terminou = anyio.Event()
    escopo = anyio.CancelScope()

    async def executar():
        nonlocal retornou
        with escopo:
            await garantir_demonstracao(recursos)
            retornou = True
        terminou.set()

    async with anyio.create_task_group() as grupo:
        grupo.start_soon(executar)
        with anyio.fail_after(5):
            await iniciou.wait()
            escopo.cancel()
            await terminou.wait()
    assert escopo.cancel_called and not retornou
    async with recursos.engine.connect() as conexao:
        assert await conexao.scalar(
            text(
                "SELECT NOT EXISTS (SELECT 1 FROM pg_locks "
                "WHERE locktype = 'advisory' AND classid = 0 AND objid = :id AND objsubid = 1)"
            ),
            {"id": TRAVA_DEMO},
        )
        assert await conexao.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": TRAVA_DEMO})
        await conexao.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": TRAVA_DEMO})
        await conexao.commit()


@pytest.mark.parametrize("interromper_apos", range(1, 12))
async def test_retomada_apos_cada_publicacao_ou_lance(recursos, monkeypatch, interromper_apos):
    from app.demo import seed

    feitas = 0

    def interrompivel(original):
        async def executar(*args, **kwargs):
            nonlocal feitas
            resposta = await original(*args, **kwargs)
            feitas += 1
            if feitas == interromper_apos:
                raise RuntimeError("Interrupção depois do commit")
            return resposta

        return executar

    with monkeypatch.context() as m:
        m.setattr(seed, "publicar_lote", interrompivel(seed.publicar_lote))
        m.setattr(seed, "dar_lance", interrompivel(seed.dar_lance))
        assert (await garantir_demonstracao(recursos)).erro == "RuntimeError"
    assert (await garantir_demonstracao(recursos)).erro is None
    await conferir_seed(recursos)
    async with recursos.fabrica() as s, s.begin():
        assert (
            await s.scalar(
                select(func.count()).select_from(EventoLote).where(EventoLote.tipo == "lance")
            )
            == 7
        )


@pytest.mark.parametrize("deposito_concorrente", [False, True])
async def test_saldo_perto_do_teto_nao_interrompe_reposicao(
    recursos, monkeypatch, caplog, deposito_concorrente
):
    from app.demo import seed
    from app.services import carteira
    from app.services.consultas import consultar_carteira
    from app.services.lances import dar_lance

    await garantir_demonstracao(recursos)
    usuarios = await seed._usuarios(recursos, seed.ResumoSeed())
    async with recursos.fabrica() as s, s.begin():
        disputado = await s.scalar(select(Lote.public_id).where(Lote.item_id_externo == "45434"))
        agendado = await s.scalar(select(Lote.public_id).where(Lote.item_id_externo == "459123"))
    await dar_lance(recursos, usuarios["comprador2"], disputado, 700000, secrets.token_hex(16))
    await cancelar_lote(recursos, usuarios["leiloeiro"], agendado)
    monkeypatch.setattr(seed, "LIMITE_SALDO_DEPOSITO", 1000100)
    monkeypatch.setattr(carteira, "LIMITE_SALDO_DEPOSITO", 1000100)
    original = seed.depositar
    valores = []

    async def depositar_com_concorrencia(recursos, usuario, valor, chave):
        valores.append(valor)
        if deposito_concorrente:
            await original(recursos, usuario, 100, secrets.token_hex(16))
        return await original(recursos, usuario, valor, chave)

    monkeypatch.setattr(seed, "depositar", depositar_com_concorrencia)
    resumo = await garantir_demonstracao(recursos)
    assert resumo.erro is None and resumo.lotes_criados == 1
    assert valores == [100]
    assert resumo.depositos == (0 if deposito_concorrente else 1)
    assert (
        await consultar_carteira(recursos, usuarios["comprador2"])
    ).saldo_total_centavos == 1000100
    if deposito_concorrente:
        assert "Depósito do seed recusado para comprador2: limite_saldo" in caplog.text
    seguinte = await garantir_demonstracao(recursos)
    assert seguinte.erro is None and seguinte.depositos == 0 and seguinte.lotes_criados == 0
    await conferir_reconciliacao(recursos)


@pytest.mark.parametrize("falha", ["bloqueio", "false"])
async def test_liberacao_com_falha_invalida_conexao(recursos, monkeypatch, caplog, falha):
    from sqlalchemy.ext.asyncio import AsyncConnection

    from app.demo import seed

    await garantir_demonstracao(recursos)
    original = AsyncConnection.scalar

    async def interceptar(conexao, instrucao, *args, **kwargs):
        if str(instrucao).startswith("SELECT pg_advisory_unlock"):
            if falha == "bloqueio":
                await anyio.sleep_forever()
            return False
        return await original(conexao, instrucao, *args, **kwargs)

    monkeypatch.setattr(seed, "PRAZO_LIBERAR_TRAVA", 0.05)
    monkeypatch.setattr(AsyncConnection, "scalar", interceptar)
    with anyio.fail_after(5):
        resumo = await garantir_demonstracao(recursos)
    assert resumo.erro == "falha_liberar_trava"
    assert "liberar a trava de demonstração" in caplog.text
    async with recursos.engine.connect() as conexao:
        assert await conexao.scalar(
            text(
                "SELECT NOT EXISTS (SELECT 1 FROM pg_locks "
                "WHERE locktype = 'advisory' AND classid = 0 AND objid = :id AND objsubid = 1)"
            ),
            {"id": TRAVA_DEMO},
        )
