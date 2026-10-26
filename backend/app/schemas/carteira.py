from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.core.config import MAX_DEPOSITO
from app.schemas.comum import DataUTC, SaidaIdempotente, Schema


class DepositoEntrada(Schema):
    valor_centavos: Annotated[int, Field(strict=True, ge=1, le=MAX_DEPOSITO)]


class ReservaSaida(Schema):
    lote_id: UUID
    titulo: str
    valor_centavos: int


class LancamentoSaida(Schema):
    tipo: Literal["deposito", "arremate_debito", "arremate_credito"]
    valor_centavos: int
    criado_em: DataUTC
    lote_id: UUID | None


class Carteira(SaidaIdempotente):
    saldo_total_centavos: int
    comprometido_centavos: int
    disponivel_centavos: int
    reservas: list[ReservaSaida]
    lancamentos: list[LancamentoSaida]
