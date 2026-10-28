import json
import socket

import anyio
import pytest
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from app.main import create_app
from app.services.lances import dar_lance
from tests.apoio import criar_lote, criar_usuario

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


async def test_websocket_real(recursos, cliente):
    usuario = await criar_usuario(recursos, saldo=1000, cliente=cliente)
    lote = await criar_lote(recursos)
    recursos.publicador = recursos.central
    servidor = uvicorn.Server(uvicorn.Config(create_app(recursos=recursos), log_level="warning"))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        url = f"ws://127.0.0.1:{listener.getsockname()[1]}/ws"

        async def servir():
            await servidor.serve(sockets=[listener])

        async with anyio.create_task_group() as grupo:
            grupo.start_soon(servir)
            try:
                with anyio.fail_after(5):
                    while not servidor.started:
                        await anyio.sleep(0.01)
                with pytest.raises(InvalidStatus) as erro:
                    async with connect(url, origin="http://evil.example"):
                        pytest.fail("Origin inválido aceito")
                assert erro.value.response.status_code == 403
                async with connect(
                    url,
                    origin="http://test",
                    additional_headers={"Cookie": f"sessao={cliente.cookies.get('sessao')}"},
                ) as ws:
                    with anyio.fail_after(5):
                        assert json.loads(await ws.recv())["autenticado"] is True
                        await dar_lance(recursos, usuario, lote.id, 100, "lance-socket-real")
                        assert json.loads(await ws.recv())["tipo"] == "lote_atualizado"
            finally:
                servidor.should_exit = True
