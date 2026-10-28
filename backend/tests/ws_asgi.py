import json
from contextlib import asynccontextmanager

import anyio


class SocketASGI:
    def __init__(self, envio, recebimento, terminou):
        self.envio = envio
        self.recebimento = recebimento
        self.terminou = terminou

    async def proxima(self, timeout=2):
        with anyio.fail_after(timeout):
            return await self.recebimento.receive()

    async def json(self, timeout=2):
        mensagem = await self.proxima(timeout)
        assert mensagem["type"] == "websocket.send", mensagem
        return json.loads(mensagem["text"])

    async def enviar_texto(self, texto):
        await self.envio.send({"type": "websocket.receive", "text": texto})


@asynccontextmanager
async def conectar(app, *, origem="http://test", cookie=None, caminho="/ws", interceptar=None):
    headers = [(b"host", b"test")]
    if origem is not None:
        headers.append((b"origin", origem.encode()))
    if cookie is not None:
        headers.append((b"cookie", f"sessao={cookie}".encode()))
    escopo = {
        "type": "websocket",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "scheme": "ws",
        "path": caminho,
        "raw_path": caminho.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
        "subprotocols": [],
        "state": {},
        "extensions": {},
    }
    entrada, receber_entrada = anyio.create_memory_object_stream(100)
    saida, receber_saida = anyio.create_memory_object_stream(100)
    terminou = anyio.Event()

    async def enviar(mensagem):
        if interceptar:
            await interceptar(mensagem)
        await saida.send(mensagem)
        if mensagem["type"] == "websocket.close":
            entrada.send_nowait({"type": "websocket.disconnect", "code": mensagem["code"]})

    async def executar():
        try:
            await app(escopo, receber_entrada.receive, enviar)
        finally:
            terminou.set()

    async with entrada, receber_entrada, saida, receber_saida, anyio.create_task_group() as grupo:
        entrada.send_nowait({"type": "websocket.connect"})
        grupo.start_soon(executar)
        try:
            yield SocketASGI(entrada, receber_saida, terminou)
        finally:
            entrada.send_nowait({"type": "websocket.disconnect", "code": 1000})
            with anyio.fail_after(2):
                await terminou.wait()
