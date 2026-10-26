import pytest
from sqlalchemy.exc import DBAPIError

from app.core.erros import Recusa
from app.db.transacao import executar_comando


class FalhaBanco(Exception):
    def __init__(self, sqlstate):
        self.sqlstate = sqlstate


@pytest.mark.anyio
async def test_reexecuta_transacao():
    chamadas = []

    async def comando():
        chamadas.append(1)
        if len(chamadas) < 3:
            raise DBAPIError(None, None, FalhaBanco(["40P01", "55P03"][len(chamadas) - 1]))
        return "aceito"

    assert await executar_comando(comando) == "aceito"
    assert len(chamadas) == 3


@pytest.mark.anyio
@pytest.mark.parametrize(
    "estado,codigo,quantidade",
    [
        ("40P01", "servico_ocupado", 3),
        (None, "saldo_insuficiente", 1),
    ],
)
async def test_limite_e_recusa(estado, codigo, quantidade):
    chamadas = []

    async def comando():
        chamadas.append(1)
        if estado:
            raise DBAPIError(None, None, FalhaBanco(estado))
        raise Recusa("saldo_insuficiente")

    with pytest.raises(Recusa) as erro:
        await executar_comando(comando)
    assert erro.value.codigo == codigo
    assert len(chamadas) == quantidade


@pytest.mark.anyio
async def test_resultado_desconhecido_nao_reexecuta():
    chamadas = []

    async def comando():
        chamadas.append(1)
        raise DBAPIError(None, None, FalhaBanco("08006"))

    with pytest.raises(DBAPIError):
        await executar_comando(comando)
    assert len(chamadas) == 1
