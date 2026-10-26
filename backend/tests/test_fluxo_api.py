import secrets
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.main import create_app
from app.services.liquidacao import encerrar_lote
from tests.apoio import conferir_reconciliacao, envelhecer_lote

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


def conferir_privacidade(valor, usuarios):
    if isinstance(valor, dict):
        assert "cabeca_assinatura" not in valor
        for chave, dado in valor.items():
            assert not (chave.endswith("_id") and isinstance(dado, int))
            conferir_privacidade(dado, usuarios)
    elif isinstance(valor, list):
        for dado in valor:
            conferir_privacidade(dado, usuarios)
    elif isinstance(valor, str):
        for usuario in usuarios:
            assert usuario["nome"] not in valor
            assert usuario["email"] not in valor


async def test_fluxo_http_privacidade_notificacoes(recursos):
    app = create_app(recursos=recursos)
    usuarios = [
        {
            "nome": f"Nome privado {i}",
            "email": f"privado{i}@example.test",
            "senha": secrets.token_urlsafe(18),
            "papel": "leiloeiro" if i == 0 else "licitante",
        }
        for i in range(3)
    ]
    clientes = [
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": "http://test"},
        )
        for _ in usuarios
    ]
    dono, a, b = clientes
    try:
        for cliente, usuario in zip(clientes, usuarios, strict=True):
            assert (await cliente.post("/api/auth/cadastro", json=usuario)).status_code == 201
        for cliente in (a, b):
            r = await cliente.post(
                "/api/carteira/depositos",
                json={"valor_centavos": 1000},
                headers={"Idempotency-Key": "deposito-http"},
            )
            assert r.status_code == 201
        agora = datetime.now(UTC)
        entrada = {
            "item_id_externo": "123",
            "lance_inicial_centavos": 100,
            "incremento_centavos": 10,
            "inicio_em": (agora - timedelta(seconds=1)).isoformat(),
            "fim_em": (agora + timedelta(minutes=2)).isoformat(),
        }
        recursos.publicador.eventos.clear()
        r = await dono.post("/api/leiloeiro/lotes", json=entrada)
        assert r.status_code == 201, r.text
        lote_id = r.json()["id"]
        caminho = f"/api/lotes/{lote_id}"
        primeira = await a.post(
            caminho + "/lances",
            json={"valor_centavos": 100},
            headers={"Idempotency-Key": "lance-http-1"},
        )
        assert primeira.status_code == 201, primeira.text
        assert [e.tipo for e in recursos.publicador.eventos] == [
            "lote_publicado",
            "lote_atualizado",
            "carteira_atualizada",
        ]
        participacao = (await a.get(caminho)).json()["minha_participacao"]
        assert participacao["ganhando"] is True
        assert participacao["posicao"] == participacao["total_participantes"] == 1
        assert participacao["meu_maior_lance_centavos"] == 100
        cancelamento = await dono.post(f"/api/leiloeiro/lotes/{lote_id}/cancelar")
        assert cancelamento.status_code == 409
        assert cancelamento.json()["erro"]["codigo"] == "lote_com_lances"
        notificacoes_antes = len(recursos.publicador.eventos)
        recusa = await b.post(
            caminho + "/lances",
            json={"valor_centavos": 109},
            headers={"Idempotency-Key": "lance-http-2"},
        )
        assert recusa.status_code == 409 and recusa.json()["erro"]["codigo"] == "abaixo_do_minimo"
        sem_saldo = await b.post(
            caminho + "/lances",
            json={"valor_centavos": 1001},
            headers={"Idempotency-Key": "lance-sem-saldo"},
        )
        assert sem_saldo.status_code == 409
        assert sem_saldo.json()["erro"]["codigo"] == "saldo_insuficiente"
        assert sem_saldo.json()["erro"]["detalhes"] == {"disponivel_centavos": 1000}
        assert len(recursos.publicador.eventos) == notificacoes_antes
        assert (
            await b.post(
                caminho + "/lances",
                json={"valor_centavos": 110},
                headers={"Idempotency-Key": "lance-http-2"},
            )
        ).status_code == 201
        for cliente, posicao, valor, situacao in [(a, 2, 100, "superado"), (b, 1, 110, "ganhando")]:
            participacao = (await cliente.get(caminho)).json()["minha_participacao"]
            assert participacao["posicao"] == posicao
            assert participacao["total_participantes"] == 2
            assert participacao["ganhando"] is (posicao == 1)
            assert participacao["meu_maior_lance_centavos"] == valor
            assert (await cliente.get("/api/me/participacoes")).json()[0]["situacao"] == situacao
        repeticao = await a.post(
            caminho + "/lances",
            json={"valor_centavos": 100},
            headers={"Idempotency-Key": "lance-http-1"},
        )
        assert repeticao.json() == primeira.json()
        assert repeticao.headers["Idempotency-Replayed"] == "true"
        from uuid import UUID

        interno = await envelhecer_lote(recursos, UUID(lote_id))
        for cliente in (a, b):
            participacao = (await cliente.get("/api/me/participacoes")).json()[0]
            assert participacao["situacao"] == "aguardando_resultado"
            assert participacao["comprovante_codigo"] is None
        await encerrar_lote(recursos, interno)
        assert "lote_encerrado" in [e.tipo for e in recursos.publicador.eventos]
        participacoes = (await b.get("/api/me/participacoes")).json()
        assert participacoes[0]["situacao"] == "arrematado"
        perdeu = (await a.get("/api/me/participacoes")).json()[0]
        assert perdeu["situacao"] == "nao_arrematado" and perdeu["comprovante_codigo"] is None
        codigo = participacoes[0]["comprovante_codigo"]
        assert (await dono.get("/api/leiloeiro/lotes")).json()["total_recebido_centavos"] == 110
        assert (await b.get(caminho)).json()["resultado"]["comprovante_codigo"] == codigo
        assert (await a.get(caminho)).json()["resultado"]["comprovante_codigo"] is None
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as publico:
            for rota in [
                "/api/lotes",
                caminho,
                caminho + "/auditoria",
                f"/api/comprovantes/{codigo}",
            ]:
                resposta = await publico.get(rota)
                assert resposta.status_code == 200, resposta.text
                conferir_privacidade(resposta.json(), usuarios)
            assert (await publico.get(caminho + "/auditoria")).json()["veredito"] == "integro"
        # Cancelado fora da vitrine; agendado e ao vivo nos grupos corretos.
        agora = datetime.now(UTC)
        entrada.update(inicio_em=agora.isoformat(), fim_em=(agora + timedelta(hours=1)).isoformat())
        cancelado = (await dono.post("/api/leiloeiro/lotes", json=entrada)).json()["id"]
        assert (await dono.post(f"/api/leiloeiro/lotes/{cancelado}/cancelar")).status_code == 200
        vivo = (await dono.post("/api/leiloeiro/lotes", json=entrada)).json()["id"]
        entrada["inicio_em"] = (agora + timedelta(minutes=10)).isoformat()
        agendado = (await dono.post("/api/leiloeiro/lotes", json=entrada)).json()["id"]
        vitrine = (await a.get("/api/lotes")).json()
        assert vivo in [item["id"] for item in vitrine["ao_vivo"]]
        assert agendado in [item["id"] for item in vitrine["agendados"]]
        assert cancelado not in [
            item["id"]
            for grupo in ("ao_vivo", "agendados", "encerrados")
            for item in vitrine[grupo]
        ]
        assert (await a.get(f"/api/lotes/{cancelado}/auditoria")).json()["veredito"] == "integro"
        await conferir_reconciliacao(recursos)
    finally:
        for cliente in clientes:
            await cliente.aclose()


