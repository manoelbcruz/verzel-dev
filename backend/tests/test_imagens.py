import hashlib

import httpx
import pytest

from app.core.erros import Recusa
from app.integrations.imagens import baixar_imagem
from tests.apoio import PNG

pytestmark = pytest.mark.anyio
URL = "https://images.metmuseum.org/imagem.png"


@pytest.mark.parametrize(
    "url",
    [
        "https://outro.test/a",
        "http://images.metmuseum.org/a",
        "https://usuario@images.metmuseum.org/a",
    ],
)
async def test_url_recusada_sem_requisicao(url):
    def responder(request):
        pytest.fail("Não deve requisitar URL recusada")

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        with pytest.raises(Recusa):
            await baixar_imagem(http, url, 100)


@pytest.mark.parametrize(
    "status,tipo,dados,cabecalhos",
    [
        (302, "image/png", PNG, {"Location": URL}),
        (200, "text/html", PNG, {}),
        (200, "image/jpeg", PNG, {}),
        (200, "image/png", PNG, {"Content-Length": "500"}),
    ],
)
async def test_download_invalido(status, tipo, dados, cabecalhos):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                status, content=dados, headers={"Content-Type": tipo, **cabecalhos}
            )
        )
    ) as http:
        with pytest.raises(Recusa) as erro:
            await baixar_imagem(http, URL, 100)
        assert erro.value.codigo == "imagem_indisponivel"


async def test_limite_streaming():
    class Fluxo(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield PNG
            yield b"x" * 100

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, stream=Fluxo(), headers={"Content-Type": "image/png"})
        )
    ) as http:
        with pytest.raises(Recusa):
            await baixar_imagem(http, URL, 100)


async def test_sucesso():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=PNG, headers={"Content-Type": "image/png"})
        )
    ) as http:
        midia = await baixar_imagem(http, URL, 100)
        assert midia.sha256 == hashlib.sha256(PNG).hexdigest()
        assert midia.dados == PNG


@pytest.mark.parametrize("falha", [403, "timeout"])
async def test_log_download_sem_query_nem_fragmento(caplog, falha):
    import secrets

    marcador = secrets.token_hex(12)
    url = f"{URL}?parametro={marcador}#{marcador}"

    def responder(request):
        if falha == "timeout":
            raise httpx.ReadTimeout(marcador, request=request)
        return httpx.Response(falha)

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        with pytest.raises(Recusa):
            await baixar_imagem(http, url, 100)
    registros = [r for r in caplog.records if r.name == "app.integrations.imagens"]
    assert len(registros) == 1 and registros[0].levelname == "WARNING"
    mensagem = registros[0].getMessage()
    assert ("status=403" if falha == 403 else "ReadTimeout") in mensagem
    assert URL in mensagem and marcador not in mensagem
    assert "?" not in mensagem and "#" not in mensagem


async def test_log_url_recusada_sem_credenciais(caplog):
    import secrets

    marcador = secrets.token_hex(12)
    url = f"https://{marcador}@images.metmuseum.org/imagem.png"

    def responder(request):
        pytest.fail("Não deve requisitar URL com credencial")

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as http:
        with pytest.raises(Recusa):
            await baixar_imagem(http, url, 100)
    assert "Falha no download" in caplog.text
    assert marcador not in caplog.text
