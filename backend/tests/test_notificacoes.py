import pytest
from sqlalchemy import func, select

from app.models import CarteiraRegistro, ChaveIdempotencia, EventoLote, Lancamento, Lote, Reserva
from app.services.carteira import depositar
from app.services.lances import dar_lance
from app.services.notificacoes import EventoDominio, publicar_depois_do_commit
from tests.apoio import conferir_reconciliacao, criar_lote, criar_usuario


def test_falha_publicacao_nao_muda_sucesso(caplog):
    class PublicadorFalho:
        def publicar(self, evento):
            raise RuntimeError("falha simulada")

    def comando():
        resposta = {"aceito": True}
        publicar_depois_do_commit(PublicadorFalho(), [EventoDominio("lote_publicado")])
        return resposta

    assert comando() == {"aceito": True}
    assert "Falha na notificação pós-commit" in caplog.text


@pytest.mark.pg
@pytest.mark.anyio
async def test_publicador_falho_nao_desfaz_deposito_nem_lance(recursos, caplog):
    usuario = await criar_usuario(recursos)
    lote = await criar_lote(recursos)

    class PublicadorFalho:
        def publicar(self, evento):
            raise RuntimeError("falha simulada")

    recursos.publicador = PublicadorFalho()
    deposito = await depositar(recursos, usuario, 1000, "deposito-publicador")
    lance = await dar_lance(recursos, usuario, lote.id, 100, "lance-publicador")
    assert deposito.status_http == lance.status_http == 201
    assert not deposito.repetida and not lance.repetida
    async with recursos.fabrica() as s, s.begin():
        assert (
            await s.scalar(
                select(CarteiraRegistro.saldo_centavos).where(
                    CarteiraRegistro.usuario_id == usuario.id
                )
            )
            == 1000
        )
        assert await s.scalar(select(func.count()).select_from(Lancamento)) == 1
        assert await s.scalar(select(func.count()).select_from(ChaveIdempotencia)) == 2
        assert await s.scalar(select(Lote.lider_id).where(Lote.public_id == lote.id)) == usuario.id
        assert await s.scalar(select(Reserva.valor_centavos)) == 100
        assert (
            await s.scalar(
                select(func.count()).select_from(EventoLote).where(EventoLote.tipo == "lance")
            )
            == 1
        )
    assert "Falha na notificação pós-commit" in caplog.text
    await conferir_reconciliacao(recursos)
