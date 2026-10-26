import logging
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventoDominio:
    tipo: str
    lote_id: UUID | None = None
    versao: int | None = None
    dados: dict = field(default_factory=dict)
    usuarios_afetados: tuple[int, ...] = ()


class Publicador(Protocol):
    def publicar(self, evento: EventoDominio) -> None: ...


class PublicadorNulo:
    def publicar(self, evento: EventoDominio) -> None:
        pass


class PublicadorMemoria:
    def __init__(self):
        self.eventos: list[EventoDominio] = []

    def publicar(self, evento: EventoDominio) -> None:
        self.eventos.append(evento)


def publicar_depois_do_commit(publicador: Publicador, eventos: list[EventoDominio]) -> None:
    for evento in eventos:
        try:
            publicador.publicar(evento)
        except Exception:
            logger.exception("Falha na notificação pós-commit: %s", evento.tipo)
