import secrets

import pytest
from sqlalchemy import func, update

from app.models import Sessao

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


async def test_cadastro_login_me_logout(cliente, recursos):
    senha = secrets.token_urlsafe(18)
    entrada = {
        "nome": "Pessoa",
        "email": "PESSOA@example.test",
        "senha": senha,
        "papel": "licitante",
    }
    r = await cliente.post("/api/auth/cadastro", json=entrada)
    assert r.status_code == 201
    cookie = r.headers["set-cookie"]
    assert all(
        parte in cookie for parte in ["HttpOnly", "SameSite=lax", "Path=/", "Max-Age=604800"]
    )
    assert "Secure" not in cookie
    assert r.json() == {"nome": "Pessoa", "email": "pessoa@example.test", "papel": "licitante"}
    duplicado = await cliente.post("/api/auth/cadastro", json=entrada)
    assert duplicado.status_code == 409
    assert duplicado.json()["erro"]["codigo"] == "email_em_uso"
    assert (await cliente.get("/api/auth/me")).status_code == 200
    antigo = cliente.cookies.get("sessao")
    assert (await cliente.post("/api/auth/logout")).status_code == 204
    cliente.cookies.set("sessao", antigo)
    assert (await cliente.get("/api/auth/me")).status_code == 401
    cliente.cookies.clear()
    for email in [entrada["email"], "ausente@example.test"]:
        resposta = await cliente.post(
            "/api/auth/login", json={"email": email, "senha": secrets.token_urlsafe(18)}
        )
        assert resposta.status_code == 401
        assert resposta.json()["erro"]["codigo"] == "credenciais_invalidas"
    assert (
        await cliente.post("/api/auth/login", json={"email": entrada["email"], "senha": senha})
    ).status_code == 200
    async with recursos.fabrica() as s, s.begin():
        await s.execute(update(Sessao).values(expira_em=func.now()))
    assert (await cliente.get("/api/auth/me")).status_code == 401
    assert (await cliente.post("/api/auth/logout")).status_code == 204


async def test_cookie_secure_producao(cliente, recursos):
    recursos.settings.environment = "production"
    resposta = await cliente.post(
        "/api/auth/cadastro",
        json={
            "nome": "Pessoa",
            "email": "pessoa@example.test",
            "senha": secrets.token_urlsafe(18),
            "papel": "licitante",
        },
    )
    assert "Secure" in resposta.headers["set-cookie"]


async def test_papeis(cliente):
    for papel, rotas in [
        ("licitante", ["/api/leiloeiro/lotes", "/api/leiloeiro/itens?q=arte"]),
        ("leiloeiro", ["/api/me/participacoes"]),
    ]:
        cliente.cookies.clear()
        await cliente.post(
            "/api/auth/cadastro",
            json={
                "nome": papel,
                "email": f"{papel}@example.test",
                "senha": secrets.token_urlsafe(18),
                "papel": papel,
            },
        )
        for rota in rotas:
            assert (await cliente.get(rota)).status_code == 403
        if papel == "leiloeiro":
            for rota in [
                "/api/carteira/depositos",
                "/api/lotes/11111111-aaaa-4000-8000-111111111111/lances",
            ]:
                r = await cliente.post(
                    rota, json={"valor_centavos": 100}, headers={"Idempotency-Key": "chave-teste"}
                )
                assert r.status_code == 403
