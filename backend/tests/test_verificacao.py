from datetime import timedelta

import pytest

from app.services.cadeia import pseudonimo
from app.services.verificacao import verificar
from tests.apoio import AGORA, anexar_memoria, dados_com_lances, dados_publicados, reassinar


@pytest.mark.parametrize("estado", ["publicado", "lances", "arrematado", "sem_lances", "cancelado"])
def test_integros(chaves, estado):
    dados = (
        dados_com_lances(chaves, estado == "arrematado")
        if estado in {"lances", "arrematado"}
        else dados_publicados(chaves)
    )
    if estado == "sem_lances":
        anexar_memoria(dados, chaves, "encerramento", dados.lote["fim_em"])
    elif estado == "cancelado":
        anexar_memoria(dados, chaves, "cancelamento", AGORA)
    veredito = verificar(dados, chaves)
    assert veredito.integro, veredito
    assert veredito.eventos_verificados == len(dados.eventos)


@pytest.mark.parametrize(
    "mutacao,codigo",
    [
        ("valor", "mac_invalido"),
        ("licitante", "pseudonimo_divergente"),
        ("pseudonimo", "pseudonimo_divergente"),
        ("meio", "sequencia_quebrada"),
        ("ultimo", "cabeca_invalida"),
        ("cabeca_falsa", "cabeca_invalida"),
        ("insercao", "mac_invalido"),
        ("projecao", "projecao_divergente"),
        ("reserva", "reserva_divergente"),
        ("midia", "midia_divergente"),
        ("titulo", "mac_invalido"),
        ("atributos", "mac_invalido"),
    ],
)
def test_adulteracoes(chaves, mutacao, codigo):
    dados = dados_com_lances(chaves)
    match mutacao:
        case "valor":
            dados.eventos[1]["valor_centavos"] += 1
        case "licitante":
            dados.eventos[1]["licitante_id"] = 4
        case "pseudonimo":
            dados.eventos[1]["pseudonimo"] = "adulterado"
        case "meio":
            del dados.eventos[1]
        case "ultimo" | "cabeca_falsa":
            dados.eventos.pop()
            if mutacao == "cabeca_falsa":
                dados.lote["cabeca_seq"] -= 1
                dados.lote["cabeca_assinatura"] = dados.eventos[-1]["mac"]
        case "insercao":
            dados.eventos.append(dados.eventos[-1] | {"seq": 4, "mac": bytes(32)})
        case "projecao":
            dados.lote["lance_atual_centavos"] = 101
        case "reserva":
            dados.reserva["valor_centavos"] += 1
        case "midia":
            dados.midia_sha256_calculado = "0" * 64
        case "titulo":
            dados.lote["titulo"] = "Outra obra"
        case "atributos":
            dados.lote["atributos"]["artista"] = "Outra pessoa"
    veredito = verificar(dados, chaves)
    assert veredito.falha.codigo == codigo
    if mutacao == "meio":
        assert veredito.eventos_verificados == 1
        assert veredito.falha.seq == 2


@pytest.mark.parametrize(
    "mutacao,codigo",
    [
        ("valor", "mac_invalido"),
        ("vencedor", "mac_invalido"),
        ("ausente", "liquidacao_divergente"),
        ("lancamento", "liquidacao_divergente"),
        ("pseudonimo", "liquidacao_divergente"),
        ("fim", "projecao_divergente"),
        ("apos_terminal", "gramatica_invalida"),
    ],
)
def test_liquidacao_adulterada(chaves, mutacao, codigo):
    dados = dados_com_lances(chaves, encerrar=True)
    match mutacao:
        case "valor":
            dados.liquidacao["valor_centavos"] += 1
        case "vencedor":
            dados.liquidacao["vencedor_id"] = 2
        case "ausente":
            dados.liquidacao = None
        case "lancamento":
            dados.lancamentos.pop()
        case "pseudonimo":
            dados.liquidacao["vencedor_pseudonimo"] = "outro"
        case "fim":
            dados.lote["fim_em"] += timedelta(seconds=1)
        case "apos_terminal":
            anexar_memoria(dados, chaves, "lance", dados.lote["fim_em"], usuario=4, valor=120)
    assert verificar(dados, chaves).falha.codigo == codigo


@pytest.mark.parametrize(
    "mutacao",
    [
        "minimo",
        "mesmo",
        "fim_anterior",
        "fim_novo",
        "antes",
        "depois",
        "instante_decresce",
        "lavagem",
    ],
)
def test_transicoes_com_mac_valido(chaves, mutacao):
    dados = dados_com_lances(chaves)
    evento = dados.eventos[-1]
    match mutacao:
        case "minimo" | "lavagem":
            evento["valor_centavos"] = 109 if mutacao == "minimo" else 90
            dados.lote["lance_atual_centavos"] = evento["valor_centavos"]
            dados.reserva["valor_centavos"] = evento["valor_centavos"]
        case "mesmo":
            evento["licitante_id"] = 2
            evento["pseudonimo"] = pseudonimo(chaves.privacidade, dados.lote["public_id"], 2)
        case "fim_anterior":
            evento["fim_anterior"] += timedelta(seconds=1)
        case "fim_novo":
            evento["fim_novo"] += timedelta(seconds=1)
        case "antes":
            evento["instante"] = AGORA - timedelta(seconds=1)
        case "depois":
            evento["instante"] = evento["fim_anterior"]
        case "instante_decresce":
            evento["instante"] = AGORA + timedelta(seconds=5)
    reassinar(dados, chaves)
    assert verificar(dados, chaves).falha.codigo == "transicao_invalida"


def test_cancelamento_com_lance(chaves):
    dados = dados_com_lances(chaves)
    anexar_memoria(dados, chaves, "cancelamento", AGORA + timedelta(seconds=30))
    assert verificar(dados, chaves).falha.codigo == "gramatica_invalida"


def test_primeiro_lance_abaixo_do_inicial_assinado(chaves):
    dados = dados_publicados(chaves)
    anexar_memoria(dados, chaves, "lance", AGORA, valor=99)
    assert verificar(dados, chaves).falha.codigo == "transicao_invalida"


def test_encerramento_antes_do_fim_assinado(chaves):
    dados = dados_com_lances(chaves)
    anexar_memoria(dados, chaves, "encerramento", dados.lote["fim_em"] - timedelta(seconds=1))
    assert verificar(dados, chaves).falha.codigo == "transicao_invalida"


def test_lance_do_dono_com_mac_valido(chaves):
    dados = dados_publicados(chaves)
    anexar_memoria(dados, chaves, "lance", AGORA, usuario=dados.lote["leiloeiro_id"])
    falha = verificar(dados, chaves).falha
    assert falha.codigo == "transicao_invalida" and falha.seq == 2
