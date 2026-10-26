from uuid import UUID

from app.schemas.comum import DataUTC, Schema


class EventoEncerramento(Schema):
    seq: int
    mac: str


class Comprovante(Schema):
    codigo: str
    lote_id: UUID
    titulo: str
    atributos: dict[str, str]
    imagem_url: str
    valor_centavos: int
    vencedor_pseudonimo: str
    encerrado_em: DataUTC
    evento_encerramento: EventoEncerramento
    auditoria_url: str