async def test_cancelamento_outro_dono_e_lote_ausente(cliente, recursos):
    from uuid import uuid4

    from tests.apoio import criar_lote, criar_usuario

    await criar_usuario(recursos, "leiloeiro", cliente=cliente)
    alheio = await criar_lote(recursos)
    for lote_id, status, codigo in [
        (alheio.id, 403, "lote_de_outro_leiloeiro"),
        (uuid4(), 404, "lote_nao_encontrado"),
    ]:
        resposta = await cliente.post(f"/api/leiloeiro/lotes/{lote_id}/cancelar")
        assert resposta.status_code == status
        assert resposta.json()["erro"]["codigo"] == codigo


async def test_item_inelegivel_pelas_rotas(cliente, recursos):
    from tests.apoio import criar_usuario

    await criar_usuario(recursos, "leiloeiro", cliente=cliente)
    await recursos.met.cache.guardar("objeto:v1:123", {"erro": "item_inelegivel"})
    agora = datetime.now(UTC)
    entrada = {
        "item_id_externo": "123",
        "lance_inicial_centavos": 100,
        "incremento_centavos": 10,
        "inicio_em": agora.isoformat(),
        "fim_em": (agora + timedelta(hours=1)).isoformat(),
    }
    for resposta in [
        await cliente.get("/api/leiloeiro/itens/123"),
        await cliente.post("/api/leiloeiro/lotes", json=entrada),
    ]:
        assert resposta.status_code == 422
        assert resposta.json()["erro"]["codigo"] == "item_inelegivel"


