import json
from types import SimpleNamespace
from uuid import UUID

import anyio
import pytest

from app.core.erros import Recusa
from app.main import create_app
from app.recursos import abrir_recursos
from app.services.auth import UsuarioAutenticado
from app.services.notificacoes import EventoDominio, PublicadorMemoria
from app.services.tempo_real import TIPOS_LOTE, CentralLotada, CentralTempoReal, traduzir
from tests.ws_asgi import conectar

LOTE_ID = UUID("0F8FAD5B-D9CB-469F-A165-70867728950E")


def usuario(id=1, sessao=10):
    return UsuarioAutenticado(id, "Pessoa privada", "privado@example.test", "licitante", sessao)


@pytest.mark.parametrize("tipo", sorted(TIPOS_LOTE))
def test_traduzir_lote_sem_dados_privados(tipo):
    evento = EventoDominio(
        tipo, LOTE_ID, 5, {"pseudonimo": "secreto", "valor_centavos": 123456}, (123, 456)
    )
    texto, destinos = traduzir(evento)
    assert json.loads(texto) == {"v": 1, "tipo": tipo, "lote_id": str(LOTE_ID), "versao": 5}
    assert destinos is None


def test_traduzir_carteira_e_invalidos():
    texto, destinos = traduzir(EventoDominio("carteira_atualizada", usuarios_afetados=(1, 2)))
    assert json.loads(texto) == {"v": 1, "tipo": "carteira_atualizada"}
    assert destinos == frozenset({1, 2})
    for evento in (
        EventoDominio("desconhecido"),
        EventoDominio("lote_atualizado", LOTE_ID),
        EventoDominio("carteira_atualizada"),
    ):
        assert traduzir(evento) is None


def test_central_isola_sessoes_e_destinatarios():
    central = CentralTempoReal(max_conexoes=4)
    anonimo, a, outra_aba, b = (
        central.registrar(u) for u in (None, usuario(), usuario(sessao=11), usuario(2, 20))
    )
    with pytest.raises(CentralLotada):
        central.registrar(None)
    central.publicar(EventoDominio("carteira_atualizada", usuarios_afetados=(1,)))
    central.publicar(EventoDominio("lote_atualizado", LOTE_ID, 5))
    for conexao in (a, outra_aba):
        assert json.loads(conexao.recebimento.receive_nowait())["tipo"] == "carteira_atualizada"
    for conexao in (anonimo, a, outra_aba, b):
        assert json.loads(conexao.recebimento.receive_nowait())["tipo"] == "lote_atualizado"
    assert central.encerrar_sessao(10) == 1
    central.publicar(EventoDominio("carteira_atualizada", usuarios_afetados=(1,)))
    assert a.codigo_fechamento == 4001
    with pytest.raises(anyio.EndOfStream):
        a.recebimento.receive_nowait()
    assert json.loads(outra_aba.recebimento.receive_nowait())["tipo"] == "carteira_atualizada"
    central.encerrar_todas()
    assert central.total == 4  # O limite só é liberado no finally do endpoint.
    for conexao in (anonimo, a, outra_aba, b):
        central.remover(conexao)
        central.remover(conexao)
    assert central.total == 0
    assert central.registrar(usuario()).usuario_id is None


def test_fila_cheia_fecha_apenas_o_lento_e_nao_levanta():
    central = CentralTempoReal(tamanho_fila=1)
    lento, rapido = central.registrar(None), central.registrar(None)
    evento = EventoDominio("lote_atualizado", LOTE_ID, 5)
    central.publicar(evento)
    rapido.recebimento.receive_nowait()
    central.publicar(evento)
    assert lento.codigo_fechamento == 1013
    assert rapido.codigo_fechamento is None
    rapido.recebimento.receive_nowait()
    rapido.recebimento.close()
    central.publicar(evento)
    central.publicar(EventoDominio("desconhecido"))
    central.publicar(None)
    assert rapido.codigo_fechamento == 1000


@pytest.mark.anyio
async def test_recursos_publicador_padrao_e_explicito(settings_teste):
    async with abrir_recursos(settings_teste, iniciar_worker=False) as recursos:
        assert recursos.publicador is recursos.central
    publicador = PublicadorMemoria()
    async with abrir_recursos(
        settings_teste, iniciar_worker=False, publicador=publicador
    ) as recursos:
        assert recursos.publicador is publicador


