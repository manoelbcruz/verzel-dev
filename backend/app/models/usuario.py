from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, LargeBinary, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.apoio import DataCriacao, Id


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (CheckConstraint("papel IN ('leiloeiro','licitante')", name="papel_valido"),)
    id: Mapped[Id]
    nome: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    senha_hash: Mapped[str] = mapped_column(Text)
    papel: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[DataCriacao]


class Sessao(Base):
    __tablename__ = "sessoes"
    __table_args__ = (CheckConstraint("octet_length(token_hash) = 32", name="token_hash_32"),)
    id: Mapped[Id]
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    criada_em: Mapped[DataCriacao]
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
