from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import LeiloeiroDep, RecursosDep
from app.schemas.comum import IdItem, Texto
from app.schemas.itens import ItemExterno, PaginaItens
from app.schemas.lotes import LoteDetalhe, LoteEntrada, LoteResumo, PainelLeiloeiro
from app.services import consultas, lotes

router = APIRouter(prefix="/leiloeiro")


@router.get("/itens", response_model=PaginaItens)
async def buscar_itens(
    recursos: RecursosDep,
    usuario: LeiloeiroDep,
    q: Annotated[Texto, Query(min_length=1, max_length=200)],
    pagina: Annotated[int, Query(ge=1)] = 1,
):
    return await recursos.met.buscar(q, pagina)


@router.get("/itens/{item_id}", response_model=ItemExterno)
async def item(item_id: IdItem, recursos: RecursosDep, usuario: LeiloeiroDep):
    return await recursos.met.obter_item(item_id)


@router.post("/lotes", response_model=LoteDetalhe, status_code=201)
async def criar(entrada: LoteEntrada, recursos: RecursosDep, usuario: LeiloeiroDep):
    return await lotes.criar_lote_do_met(recursos, usuario, entrada)


@router.get("/lotes", response_model=PainelLeiloeiro)
async def painel(recursos: RecursosDep, usuario: LeiloeiroDep):
    return await consultas.painel(recursos, usuario)


@router.post("/lotes/{lote_id}/cancelar", response_model=LoteResumo)
async def cancelar(lote_id: UUID, recursos: RecursosDep, usuario: LeiloeiroDep):
    return await lotes.cancelar_lote(recursos, usuario, lote_id)
