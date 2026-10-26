from fastapi import APIRouter, Response

from app.api.deps import ChaveDep, LicitanteDep, RecursosDep, UsuarioDep
from app.schemas.carteira import Carteira, DepositoEntrada
from app.services.carteira import depositar
from app.services.consultas import consultar_carteira

router = APIRouter(prefix="/carteira")


@router.get("", response_model=Carteira)
async def consultar(recursos: RecursosDep, usuario: UsuarioDep):
    return await consultar_carteira(recursos, usuario)


@router.post("/depositos", response_model=Carteira, status_code=201)
async def deposito(
    entrada: DepositoEntrada,
    response: Response,
    recursos: RecursosDep,
    usuario: LicitanteDep,
    chave: ChaveDep,
):
    resultado = await depositar(recursos, usuario, entrada.valor_centavos, chave)
    response.status_code = resultado.status_http
    if resultado.repetida:
        response.headers["Idempotency-Replayed"] = "true"
    return resultado