@pytest.fixture
def ambiente_ws(settings_teste, monkeypatch):
    recursos = SimpleNamespace(settings=settings_teste, central=CentralTempoReal(), fabrica=None)
    chamadas = []

    async def autenticar(fabrica, token):
        chamadas.append(token)
        if token == "token-a":
            return usuario()
        if token == "token-b":
            return usuario(2, 20)
        raise Recusa("nao_autenticado")

    monkeypatch.setattr("app.api.tempo_real.autenticar_token", autenticar)
    return create_app(recursos=recursos), recursos, chamadas


@pytest.mark.anyio
@pytest.mark.parametrize("origem", [None, "null", "http://evil.example", "http://test.evil"])
@pytest.mark.parametrize("cookie", [None, "token-a"])
async def test_handshake_recusa_origem_antes_de_autenticar(ambiente_ws, origem, cookie):
    app, recursos, chamadas = ambiente_ws
    async with conectar(app, origem=origem, cookie=cookie) as socket:
        assert (await socket.proxima()) == {"type": "websocket.close", "code": 1008, "reason": ""}
    assert chamadas == []
    assert recursos.central.total == 0


@pytest.mark.anyio
@pytest.mark.parametrize("cookie", [None, "invalido", "token-a"])
async def test_handshake_identidade_e_entrega(ambiente_ws, cookie):
    app, recursos, _ = ambiente_ws
    async with conectar(app, cookie=cookie) as socket:
        assert (await socket.proxima())["type"] == "websocket.accept"
        assert await socket.json() == {"v": 1, "tipo": "ola", "autenticado": cookie == "token-a"}
        recursos.central.publicar(EventoDominio("carteira_atualizada", usuarios_afetados=(2,)))
        recursos.central.publicar(EventoDominio("carteira_atualizada", usuarios_afetados=(1,)))
        recursos.central.publicar(EventoDominio("lote_atualizado", LOTE_ID, 5))
        if cookie == "token-a":
            assert (await socket.json())["tipo"] == "carteira_atualizada"
        assert (await socket.json())["tipo"] == "lote_atualizado"
    assert recursos.central.total == 0


@pytest.mark.anyio
async def test_handshake_lotacao_e_banco(ambiente_ws, monkeypatch, caplog):
    app, recursos, chamadas = ambiente_ws
    recursos.central = CentralTempoReal(max_conexoes=1)
    conexao = recursos.central.registrar(None)
    async with conectar(app, cookie="token-a") as socket:
        assert (await socket.proxima())["code"] == 1013
    assert chamadas == []
    recursos.central.remover(conexao)

    async def falhar(*args):
        raise RuntimeError("Banco indisponível")

    monkeypatch.setattr("app.api.tempo_real.autenticar_token", falhar)
    async with conectar(app, cookie="token-a") as socket:
        assert (await socket.proxima())["code"] == 1011
    assert "token-a" not in caplog.text
    assert recursos.central.total == 0


@pytest.mark.anyio
async def test_logout_entre_autenticacao_e_registro(ambiente_ws, monkeypatch):
    app, recursos, _ = ambiente_ws
    leu, liberar = anyio.Event(), anyio.Event()

    async def autenticar(*args):
        leu.set()
        await liberar.wait()
        return usuario()

    monkeypatch.setattr("app.api.tempo_real.autenticar_token", autenticar)
    async with conectar(app, cookie="token-a") as socket:
        await leu.wait()
        recursos.central.encerrar_sessao(10)
        liberar.set()
        assert (await socket.proxima())["type"] == "websocket.accept"
        assert (await socket.json())["autenticado"] is False
        recursos.central.publicar(EventoDominio("carteira_atualizada", usuarios_afetados=(1,)))
        recursos.central.publicar(EventoDominio("lote_atualizado", LOTE_ID, 5))
        assert (await socket.json())["tipo"] == "lote_atualizado"


