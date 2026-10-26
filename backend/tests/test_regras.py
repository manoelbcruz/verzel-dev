from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.core.erros import Recusa
from app.services.regras import avaliar_lance, calcular_fase, validar_datas
from tests.apoio import AGORA, dados_publicados


@pytest.mark.parametrize(
    "mudancas,valor,saldo,comprometido,codigo,detalhes",
    [
        ({"status": "cancelado", "fim_em": AGORA}, 0, 0, 0, "lote_cancelado", {}),
        (
            {"fim_em": AGORA, "inicio_em": AGORA + timedelta(seconds=1)},
            0,
            0,
            0,
            "lote_encerrado",
            {},
        ),
        (
            {"inicio_em": AGORA + timedelta(seconds=1), "lider_id": 2},
            0,
            0,
            0,
            "lote_nao_iniciado",
            {},
        ),
        ({"lider_id": 2}, 0, 0, 0, "ja_esta_ganhando", {}),
        ({}, 99, 0, 0, "abaixo_do_minimo", {"minimo_centavos": 100}),
        (
            {"lider_id": 3, "lance_atual_centavos": 100},
            109,
            0,
            0,
            "abaixo_do_minimo",
            {"minimo_centavos": 110},
        ),
        ({}, 101, 130, 30, "saldo_insuficiente", {"disponivel_centavos": 100}),
    ],
)
def test_recusas_precedencia(chaves, mudancas, valor, saldo, comprometido, codigo, detalhes):
    estado = dados_publicados(chaves).lote | mudancas
    with pytest.raises(Recusa) as erro:
        avaliar_lance(estado, 2, valor, saldo, comprometido, AGORA)
    assert erro.value.codigo == codigo
    assert erro.value.detalhes == detalhes


@pytest.mark.parametrize("segundos,prorrogou", [(121, False), (120, False), (30, True)])
@pytest.mark.parametrize("lider,atual,valor", [(None, None, 100), (3, 100, 110)])
def test_aceite_limites(chaves, segundos, prorrogou, lider, atual, valor):
    estado = dados_publicados(chaves).lote | {
        "fim_em": AGORA + timedelta(seconds=segundos),
        "lider_id": lider,
        "lance_atual_centavos": atual,
    }
    decisao = avaliar_lance(estado, 2, valor, valor + 30, 30, AGORA)
    assert decisao.prorrogou is prorrogou
    assert decisao.fim_novo == AGORA + timedelta(seconds=max(120, segundos))
    assert decisao.fim_novo >= estado["fim_em"]


@pytest.mark.parametrize(
    "status,inicio,fim,fase",
    [
        ("cancelado", -1, 1, "cancelado"),
        ("encerrado", -1, 1, "encerrado"),
        ("publicado", -1, 0, "encerrado"),
        ("publicado", 0, 1, "ao_vivo"),
        ("publicado", 1, 2, "agendado"),
    ],
)
def test_fases(status, inicio, fim, fase):
    assert (
        calcular_fase(
            status, AGORA + timedelta(seconds=inicio), AGORA + timedelta(seconds=fim), AGORA
        )
        == fase
    )


def test_dono_nao_pode_dar_lance(chaves):
    estado = dados_publicados(chaves).lote
    with pytest.raises(Recusa) as erro:
        avaliar_lance(estado, estado["leiloeiro_id"], 100, 1000, 0, AGORA)
    assert erro.value.codigo == "papel_nao_permitido"


@pytest.mark.parametrize(
    "inicio,fim",
    [
        (AGORA - timedelta(minutes=5, microseconds=1), AGORA + timedelta(hours=1)),
        (AGORA - timedelta(minutes=2), AGORA - timedelta(minutes=1)),
        (AGORA, AGORA + timedelta(days=30, microseconds=1)),
    ],
)
def test_datas_invalidas(inicio, fim):
    with pytest.raises(Recusa) as erro:
        validar_datas(SimpleNamespace(inicio_em=inicio, fim_em=fim), AGORA)
    assert erro.value.codigo == "datas_invalidas"


def test_limites_de_datas_aceitos():
    validar_datas(
        SimpleNamespace(inicio_em=AGORA - timedelta(minutes=5), fim_em=AGORA + timedelta(hours=1)),
        AGORA,
    )
    validar_datas(SimpleNamespace(inicio_em=AGORA, fim_em=AGORA + timedelta(days=30)), AGORA)
