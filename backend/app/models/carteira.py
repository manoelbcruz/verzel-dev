from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import JS_MAX_SEGURO
from app.db.base import Base
from app.models.apoio import DataCriacao, Id


class CarteiraRegistro(Base):
    __tablename__ = "carteiras"
    __table_args__ = (
        CheckConstraint("saldo_centavos >= 0", name="saldo_nao_negativo"),
        CheckConstraint(f"{JS_MAX_SEGURO} >= saldo_centavos", name="saldo_seguro_js"),
    )
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), primary_key=True)
    saldo_centavos: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    atualizada_em: Mapped[DataCriacao]


class Lancamento(Base):
    __tablename__ = "lancamentos"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('deposito','arremate_debito','arremate_credito')", name="tipo_valido"
        ),
        CheckConstraint(
            "(tipo = 'arremate_debito' AND valor_centavos < 0) OR "
            "(tipo IN ('deposito','arremate_credito') AND valor_centavos > 0)",
            name="sinal_por_tipo",
        ),
        CheckConstraint(
            "(tipo = 'deposito' AND liquidacao_id IS NULL) OR "
            "(tipo IN ('arremate_debito','arremate_credito') AND liquidacao_id IS NOT NULL)",
            name="liquidacao_por_tipo",
        ),
        UniqueConstraint("liquidacao_id", "tipo", name="uq_lancamentos_liquidacao_id_tipo"),
    )
    id: Mapped[Id]
    usuario_id: Mapped[int] = mapped_column(ForeignKey("carteiras.usuario_id"), index=True)
    tipo: Mapped[str] = mapped_column(Text)
    valor_centavos: Mapped[int] = mapped_column(BigInteger)
    liquidacao_id: Mapped[int | None] = mapped_column(ForeignKey("liquidacoes.id"))
    criado_em: Mapped[DataCriacao]


class Reserva(Base):
    __tablename__ = "reservas"
    __table_args__ = (CheckConstraint("valor_centavos > 0", name="valor_positivo"),)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id"), primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("carteiras.usuario_id"), index=True)
    valor_centavos: Mapped[int] = mapped_column(BigInteger)
    atualizada_em: Mapped[DataCriacao]
