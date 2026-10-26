from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core.erros import ApiExternaIndisponivel, Recusa
from app.integrations.met import CacheMetMemoria, MetCliente, RegistroCache
from tests.apoio import met_simulado

pytestmark = pytest.mark.anyio
BASE = "https://collectionapi.metmuseum.org/public/collection"


async def test_paginacao_filtra_e_cache():
    requisicoes = []

    def responder(request):
        requisicoes.append(request)
        if request.url.path.endswith("/21"):
            return httpx.Response(200, json={"isPublicDomain": False})
        return met_simulado(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        cliente = MetCliente(http, CacheMetMemoria(), BASE)
        pagina = await cliente.buscar("Obra", 2)
        assert [int(i.id_externo) for i in pagina.itens] == list(range(22, 41))
        assert pagina.total_ids == 50 and pagina.tem_mais and not pagina.parcial
        assert pagina.origem == "api"
        assert requisicoes[0].url.path.endswith("/v1.1/search")
        assert requisicoes[0].url.params["hasImages"] == "true"
        quantidade = len(requisicoes)
        assert (await cliente.buscar("Obra", 2)).origem == "cache"
        assert len(requisicoes) == quantidade


async def test_lista_nula():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"total": 0, "objectIDs": None})
        )
    ) as http:
        assert (await MetCliente(http, CacheMetMemoria(), BASE).buscar("nada")).itens == []


@pytest.mark.parametrize("falha", [429, 500, "timeout"])
@pytest.mark.parametrize("com_cache", [False, True])
async def test_falhas_busca(falha, com_cache):
    cache = CacheMetMemoria()
    if com_cache:
        cache.registros["busca:v1:obra"] = RegistroCache(
            {"ids": []}, datetime.now(UTC) - timedelta(days=2)
        )

    def responder(request):
        if falha == "timeout":
            raise httpx.ReadTimeout("simulado", request=request)
        return httpx.Response(falha)

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        cliente = MetCliente(http, cache, BASE)
        if com_cache:
            assert (await cliente.buscar("obra")).origem == "cache"
        else:
            with pytest.raises(ApiExternaIndisponivel):
                await cliente.buscar("obra")


async def test_404_parcial_e_cache_vencido():
    falhar = False

    def responder(request):
        if request.url.path.endswith("/1"):
            return httpx.Response(404)
        if request.url.path.endswith("/2") or falhar:
            return httpx.Response(500)
        return met_simulado(request)

    cache = CacheMetMemoria()
    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        cliente = MetCliente(http, cache, BASE)
        with pytest.raises(Recusa) as erro:
            await cliente.obter_item("1")
        assert erro.value.codigo == "item_nao_encontrado"
        assert (await cliente.buscar("obra")).parcial
        item = await cliente.obter_item("3")
        registro = cache.registros["objeto:v1:3"]
        cache.registros["objeto:v1:3"] = RegistroCache(
            registro.dados, datetime.now(UTC) - timedelta(days=2)
        )
        falhar = True
        assert await cliente.obter_item("3") == item


@pytest.mark.parametrize("operacao", ["buscar", "obter_item"])
@pytest.mark.parametrize("falha", [403, "timeout"])
async def test_falhas_registram_status_ou_classe_sem_query(caplog, operacao, falha):
    import secrets

    marcador = secrets.token_hex(12)

    def responder(request):
        if falha == "timeout":
            raise httpx.ReadTimeout(marcador, request=request)
        return httpx.Response(falha)

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        cliente = MetCliente(http, CacheMetMemoria(), BASE)
        with pytest.raises(ApiExternaIndisponivel):
            await getattr(cliente, operacao)(marcador if operacao == "buscar" else "123")
    registros = [r for r in caplog.records if r.name == "app.integrations.met"]
    assert len(registros) == 1 and registros[0].levelname == "WARNING"
    mensagem = registros[0].getMessage()
    assert ("status=403" if falha == 403 else "ReadTimeout") in mensagem
    assert BASE in mensagem and "?" not in mensagem and marcador not in mensagem
