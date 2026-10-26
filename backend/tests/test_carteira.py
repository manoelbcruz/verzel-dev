import pytest
from sqlalchemy import insert, update

from app.core.config import LIMITE_SALDO_DEPOSITO
from app.core.erros import Recusa
from app.models import CarteiraRegistro, Lancamento
from app.services.carteira import depositar
from app.services.consultas import consultar_carteira
from app.services.lances import dar_lance
from tests.apoio import conferir_reconciliacao, criar_lote, criar_usuario

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


async def test_deposito_idempotencia_e_carteira(recursos):
    usuario = await criar_usuario(recursos)
    primeira = await depositar(recursos, usuario, 1000, "deposito-01")
    segunda = await depositar(recursos, usuario, 1000, "deposito-01")
    assert primeira.resposta == segunda.resposta
    assert not primeira.repetida and segunda.repetida
    with pytest.raises(Recusa) as erro:
        await depositar(recursos, usuario, 1001, "deposito-01")
    assert erro.value.codigo == "chave_idempotencia_conflito"
    lote = await criar_lote(recursos)
    await dar_lance(recursos, usuario, lote.id, 100, "reserva-carteira")
    carteira = await consultar_carteira(recursos, usuario)
    assert carteira.saldo_total_centavos == 1000
    assert carteira.disponivel_centavos == 900 and carteira.comprometido_centavos == 100
    assert len(carteira.lancamentos) == 1
    assert carteira.reservas[0].lote_id == lote.id
    await conferir_reconciliacao(recursos)


async def test_limite_deposito(recursos):
    usuario = await criar_usuario(recursos)
    async with recursos.fabrica() as s, s.begin():
        await s.execute(
            update(CarteiraRegistro)
            .where(CarteiraRegistro.usuario_id == usuario.id)
            .values(saldo_centavos=LIMITE_SALDO_DEPOSITO)
        )
        await s.execute(
            insert(Lancamento).values(
                usuario_id=usuario.id, tipo="deposito", valor_centavos=LIMITE_SALDO_DEPOSITO
            )
        )
    with pytest.raises(Recusa) as erro:
        await depositar(recursos, usuario, 1, "excede-limite")
    assert erro.value.codigo == "limite_saldo"
    await conferir_reconciliacao(recursos)
