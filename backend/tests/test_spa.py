import httpx
import pytest

from app.core.chaves import ConfiguracaoInvalida
from app.main import create_app


@pytest.fixture
def app_spa(tmp_path, settings_teste):
    (tmp_path / "index.html").write_text("<html>Casa de Leilões</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app-1a2b.js").write_text("console.log('app');")
    (tmp_path / "tema.js").write_text("console.log('tema');")
    settings_teste.frontend_dist = str(tmp_path)
    return create_app(settings_teste)


@pytest.mark.anyio
async def test_spa_respostas_e_cabecalhos(app_spa):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_spa), base_url="http://test"
    ) as cl:
        for caminho in (
            "/",
            "/lotes/0f8fad5b-d9cb-469f-a165-70867728950e",
            "/%2e%2e/%2e%2e/etc/passwd",
        ):
            resposta = await cl.get(caminho)
            assert resposta.status_code == 200
            assert "Casa de Leilões" in resposta.text
            assert resposta.headers["Cache-Control"] == "no-cache"
            assert resposta.headers["Referrer-Policy"] == "same-origin"
            assert resposta.headers["X-Content-Type-Options"] == "nosniff"
            assert resposta.headers["X-Frame-Options"] == "DENY"
            assert resposta.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
        asset = await cl.get("/assets/app-1a2b.js")
        assert asset.text == "console.log('app');"
        assert "javascript" in asset.headers["Content-Type"]
        assert "immutable" in asset.headers["Cache-Control"]
        assert (await cl.get("/tema.js")).headers["Cache-Control"] == "no-cache"
        head = await cl.head("/")
        assert head.content == b"" and int(head.headers["Content-Length"]) > 0
        for caminho in (
            "/assets/nao-existe.js",
            "/favicon.ico",
            "/api/nao-existe",
            "/ws",
            "/api",
            "/ws/x",
        ):
            resposta = await cl.get(caminho)
            assert resposta.status_code == 404
            assert resposta.json()["erro"]["codigo"] == "nao_encontrado"
        resposta = await cl.post("/api/health", headers={"Origin": "http://test"})
        assert resposta.status_code == 405 and "GET" in resposta.headers["Allow"]


@pytest.mark.anyio
async def test_sem_spa_e_diretorio_invalido(settings_teste, tmp_path):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(settings_teste)), base_url="http://test"
    ) as cl:
        assert (await cl.get("/")).json()["erro"]["codigo"] == "nao_encontrado"
    settings_teste.frontend_dist = str(tmp_path)
    with pytest.raises(ConfiguracaoInvalida):
        create_app(settings_teste)
