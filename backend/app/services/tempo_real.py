import json
import logging
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

from app.services.notificacoes import EventoDominio

if TYPE_CHECKING:
    from app.services.auth import UsuarioAutenticado

logger = logging.getLogger(__name__)
TIPOS_LOTE = frozenset({"lote_publicado", "lote_atualizado", "lote_cancelado", "lote_encerrado"})
_avisados: set[str] = set()


class CentralLotada(Exception):
    pass


@dataclass
class Conexao:
    id: int
    usuario_id: int | None
    sessao_id: int | None
    envio: MemoryObjectSendStream[str]
    recebimento: MemoryObjectReceiveStream[str]
    codigo_fechamento: int | None = None
    escopo_envio: anyio.CancelScope | None = None


def traduzir(evento: EventoDominio) -> tuple[str, frozenset[int] | None] | None:
    mensagem = {"v": 1, "tipo": evento.tipo}
    if (
        evento.tipo in TIPOS_LOTE
        and isinstance(evento.lote_id, UUID)
        and type(evento.versao) is int
        and evento.versao > 0
    ):
        mensagem.update(lote_id=str(evento.lote_id), versao=evento.versao)
        destinos = None
    elif evento.tipo == "carteira_atualizada" and evento.usuarios_afetados:
        destinos = frozenset(evento.usuarios_afetados)
    else:
        if evento.tipo not in _avisados:
            _avisados.add(evento.tipo)
            logger.warning("Evento ignorado pelo tempo real: %s", evento.tipo)
        return None
    return json.dumps(mensagem, separators=(",", ":")), destinos


class CentralTempoReal:
    def __init__(self, max_conexoes=500, tamanho_fila=64):
        self.max_conexoes = max_conexoes
        self.tamanho_fila = tamanho_fila
        self._proximo_id = 0
        self._conexoes: dict[int, Conexao] = {}
        self._entregas: dict[int, Conexao] = {}
        self._revogadas: set[int] = set()
        self._ordem_revogadas: deque[int] = deque()

    @property
    def total(self) -> int:
        return len(self._conexoes)

    def lotada(self) -> bool:
        return self.total >= self.max_conexoes

    def registrar(self, usuario: "UsuarioAutenticado | None") -> Conexao:
        if self.lotada():
            raise CentralLotada
        if usuario and usuario.sessao_id in self._revogadas:
            usuario = None
        self._proximo_id += 1
        envio, recebimento = anyio.create_memory_object_stream[str](self.tamanho_fila)
        conexao = Conexao(
            self._proximo_id,
            usuario.id if usuario else None,
            usuario.sessao_id if usuario else None,
            envio,
            recebimento,
        )
        self._conexoes[conexao.id] = conexao
        self._entregas[conexao.id] = conexao
        return conexao

    def remover(self, conexao: Conexao) -> None:
        self._entregas.pop(conexao.id, None)
        self._conexoes.pop(conexao.id, None)
        conexao.envio.close()
        conexao.recebimento.close()

    def encerrar(self, conexao: Conexao, codigo: int) -> None:
        if conexao.codigo_fechamento is not None:
            return
        conexao.codigo_fechamento = codigo
        self._entregas.pop(conexao.id, None)
        conexao.envio.close()
        if conexao.escopo_envio is not None:
            conexao.escopo_envio.cancel()

    def encerrar_sessao(self, sessao_id: int, codigo=4001) -> int:
        if sessao_id not in self._revogadas:
            self._revogadas.add(sessao_id)
            self._ordem_revogadas.append(sessao_id)
            if len(self._ordem_revogadas) > 10_000:
                self._revogadas.remove(self._ordem_revogadas.popleft())
        conexoes = [c for c in self._entregas.values() if c.sessao_id == sessao_id]
        for conexao in conexoes:
            self.encerrar(conexao, codigo)
        return len(conexoes)

    def encerrar_todas(self, codigo=1012) -> None:
        for conexao in list(self._entregas.values()):
            self.encerrar(conexao, codigo)

    def publicar(self, evento: EventoDominio) -> None:
        try:
            traduzido = traduzir(evento)
            if traduzido is None:
                return
            texto, destinos = traduzido
            for conexao in list(self._entregas.values()):
                if destinos is not None and conexao.usuario_id not in destinos:
                    continue
                try:
                    conexao.envio.send_nowait(texto)
                except anyio.WouldBlock:
                    self.encerrar(conexao, 1013)
                except (anyio.ClosedResourceError, anyio.BrokenResourceError):
                    self.encerrar(conexao, 1000)
        except Exception:
            logger.exception("Falha ao publicar sinal de tempo real")
