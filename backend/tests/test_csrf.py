import httpx
import pytest
from fastapi import FastAPI

from app.core.seguranca import ProtecaoCSRF


@pytest.mark.anyio
@pytest.mark.parametrize(
    "metodo,headers,status",
    [
        ("POST", {}, 403),
        ("POST", {"Origin": "http://estranho"}, 403),
        ("POST", {"Origin": "null", "Referer": "http://test/pagina"}, 403),
        ("POST", {"Referer": "http://test/pagina"}, 200),
        ("POST", {"Origin": "http://test"}, 200),
        ("GET", {}, 200),
    ],
)
async def test_csrf(settings_teste, metodo, headers, status):
    app = FastAPI()
    app.add_middleware(ProtecaoCSRF, settings=settings_teste)

    @app.api_route("/api/eco", methods=["GET", "POST"])
    async def eco():
        return {"ok": True}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.request(metodo, "/api/eco", headers=headers)
    assert r.status_code == status
    if status == 403:
        assert r.json()["erro"]["codigo"] == "origem_invalida"