@pytest.mark.parametrize(
    "caso,codigo",
    [
        ("inicio_antigo", "datas_invalidas"),
        ("fim_passado", "datas_invalidas"),
        ("duracao_longa", "entrada_invalida"),
    ],
)
async def test_datas_recusadas_pela_rota_antes_do_met(cliente, recursos, monkeypatch, caso, codigo):
    from tests.apoio import criar_usuario

    await criar_usuario(recursos, "leiloeiro", cliente=cliente)

    async def nao_consultar(*args, **kwargs):
        pytest.fail("Datas inválidas não devem consultar o Met nem baixar imagem")

    monkeypatch.setattr(recursos.met, "obter_item", nao_consultar)
    monkeypatch.setattr("app.services.lotes.baixar_imagem", nao_consultar)
    agora = datetime.now(UTC)
    inicio, fim = {
        "inicio_antigo": (agora - timedelta(minutes=6), agora + timedelta(hours=1)),
        "fim_passado": (agora - timedelta(minutes=3), agora - timedelta(minutes=1)),
        "duracao_longa": (agora, agora + timedelta(days=31)),
    }[caso]
    resposta = await cliente.post(
        "/api/leiloeiro/lotes",
        json={
            "item_id_externo": "123",
            "lance_inicial_centavos": 100,
            "incremento_centavos": 10,
            "inicio_em": inicio.isoformat(),
            "fim_em": fim.isoformat(),
        },
    )
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == codigo


@pytest.mark.parametrize("operacao", ["criar_lote_do_met", "publicar_lote"])
@pytest.mark.parametrize("caso", ["inicio_antigo", "fim_passado", "duracao_longa"])
async def test_servicos_recusam_datas_sem_chamar_externos(recursos, monkeypatch, operacao, caso):
    import hashlib
    from types import SimpleNamespace

    from sqlalchemy import func, select

    from app.core.erros import Recusa
    from app.integrations.imagens import MidiaBaixada
    from app.models import EventoLote, Lote, Midia
    from app.schemas.itens import ItemExterno
    from app.services import lotes
    from tests.apoio import PNG, criar_usuario

    usuario = await criar_usuario(recursos, "leiloeiro")

    async def nao_consultar(*args, **kwargs):
        pytest.fail("Datas inválidas não devem consultar o Met nem baixar imagem")

    monkeypatch.setattr(recursos.met, "obter_item", nao_consultar)
    monkeypatch.setattr(lotes, "baixar_imagem", nao_consultar)
    async with recursos.fabrica() as s, s.begin():
        agora = await s.scalar(select(func.clock_timestamp()))
    inicio, fim = {
        "inicio_antigo": (agora - timedelta(minutes=6), agora + timedelta(hours=1)),
        "fim_passado": (agora - timedelta(minutes=3), agora - timedelta(minutes=1)),
        "duracao_longa": (agora, agora + timedelta(days=31)),
    }[caso]
    entrada = SimpleNamespace(
        item_id_externo="123",
        lance_inicial_centavos=100,
        incremento_centavos=10,
        inicio_em=inicio,
        fim_em=fim,
    )
    item = ItemExterno(
        id_externo="123",
        titulo="Obra",
        atributos={},
        imagem_url_externa="https://images.metmuseum.org/obra.png",
    )
    midia = MidiaBaixada(PNG, "image/png", hashlib.sha256(PNG).hexdigest())
    with pytest.raises(Recusa) as erro:
        if operacao == "criar_lote_do_met":
            await lotes.criar_lote_do_met(recursos, usuario, entrada)
        else:
            await lotes.publicar_lote(recursos, usuario, item, midia, entrada)
    assert erro.value.codigo == "datas_invalidas"
    async with recursos.fabrica() as s, s.begin():
        for tabela in (Lote, Midia, EventoLote):
            assert await s.scalar(select(func.count()).select_from(tabela)) == 0


@pytest.mark.parametrize("q,titulo", [("%", "Arte 100%"), ("_", "Arte_A")])
async def test_vitrine_escapa_curingas(cliente, recursos, q, titulo):
    from tests.apoio import criar_lote

    for nome in ["Arte 100%", "Arte 100X", "Arte_A", "ArteXA"]:
        await criar_lote(recursos, titulo=nome)
    resposta = await cliente.get("/api/lotes", params={"q": q})
    assert resposta.status_code == 200
    assert [lote["titulo"] for lote in resposta.json()["ao_vivo"]] == [titulo]
