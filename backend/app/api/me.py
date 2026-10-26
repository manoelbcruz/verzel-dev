from fastapi import APIRouter

from app.api.deps import LicitanteDep, RecursosDep
from app.schemas.lotes import Participacao
from app.services.consultas import participacoes

router = APIRouter(prefix="/me")


@router.get("/participacoes", response_model=list[Participacao])
async def minhas_participacoes(recursos: RecursosDep, usuario: LicitanteDep):
    return await participacoes(recursos, usuario)
