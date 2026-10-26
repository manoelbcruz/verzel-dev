from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.apoio import DataCriacao, Id


class Lote(Base):
    __tablename__ = "lotes"
    __table_args__ = (
        CheckConstraint("status IN ('publicado','cancelado','encerrado')", name="status_valido"),
        CheckConstraint("lance_inicial_centavos > 0", name="lance_inicial_positivo"),
        CheckConstraint("incremento_centavos > 0", name="incremento_positivo"),
        CheckConstraint("fim_original_em > inicio_em", name="fim_depois_do_inicio"),
        CheckConstraint("fim_em >= fim_original_em", name="fim_nao_recua"),
        CheckConstraint(
            "((total_lances = 0) = (lider_id IS NULL)) AND "
            "((lider_id IS NULL) = (lance_atual_centavos IS NULL))",
            name="projecao_coerente",
        ),
        CheckConstraint("cabeca_seq > 0", name="cabeca_seq_positiva"),
        CheckConstraint("octet_length(cabeca_assinatura) = 32", name="cabeca_assinatura_32"),
        Index("ix_lotes_status_fim_em", "status", "fim_em"),
    )
    id: Mapped[Id]
    public_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    leiloeiro_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    status: Mapped[str] = mapped_column(Text)
    item_fonte: Mapped[str] = mapped_column(Text)
    item_id_externo: Mapped[str] = mapped_column(Text)
    titulo: Mapped[str] = mapped_column(Text)
    atributos: Mapped[dict[str, str]] = mapped_column(JSONB)
    midia_id: Mapped[int] = mapped_column(ForeignKey("midias.id"))
    lance_inicial_centavos: Mapped[int] = mapped_column(BigInteger)
    incremento_centavos: Mapped[int] = mapped_column(BigInteger)
    inicio_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fim_original_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fim_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lance_atual_centavos: Mapped[int | None] = mapped_column(BigInteger)
    lider_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    total_lances: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cabeca_seq: Mapped[int] = mapped_column(Integer)
    cabeca_assinatura: Mapped[bytes] = mapped_column(LargeBinary)
    criado_em: Mapped[DataCriacao]


class EventoLote(Base):
    __tablename__ = "eventos_lote"
    __table_args__ = (
        CheckConstraint("seq > 0", name="seq_positiva"),
        CheckConstraint(
            "tipo IN ('publicacao','lance','cancelamento','encerramento')", name="tipo_valido"
        ),
        CheckConstraint("octet_length(mac) = 32", name="mac_32"),
        CheckConstraint(
            "(tipo = 'lance' AND licitante_id IS NOT NULL AND pseudonimo IS NOT NULL "
            "AND valor_centavos IS NOT NULL AND fim_anterior IS NOT NULL "
            "AND fim_novo IS NOT NULL AND valor_centavos > 0 AND fim_novo >= fim_anterior) "
            "OR (tipo <> 'lance' AND licitante_id IS NULL AND pseudonimo IS NULL "
            "AND valor_centavos IS NULL AND fim_anterior IS NULL AND fim_novo IS NULL)",
            name="campos_de_lance",
        ),
        UniqueConstraint("lote_id", "seq", name="uq_eventos_lote_lote_id_seq"),
    )
    id: Mapped[Id]
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id"))
    seq: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(Text)
    instante: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    licitante_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    pseudonimo: Mapped[str | None] = mapped_column(Text)
    valor_centavos: Mapped[int | None] = mapped_column(BigInteger)
    fim_anterior: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fim_novo: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mac: Mapped[bytes] = mapped_column(LargeBinary)


class Liquidacao(Base):
    __tablename__ = "liquidacoes"
    __table_args__ = (
        CheckConstraint("resultado IN ('arrematado','sem_lances')", name="resultado_valido"),
        CheckConstraint(
            "(resultado = 'arrematado' AND vencedor_id IS NOT NULL "
            "AND vencedor_pseudonimo IS NOT NULL AND valor_centavos IS NOT NULL "
            "AND comprovante_codigo IS NOT NULL AND valor_centavos > 0) OR "
            "(resultado = 'sem_lances' AND vencedor_id IS NULL AND vencedor_pseudonimo IS NULL "
            "AND valor_centavos IS NULL AND comprovante_codigo IS NULL)",
            name="campos_por_resultado",
        ),
    )
    id: Mapped[Id]
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id"), unique=True)
    resultado: Mapped[str] = mapped_column(Text)
    vencedor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    vencedor_pseudonimo: Mapped[str | None] = mapped_column(Text)
    valor_centavos: Mapped[int | None] = mapped_column(BigInteger)
    comprovante_codigo: Mapped[str | None] = mapped_column(Text, unique=True)