@pytest.mark.anyio
async def test_registra_antes_do_ola(ambiente_ws, monkeypatch):
    app, recursos, _ = ambiente_ws
    original = recursos.central.registrar

    def registrar(usuario):
        conexao = original(usuario)
        recursos.central.publicar(EventoDominio("lote_atualizado", LOTE_ID, 5))
        return conexao

    monkeypatch.setattr(recursos.central, "registrar", registrar)
    async with conectar(app) as socket:
        assert (await socket.proxima())["type"] == "websocket.accept"
        assert (await socket.json())["tipo"] == "ola"
        assert (await socket.json())["tipo"] == "lote_atualizado"


@pytest.mark.anyio
@pytest.mark.parametrize("etapa", ["websocket.accept", "ola", "lote_atualizado"])
async def test_falha_no_driver_nao_deixa_conexao(ambiente_ws, etapa):
    app, recursos, _ = ambiente_ws

    async def falhar(mensagem):
        if mensagem["type"] == etapa or etapa in mensagem.get("text", ""):
            raise OSError("Cliente desconectado")

    async with conectar(app, interceptar=falhar) as socket:
        if etapa != "websocket.accept":
            await socket.proxima()
        if etapa == "lote_atualizado":
            await socket.json()
            recursos.central.publicar(EventoDominio("lote_atualizado", LOTE_ID, 5))
        with anyio.fail_after(2):
            await socket.terminou.wait()
    assert recursos.central.total == 0


@pytest.mark.anyio
async def test_logout_cancela_envio_bloqueado_sem_drenar(ambiente_ws):
    app, recursos, _ = ambiente_ws
    bloqueado = anyio.Event()

    async def bloquear(mensagem):
        if "carteira_atualizada" in mensagem.get("text", ""):
            bloqueado.set()
            await anyio.sleep_forever()

    async with conectar(app, cookie="token-a", interceptar=bloquear) as socket:
        await socket.proxima()
        await socket.json()
        evento = EventoDominio("carteira_atualizada", usuarios_afetados=(1,))
        recursos.central.publicar(evento)
        await bloqueado.wait()
        recursos.central.publicar(evento)
        recursos.central.encerrar_sessao(10)
        assert recursos.central.total == 1
        assert (await socket.proxima())["code"] == 4001
    assert recursos.central.total == 0


@pytest.mark.anyio
async def test_envio_sem_consumidor_expira_e_libera_vaga(ambiente_ws, monkeypatch):
    app, recursos, _ = ambiente_ws
    monkeypatch.setattr("app.api.tempo_real.PRAZO_ENVIO_S", 0.03)

    async def bloquear(mensagem):
        if "lote_atualizado" in mensagem.get("text", ""):
            await anyio.sleep_forever()

    async with conectar(app, interceptar=bloquear) as socket:
        await socket.proxima()
        await socket.json()
        recursos.central.publicar(EventoDominio("lote_atualizado", LOTE_ID, 5))
        with anyio.fail_after(0.5):
            await socket.terminou.wait()
    assert recursos.central.total == 0


@pytest.mark.anyio
async def test_ping_e_texto_do_cliente(ambiente_ws):
    app, recursos, _ = ambiente_ws
    recursos.settings.ws_intervalo_ping_s = 0.05
    async with conectar(app) as socket:
        await socket.proxima()
        await socket.json()
        await socket.enviar_texto("união com usuário 2")
        assert await socket.json() == {"v": 1, "tipo": "ping"}


@pytest.mark.anyio
@pytest.mark.parametrize("falha", ["recusa", "erro", "bloqueio"])
async def test_revalidacao_tem_prazo(ambiente_ws, monkeypatch, falha):
    app, recursos, _ = ambiente_ws
    recursos.settings.ws_revalidar_s = 0.02
    monkeypatch.setattr("app.api.tempo_real.MARGEM_REVALIDACAO_S", 0.06)
    monkeypatch.setattr("app.api.tempo_real.PRAZO_AUTENTICACAO_S", 0.02)
    async with conectar(app, cookie="token-a") as socket:
        await socket.proxima()
        await socket.json()

        async def autenticar(*args):
            if falha == "recusa":
                raise Recusa("nao_autenticado")
            if falha == "erro":
                raise RuntimeError("Banco indisponível")
            await anyio.sleep_forever()

        monkeypatch.setattr("app.api.tempo_real.autenticar_token", autenticar)
        assert (await socket.proxima(timeout=0.5))["code"] == 4001
    assert recursos.central.total == 0
