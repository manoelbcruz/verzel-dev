import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from app.core.config import MAX_DEPOSITO
from app.integrations.imagens import MidiaBaixada, assinatura_confere
from app.integrations.met import normalizar_item
from app.schemas.itens import ItemExterno

SALDO_MINIMO = 500_000
SALDO_ALVO = 1_000_000
DADOS = Path(__file__).parent / "dados"


@dataclass(frozen=True)
class UsuarioDemo:
    chave: str
    email: str
    nome: str
    papel: str
    rotulo: str


USUARIOS_DEMO = (
    UsuarioDemo(
        "leiloeiro", "leiloeiro@demo.example", "Leiloeiro Demonstração", "leiloeiro", "leiloeiro"
    ),
    UsuarioDemo("comprador1", "comprador1@demo.example", "Comprador 1", "licitante", "comprador 1"),
    UsuarioDemo("comprador2", "comprador2@demo.example", "Comprador 2", "licitante", "comprador 2"),
)


@dataclass(frozen=True)
class PapelLote:
    papel: str
    item_id: int
    lance_inicial_centavos: int
    incremento_centavos: int
    lances: tuple[tuple[str, int], ...]


CATALOGO = (
    PapelLote(
        "ao_vivo",
        45434,
        150000,
        5000,
        (("comprador1", 150000), ("comprador2", 160000), ("comprador1", 175000)),
    ),
    PapelLote("ao_vivo", 438817, 80000, 2500, (("comprador2", 80000), ("comprador1", 90000))),
    PapelLote("encerrado", 436105, 30000, 1000, (("comprador1", 30000), ("comprador2", 35000))),
    PapelLote("agendado", 459123, 200000, 10000, ()),
)


def carregar_item(papel: PapelLote) -> tuple[ItemExterno, MidiaBaixada]:
    arquivo = DADOS / f"met-{papel.item_id}.json"
    normalizado = normalizar_item(json.loads(arquivo.read_text(encoding="utf-8")), papel.item_id)
    if "item" not in normalizado:
        raise ValueError(f"Item inválido em {arquivo.name}")
    imagem = DADOS / f"met-{papel.item_id}.jpg"
    dados = imagem.read_bytes()
    if len(dados) > 5_000_000 or not assinatura_confere(dados, "image/jpeg"):
        raise ValueError(f"Imagem inválida em {imagem.name}")
    return ItemExterno.model_validate(normalizado["item"]), MidiaBaixada(
        dados, "image/jpeg", hashlib.sha256(dados).hexdigest()
    )


@dataclass(frozen=True)
class LoteExistente:
    public_id: UUID
    status: str
    inicio_em: datetime
    fim_em: datetime
    total_lances: int
    resultado: str | None


@dataclass(frozen=True)
class Criar:
    indice: int


@dataclass(frozen=True)
class DarLances:
    indice: int
    public_id: UUID | None


type Acao = Criar | DarLances


def planejar(existentes: dict[int, list[LoteExistente]], agora: datetime) -> list[Acao]:
    acoes: list[Acao] = []
    for indice, papel in enumerate(CATALOGO):
        lotes = [lote for lote in existentes.get(papel.item_id, []) if lote.status != "cancelado"]
        vigentes = [lote for lote in lotes if lote.status == "publicado"]
        if papel.papel == "ao_vivo":
            candidatos = [
                lote
                for lote in vigentes
                if lote.inicio_em <= agora and lote.fim_em > agora + timedelta(days=1)
            ]
        elif papel.papel == "agendado":
            candidatos = [lote for lote in vigentes if lote.inicio_em > agora + timedelta(hours=1)]
        else:
            if any(lote.resultado == "arrematado" for lote in lotes):
                continue
            com_lances = [lote for lote in vigentes if lote.total_lances > 0]
            if com_lances:
                lote = max(com_lances, key=lambda lote: lote.fim_em)
                if lote.fim_em > agora and lote.total_lances < len(papel.lances):
                    acoes.append(DarLances(indice, lote.public_id))
                continue
            candidatos = [lote for lote in vigentes if lote.fim_em > agora + timedelta(seconds=30)]
        if not candidatos:
            acoes.append(Criar(indice))
            if papel.lances:
                acoes.append(DarLances(indice, None))
        else:
            lote = max(candidatos, key=lambda lote: lote.fim_em)
            if lote.total_lances < len(papel.lances):
                acoes.append(DarLances(indice, lote.public_id))
    return acoes


def deposito_necessario(saldo: int, comprometido: int) -> int:
    disponivel = saldo - comprometido
    return min(SALDO_ALVO - disponivel, MAX_DEPOSITO) if disponivel < SALDO_MINIMO else 0
