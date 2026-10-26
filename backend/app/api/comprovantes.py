from fastapi import APIRouter

from app.api.deps import RecursosDep
from app.schemas.comprovantes import Comprovante
from app.schemas.comum import CodigoComprovante
from app.services.consultas import comprovante

router = APIRouter(prefix="/comprovantes")


@router.get("/{codigo}", response_model=Comprovante)
async def consultar(codigo: CodigoComprovante, recursos: RecursosDep):
    return await comprovante(recursos, codigo)
