from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.deps import ChaveDep, LicitanteDep, RecursosDep, UsuarioOpcional
from app.schemas.auditoria import RelatorioAuditoria
from app.schemas.comum import Texto
from app.schemas.lotes import LanceAceito, LanceEntrada, LoteDetalhe, Vitrine
from app.services import auditoria, consultas, lances

router = APIRouter(prefix="/lotes")


@router.get("", response_model=Vitrine)
async def vitrine(recursos: RecursosDep, q: Annotated[Texto | None, Query(max_length=200)] = None):
    return await consultas.vitrine(recursos, q)


@router.get("/{lote_id}", response_model=LoteDetalhe)
async def detalhe(lote_id: UUID, recursos: RecursosDep, usuario: UsuarioOpcional):
    return await consultas.detalhar_lote(recursos, lote_id, usuario)


@router.post("/{lote_id}/lances", response_model=LanceAceito, status_code=201)
async def lance(
    lote_id: UUID,
    entrada: LanceEntrada,
    response: Response,
    recursos: RecursosDep,
    usuario: LicitanteDep,
    chave: ChaveDep,
):
    resultado = await lances.dar_lance(recursos, usuario, lote_id, entrada.valor_centavos, chave)
    response.status_code = resultado.status_http
    if resultado.repetida:
        response.headers["Idempotency-Replayed"] = "true"
    return resultado


@router.get("/{lote_id}/auditoria", response_model=RelatorioAuditoria)
async def auditar(lote_id: UUID, recursos: RecursosDep):
    return await auditoria.auditar_lote(recursos, lote_id)
