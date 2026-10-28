import logging

import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.erros import Recusa
from app.core.seguranca import origem_permitida
from app.services.auth import autenticar_token
from app.services.tempo_real import CentralLotada

router = APIRouter()
logger = logging.getLogger(__name__)
PRAZO_ENVIO_S = 10
PRAZO_AUTENTICACAO_S = 10
MARGEM_REVALIDACAO_S = 60
FALHAS_SOCKET = (WebSocketDisconnect, RuntimeError, OSError, TimeoutError)


async def fechar(websocket, codigo):
    try:
        with anyio.fail_after(PRAZO_ENVIO_S):
            await websocket.close(codigo)
    except FALHAS_SOCKET:
        pass  # O cliente já caiu ou não consome mais; a remoção é local.


@router.websocket("/ws")
async def tempo_real(websocket: WebSocket):
    recursos = websocket.app.state.recursos
    settings, central = recursos.settings, recursos.central
    if not origem_permitida(websocket.headers.get("origin"), settings):
        await fechar(websocket, 1008)
        return
    if central.lotada():
        await fechar(websocket, 1013)
        return
    token = websocket.cookies.get("sessao")
    usuario = None
    if token:
        try:
            with anyio.fail_after(PRAZO_AUTENTICACAO_S):
                usuario = await autenticar_token(recursos.fabrica, token)
        except Recusa as exc:
            if exc.codigo != "nao_autenticado":
                logger.exception("Falha na autenticação do WebSocket")
                await fechar(websocket, 1011)
                return
        except Exception:
            logger.exception("Falha na autenticação do WebSocket")
            await fechar(websocket, 1011)
            return
    try:
        conexao = central.registrar(usuario)
    except CentralLotada:
        await fechar(websocket, 1013)
        return
    try:

        async def enviar(operacao, *args):
            if conexao.codigo_fechamento is not None:
                return False
            # Logout cancela inclusive um envio que já esteja bloqueado no driver.
            with anyio.CancelScope() as escopo:
                conexao.escopo_envio = escopo
                try:
                    with anyio.fail_after(PRAZO_ENVIO_S):
                        await operacao(*args)
                finally:
                    conexao.escopo_envio = None
            return not escopo.cancel_called

        if not await enviar(websocket.accept):
            await fechar(websocket, conexao.codigo_fechamento or 1000)
            return
        if not await enviar(
            websocket.send_json,
            {"v": 1, "tipo": "ola", "autenticado": conexao.usuario_id is not None},
        ):
            await fechar(websocket, conexao.codigo_fechamento or 1000)
            return

        async with anyio.create_task_group() as grupo:

            async def remeter():
                try:
                    while conexao.codigo_fechamento is None:
                        mensagem = '{"v":1,"tipo":"ping"}'
                        with anyio.move_on_after(settings.ws_intervalo_ping_s):
                            mensagem = await conexao.recebimento.receive()
                        if not await enviar(websocket.send_text, mensagem):
                            break
                except anyio.EndOfStream:
                    pass
                except FALHAS_SOCKET:
                    central.encerrar(conexao, 1000)
                finally:
                    await fechar(websocket, conexao.codigo_fechamento or 1000)
                    grupo.cancel_scope.cancel()

            async def receber():
                try:
                    while True:
                        mensagem = await websocket.receive()
                        if mensagem["type"] == "websocket.disconnect":
                            break
                except FALHAS_SOCKET:
                    pass
                finally:
                    grupo.cancel_scope.cancel()

            async def revalidar():
                if conexao.sessao_id is None:
                    return
                ultima_validacao = anyio.current_time()
                while conexao.codigo_fechamento is None:
                    prazo = ultima_validacao + settings.ws_revalidar_s + MARGEM_REVALIDACAO_S
                    await anyio.sleep(
                        min(settings.ws_revalidar_s, max(0, prazo - anyio.current_time()))
                    )
                    restante = prazo - anyio.current_time()
                    if restante <= 0:
                        central.encerrar(conexao, 4001)
                        return
                    try:
                        with anyio.fail_after(min(PRAZO_AUTENTICACAO_S, restante)):
                            validado = await autenticar_token(recursos.fabrica, token)
                        if (
                            validado.sessao_id != conexao.sessao_id
                            or validado.id != conexao.usuario_id
                        ):
                            central.encerrar(conexao, 4001)
                            return
                        ultima_validacao = anyio.current_time()
                    except Recusa as exc:
                        if exc.codigo == "nao_autenticado":
                            central.encerrar(conexao, 4001)
                            return
                        logger.exception("Falha na revalidação do WebSocket")
                    except Exception:
                        logger.exception("Falha na revalidação do WebSocket")
                    if anyio.current_time() >= prazo:
                        central.encerrar(conexao, 4001)
                        return

            grupo.start_soon(remeter)
            grupo.start_soon(receber)
            grupo.start_soon(revalidar)
    except FALHAS_SOCKET:
        await fechar(websocket, 1000)
    finally:
        central.remover(conexao)
