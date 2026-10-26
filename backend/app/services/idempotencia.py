import hashlib
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.erros import Recusa
from app.models import ChaveIdempotencia
from app.schemas.comum import SaidaIdempotente, validar_chave


@dataclass(frozen=True)
class RespostaIdempotente:
    status_http: int
    resposta: dict
    repetida: bool = False


def materializar[T: SaidaIdempotente](resultado: RespostaIdempotente, schema: type[T]) -> T:
    resposta = schema.model_validate(resultado.resposta)
    resposta._repetida = resultado.repetida
    resposta._status_http = resultado.status_http
    return resposta


def impressao(operacao, valor, public_id=None):
    texto = f"lance|v1|{public_id}|{valor}" if operacao == "lance" else f"deposito|v1|{valor}"
    return hashlib.sha256(texto.encode()).hexdigest()


async def iniciar(s, usuario_id, operacao, chave, resumo):
    validar_chave(chave)
    id_chave = await s.scalar(
        insert(ChaveIdempotencia)
        .values(
            usuario_id=usuario_id,
            operacao=operacao,
            chave=chave,
            impressao=resumo,
        )
        .on_conflict_do_nothing(
            index_elements=[
                ChaveIdempotencia.usuario_id,
                ChaveIdempotencia.operacao,
                ChaveIdempotencia.chave,
            ]
        )
        .returning(ChaveIdempotencia.id)
    )
    if id_chave is not None:
        return id_chave, None
    anterior = (
        (
            await s.execute(
                select(ChaveIdempotencia.__table__).where(
                    ChaveIdempotencia.usuario_id == usuario_id,
                    ChaveIdempotencia.operacao == operacao,
                    ChaveIdempotencia.chave == chave,
                )
            )
        )
        .mappings()
        .one()
    )
    if anterior["impressao"] != resumo:
        raise Recusa("chave_idempotencia_conflito")
    if anterior["status_http"] is None or anterior["resposta"] is None:
        raise Recusa("erro_interno")
    return None, RespostaIdempotente(anterior["status_http"], anterior["resposta"], True)


async def concluir(s, id_chave, resposta, status_http=201):
    corpo = resposta.model_dump(mode="json")
    await s.execute(
        update(ChaveIdempotencia)
        .where(ChaveIdempotencia.id == id_chave)
        .values(
            resposta=corpo,
            status_http=status_http,
        )
    )
    return RespostaIdempotente(status_http, corpo)
