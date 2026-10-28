from contextlib import AsyncExitStack
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, update

from app.main import create_app
from app.models import Sessao
from app.schemas.auth import LoginEntrada
from app.services.auth import login
from app.services.carteira import depositar
from app.services.lances import dar_lance
from app.services.liquidacao import encerrar_lote
from app.services.notificacoes import EventoDominio
from tests.apoio import criar_lote, criar_usuario, envelhecer_lote
from tests.ws_asgi import conectar

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


async def test_eventos_reais_privacidade_e_logout(recursos):
    app = create_app(recursos=recursos)
    async with AsyncExitStack() as pilha:
        clientes = [
            await pilha.enter_async_context(
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://test",
                    headers={"Origin": "http://test"},
                )
            )
            for _ in range(4)
        ]
        dono = await criar_usuario(recursos, "leiloeiro", cliente=clientes[0])
        a, b, c = [await criar_usuario(recursos, saldo=1000, cliente=cl) for cl in clientes[1:]]
        lote = await criar_lote(recursos, dono)
        recursos.publicador = recursos.central
        sockets = [
            await pilha.enter_async_context(conectar(app, cookie=cl.cookies.get("sessao")))
            for cl in clientes
        ]
        sockets.append(await pilha.enter_async_context(conectar(app)))
        for i, socket in enumerate(sockets):
            assert (await socket.proxima())["type"] == "websocket.accept"
            assert (await socket.json())["autenticado"] is (i < 4)

        async def conferir(tipo, privados):
            for i, socket in enumerate(sockets):
                mensagem = await socket.json()
                assert set(mensagem) == {"v", "tipo", "lote_id", "versao"}
                assert mensagem["tipo"] == tipo
                detalhe = (await clientes[i % 4].get(f"/api/lotes/{lote.id}")).json()
                assert detalhe["versao"] == mensagem["versao"]
                if i in privados:
                    assert await socket.json() == {"v": 1, "tipo": "carteira_atualizada"}
            # Uma sentinela pública prova que não havia sinal privado para os demais.
            recursos.central.publicar(EventoDominio("lote_atualizado", lote.id, 999))
            for socket in sockets:
                assert (await socket.json())["versao"] == 999

        await dar_lance(recursos, a, lote.id, 100, "lance-ws-a")
        await conferir("lote_atualizado", {1})
        await dar_lance(recursos, b, lote.id, 110, "lance-ws-b")
        await conferir("lote_atualizado", {1, 2})
        await depositar(recursos, c, 100, "deposito-ws-c")
        assert (await sockets[3].json())["tipo"] == "carteira_atualizada"
        recursos.central.publicar(EventoDominio("lote_atualizado", lote.id, 998))
        for socket in sockets:
            assert (await socket.json())["versao"] == 998
        await encerrar_lote(recursos, await envelhecer_lote(recursos, lote.id))
        await conferir("lote_encerrado", {0, 2})

        # Login HTTP cria outra sessão da mesma identidade sem trocar a senha.
        import secrets

        entrada = {
            "nome": "Duas sessões",
            "email": "sessoes@example.test",
            "senha": secrets.token_urlsafe(18),
            "papel": "licitante",
        }
        cl = clientes[1]
        cl.cookies.clear()
        await cl.post("/api/auth/cadastro", json=entrada)
        primeira = await pilha.enter_async_context(conectar(app, cookie=cl.cookies.get("sessao")))
        await primeira.proxima()
        await primeira.json()
        outra, token = await login(
            recursos, LoginEntrada(email=entrada["email"], senha=entrada["senha"])
        )
        segunda = await pilha.enter_async_context(conectar(app, cookie=token))
        await segunda.proxima()
        await segunda.json()
        assert (await cl.post("/api/auth/logout")).status_code == 204
        assert (await primeira.proxima())["code"] == 4001
        await depositar(recursos, outra, 100, "outra-sessao-deposito")
        assert (await segunda.json())["tipo"] == "carteira_atualizada"


async def test_sessao_expirada_fica_anonima(recursos, cliente):
    usuario = await criar_usuario(recursos, cliente=cliente)
    async with recursos.fabrica() as s, s.begin():
        await s.execute(
            update(Sessao)
            .where(Sessao.id == usuario.sessao_id)
            .values(expira_em=func.clock_timestamp() - timedelta(seconds=1))
        )
    async with conectar(
        create_app(recursos=recursos), cookie=cliente.cookies.get("sessao")
    ) as socket:
        await socket.proxima()
        assert (await socket.json())["autenticado"] is False
