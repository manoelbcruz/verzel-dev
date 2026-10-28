import hashlib
import json
import re
import secrets
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import anyio
import httpx
import pytest
from pydantic import SecretStr

from app.core.config import SENHA_DEMO_PUBLICA
from app.core.erros import MENSAGENS
from app.demo.catalogo import (
    CATALOGO,
    DADOS,
    Criar,
    DarLances,
    LoteExistente,
    carregar_item,
    deposito_necessario,
    planejar,
)
from app.main import create_app
from app.recursos import abrir_recursos


@pytest.mark.anyio
async def test_demo_so_mostra_contas_conferidas(settings_teste):
    contas = [
        {"email": "leiloeiro@demo.example", "rotulo": "leiloeiro", "papel": "leiloeiro"},
        {"email": "comprador1@demo.example", "rotulo": "comprador 1", "papel": "licitante"},
        {"email": "comprador2@demo.example", "rotulo": "comprador 2", "papel": "licitante"},
    ]
    recursos = SimpleNamespace(settings=settings_teste, contas_demo=contas)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(recursos=recursos)), base_url="http://test"
    ) as cl:
        assert (await cl.get("/api/demo")).status_code == 404
        settings_teste.seed_demo = True
        resposta = (await cl.get("/api/demo")).json()
        assert resposta == {"contas": contas, "senha": SENHA_DEMO_PUBLICA}
        settings_teste.senha_demo = SecretStr(secrets.token_urlsafe(18))
        assert (await cl.get("/api/demo")).json()["senha"] is None
        recursos.contas_demo = []
        resposta = await cl.get("/api/demo")
        assert resposta.status_code == 404 and resposta.json()["erro"]["codigo"] == "nao_encontrado"


def test_catalogo_local_valido_e_lances_ordenados():
    for papel in CATALOGO:
        item, midia = carregar_item(papel)
        assert item.id_externo == str(papel.item_id)
        assert midia.dados.startswith(b"\xff\xd8\xff") and len(midia.dados) <= 5_000_000
        assert midia.sha256 == hashlib.sha256(midia.dados).hexdigest()
        bruto = json.loads((DADOS / f"met-{papel.item_id}.json").read_text())
        assert item.imagem_url_externa == bruto["primaryImageSmall"]
        minimo, anterior = papel.lance_inicial_centavos, None
        for usuario, valor in papel.lances:
            assert valor >= minimo and usuario != anterior
            minimo, anterior = valor + papel.incremento_centavos, usuario


AGORA = datetime(2026, 10, 27, tzinfo=UTC)


def test_mensagens_do_front_cobrem_codigos_do_backend():
    arquivo = Path(__file__).parents[2] / "frontend/src/lib/erros.ts"
    codigo = arquivo.read_text(encoding="utf-8").split("export type ContextoErro")[0]
    for nome in MENSAGENS:
        assert re.search(rf"\b{nome}\s*:", codigo), nome


def satisfeitos():
    return {
        papel.item_id: [
            LoteExistente(
                uuid4(),
                "encerrado" if papel.papel == "encerrado" else "publicado",
                AGORA + timedelta(days=2)
                if papel.papel == "agendado"
                else AGORA - timedelta(minutes=1),
                AGORA + timedelta(days=14),
                len(papel.lances),
                "arrematado" if papel.papel == "encerrado" else None,
            )
        ]
        for papel in CATALOGO
    }


def test_planejador_vazio_e_satisfeito():
    assert planejar({}, AGORA) == [
        Criar(0),
        DarLances(0, None),
        Criar(1),
        DarLances(1, None),
        Criar(2),
        DarLances(2, None),
        Criar(3),
    ]
    assert planejar(satisfeitos(), AGORA) == []


@pytest.mark.parametrize(
    "indice,alteracoes,cria,lances",
    [
        (0, {"fim_em": AGORA + timedelta(hours=23)}, True, True),
        (0, {"total_lances": 0}, False, True),
        (0, {"total_lances": 1}, False, True),
        (0, {"total_lances": 2}, False, True),
        (3, {"inicio_em": AGORA - timedelta(seconds=1)}, True, False),
        (2, {"resultado": "sem_lances", "total_lances": 0}, True, True),
        (
            2,
            {"resultado": None, "status": "publicado", "fim_em": AGORA - timedelta(seconds=1)},
            False,
            False,
        ),
        (2, {"resultado": None, "status": "publicado", "total_lances": 1}, False, True),
        (2, {"resultado": None, "status": "publicado", "total_lances": 0}, False, True),
        (0, {"status": "cancelado"}, True, True),
    ],
)
def test_planejador_progresso_e_reposicao(indice, alteracoes, cria, lances):
    existentes = satisfeitos()
    item = CATALOGO[indice].item_id
    lote = replace(existentes[item][0], **alteracoes)
    existentes[item] = [lote]
    esperado = [Criar(indice)] if cria else []
    if lances:
        esperado.append(DarLances(indice, None if cria else lote.public_id))
    assert planejar(existentes, AGORA) == esperado


@pytest.mark.parametrize(
    "saldo,comprometido,esperado",
    [(500000, 0, 0), (499999, 0, 500001), (0, 0, 1000000), (600000, 100001, 500001)],
)
def test_deposito_necessario(saldo, comprometido, esperado):
    assert deposito_necessario(saldo, comprometido) == esperado


@pytest.mark.anyio
@pytest.mark.parametrize("ligado", [False, True])
async def test_seed_no_lifespan_so_com_flag(settings_teste, monkeypatch, ligado):
    chamadas = []
    iniciou = anyio.Event()

    async def garantir(recursos):
        chamadas.append("seed")

    async def laco(recursos):
        chamadas.append("laco")
        iniciou.set()
        await anyio.sleep_forever()

    monkeypatch.setattr("app.demo.seed.garantir_demonstracao", garantir)
    monkeypatch.setattr("app.demo.seed.laco_demonstracao", laco)
    settings_teste.seed_demo = ligado
    async with abrir_recursos(settings_teste, iniciar_worker=False):
        if ligado:
            with anyio.fail_after(2):
                await iniciou.wait()
    assert chamadas == (["seed", "laco"] if ligado else [])


@pytest.mark.parametrize("tamanho", [7, 129])
def test_senha_demo_invalida_nao_aparece_no_erro(tamanho):
    from pydantic import ValidationError

    from app.core.config import Settings

    senha = secrets.token_hex(65)[:tamanho]
    with pytest.raises(ValidationError) as erro:
        Settings(_env_file=None, senha_demo=senha)
    assert "SENHA_DEMO deve ter entre 8 e 128 caracteres" in str(erro.value)
    assert senha not in str(erro.value)
