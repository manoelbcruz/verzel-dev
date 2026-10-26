from datetime import timedelta

import pytest

from app.core.erros import ErroIntegridade
from app.services.verificacao import conferir_ponta
from tests.apoio import dados_com_lances, dados_publicados


@pytest.mark.parametrize("com_lances", [False, True])
def test_ponta_integra(chaves, com_lances):
    dados = dados_com_lances(chaves) if com_lances else dados_publicados(chaves)
    conferir_ponta(dados, chaves)


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("cabeca_assinatura", bytes(32)),
        ("cabeca_seq", 20),
        ("lance_atual_centavos", 105),
        ("lider_id", 4),
        ("total_lances", 8),
        ("fim_em", None),
        ("reserva", None),
    ],
)
def test_ponta_adulterada(chaves, campo, valor):
    dados = dados_com_lances(chaves)
    if campo == "reserva":
        dados.reserva["valor_centavos"] += 1
    elif campo == "fim_em":
        dados.lote[campo] += timedelta(seconds=1)
    else:
        dados.lote[campo] = valor
    with pytest.raises(ErroIntegridade):
        conferir_ponta(dados, chaves)


def test_snapshot_adulterado_depois_de_lance(chaves):
    dados = dados_com_lances(chaves)
    dados.lote.update(titulo="Adulterado", incremento_centavos=1)
    with pytest.raises(ErroIntegridade) as erro:
        conferir_ponta(dados, chaves)
    assert erro.value.detalhes == {"falha": "mac_invalido", "seq": 1}


def test_lavagem_consistente_da_ponta(chaves):
    from tests.apoio import AGORA, anexar_memoria

    dados = dados_publicados(chaves)
    anexar_memoria(dados, chaves, "lance", AGORA, usuario=2, valor=100)
    anexar_memoria(dados, chaves, "lance", AGORA, usuario=3, valor=500)
    dados.eventos[-1]["valor_centavos"] = 110
    dados.lote["lance_atual_centavos"] = 110
    dados.reserva["valor_centavos"] = 110
    with pytest.raises(ErroIntegridade) as erro:
        conferir_ponta(dados, chaves)
    assert erro.value.detalhes == {"falha": "mac_invalido", "seq": 3}


def test_evento_depois_da_cabeca(chaves):
    dados = dados_com_lances(chaves)
    dados.eventos.append(dados.eventos[-1] | {"seq": 4, "mac": bytes(32)})
    with pytest.raises(ErroIntegridade) as erro:
        conferir_ponta(dados, chaves)
    assert erro.value.detalhes["falha"] == "cabeca_invalida"


def test_evento_intermediario_adulterado_com_ponta_preservada(chaves):
    dados = dados_com_lances(chaves)
    dados.eventos[1]["valor_centavos"] = 99
    with pytest.raises(ErroIntegridade) as erro:
        conferir_ponta(dados, chaves)
    assert erro.value.detalhes == {"falha": "mac_invalido", "seq": 2}
