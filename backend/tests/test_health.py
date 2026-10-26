import httpx
import pytest

from app.main import create_app


@pytest.mark.anyio
async def test_health(settings_teste) -> None:
    app = create_app(settings_teste, iniciar_worker=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        response = await c.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_recursos_sem_conectar_banco(settings_teste):
    from app.recursos import abrir_recursos

    async with abrir_recursos(settings_teste, iniciar_worker=False) as recursos:
        app = create_app(recursos=recursos)
        async with app.router.lifespan_context(app):
            assert app.state.recursos is recursos
            assert recursos.engine.pool.checkedout() == 0
            assert recursos.engine.sync_engine.hide_parameters is True
        assert not recursos.http.is_closed
    assert recursos.http.is_closed


@pytest.mark.anyio
async def test_http_405_preserva_allow(settings_teste):
    app = create_app(settings_teste, iniciar_worker=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as cliente:
        resposta = await cliente.post("/api/health")
    assert resposta.status_code == 405
    assert "GET" in resposta.headers["Allow"]
    assert resposta.json()["erro"]["codigo"] == "metodo_nao_permitido"


@pytest.mark.anyio
@pytest.mark.parametrize("status,codigo", [(418, "entrada_invalida"), (503, "erro_interno")])
async def test_http_exception_mapeamento_e_headers(settings_teste, status, codigo):
    from starlette.exceptions import HTTPException

    app = create_app(settings_teste, iniciar_worker=False)

    @app.get("/teste-http-exception")
    async def falhar():
        raise HTTPException(status, headers={"Retry-After": "3"})

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as cliente:
        resposta = await cliente.get("/teste-http-exception")
    assert resposta.status_code == status
    assert resposta.headers["Retry-After"] == "3"
    assert resposta.json()["erro"]["codigo"] == codigo
