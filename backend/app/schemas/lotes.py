from datetime import timedelta
from typing import Literal
from uuid import UUID

from pydantic import model_validator

from app.schemas.comum import Centavos, DataUTC, IdItem, SaidaIdempotente, Schema

Fase = Literal["agendado", "ao_vivo", "encerrado", "cancelado"]


class LoteEntrada(Schema):
    item_id_externo: IdItem
    lance_inicial_centavos: Centavos
    incremento_centavos: Centavos
    inicio_em: DataUTC
    fim_em: DataUTC

    @model_validator(mode="after")
    def datas_validas(self):
        if not timedelta(minutes=1) <= self.fim_em - self.inicio_em <= timedelta(days=30):
            raise ValueError("Duração deve ser de 1 minuto a 30 dias")
        return self


class LanceEntrada(Schema):
    valor_centavos: Centavos


class Resultado(Schema):
    situacao: Literal["arrematado", "sem_lances"]
    valor_centavos: int | None
    vencedor_pseudonimo: str | None
    encerrado_em: DataUTC
    comprovante_codigo: str | None = None


class LoteResumo(Schema):
    id: UUID
    titulo: str
    imagem_url: str
    fase: Fase
    inicio_em: DataUTC
    fim_em: DataUTC
    lance_inicial_centavos: int
    lance_atual_centavos: int | None
    total_lances: int
    resultado: Resultado | None


class MinhaParticipacao(Schema):
    meu_pseudonimo: str
    ganhando: bool
    meu_maior_lance_centavos: int
    posicao: int
    total_participantes: int


class LanceHistorico(Schema):
    seq: int
    pseudonimo: str
    valor_centavos: int
    instante: DataUTC
    prorrogou: bool


class LoteDetalhe(LoteResumo):
    atributos: dict[str, str]
    incremento_centavos: int
    fim_original_em: DataUTC
    proximo_lance_minimo_centavos: int
    lider_pseudonimo: str | None
    versao: int
    servidor_agora: DataUTC
    lances: list[LanceHistorico]
    minha_participacao: MinhaParticipacao | None
    cancelavel: bool


class LanceAceito(SaidaIdempotente):
    lote_id: UUID
    seq: int
    valor_centavos: int
    instante: DataUTC
    fim_em: DataUTC
    prorrogou: bool
    lider_pseudonimo: str
    proximo_lance_minimo_centavos: int


class Vitrine(Schema):
    servidor_agora: DataUTC
    ao_vivo: list[LoteResumo]
    agendados: list[LoteResumo]
    encerrados: list[LoteResumo]


class LotePainel(LoteResumo):
    cancelavel: bool


class PainelLeiloeiro(Schema):
    total_recebido_centavos: int
    lotes: list[LotePainel]


class Participacao(Schema):
    lote: LoteResumo
    meu_pseudonimo: str
    meu_maior_lance_centavos: int
    situacao: Literal[
        "ganhando", "superado", "aguardando_resultado", "arrematado", "nao_arrematado"
    ]
    comprovante_codigo: str | None
