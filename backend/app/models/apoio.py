from datetime import datetime
from typing import Annotated

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

Id = Annotated[int, mapped_column(BigInteger, Identity(), primary_key=True)]
DataCriacao = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now())]


class Midia(Base):
    __tablename__ = "midias"
    __table_args__ = (
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_hex"),
        CheckConstraint(
            "content_type IN ('image/jpeg','image/png','image/webp')", name="tipo_permitido"
        ),
        CheckConstraint("tamanho_bytes BETWEEN 1 AND 5000000", name="tamanho_valido"),
    )
    id: Mapped[Id]
    sha256: Mapped[str] = mapped_column(Text, unique=True)
    content_type: Mapped[str] = mapped_column(Text)
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    dados: Mapped[bytes] = mapped_column(LargeBinary)
    origem_url: Mapped[str] = mapped_column(Text, index=True)
    criado_em: Mapped[DataCriacao]


class ChaveIdempotencia(Base):
    __tablename__ = "chaves_idempotencia"
    __table_args__ = (
        CheckConstraint("operacao IN ('lance','deposito')", name="operacao_valida"),
        UniqueConstraint(
            "usuario_id",
            "operacao",
            "chave",
            name="uq_chaves_idempotencia_usuario_operacao_chave",
        ),
    )
    id: Mapped[Id]
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    operacao: Mapped[str] = mapped_column(Text)
    chave: Mapped[str] = mapped_column(Text)
    impressao: Mapped[str] = mapped_column(Text)
    status_http: Mapped[int | None] = mapped_column(Integer)
    resposta: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    criada_em: Mapped[DataCriacao]


class CacheMetRegistro(Base):
    __tablename__ = "cache_met"
    chave: Mapped[str] = mapped_column(Text, primary_key=True)
    dados: Mapped[dict] = mapped_column(JSONB)
    obtido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
