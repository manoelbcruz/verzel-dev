from typing import Literal
from uuid import UUID

from app.schemas.comum import DataUTC, Schema
from app.schemas.lotes import Fase


class FalhaAuditoria(Schema):
    codigo: str
    seq: int | None
    mensagem: str


class EventoAuditoria(Schema):
    seq: int
    tipo: str
    instante: DataUTC
    licitante_pseudonimo: str | None
    valor_centavos: int | None
    fim_novo: DataUTC | None
    prorrogou: bool
    mac: str
    verificado: bool


class RelatorioAuditoria(Schema):
    lote_id: UUID
    titulo: str
    imagem_url: str
    fase: Fase
    veredito: Literal["integro", "adulterado"]
    metodo: str = "hmac-sha256-cadeia-por-lote-v1"
    total_eventos: int
    eventos_verificados: int
    falha: FalhaAuditoria | None
    verificado_em: DataUTC
    eventos: list[EventoAuditoria]
