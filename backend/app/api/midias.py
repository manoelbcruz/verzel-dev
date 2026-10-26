from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import RecursosDep
from app.core.erros import Recusa
from app.models import Midia
from app.schemas.comum import Sha256

router = APIRouter(prefix="/midias")


@router.get("/{sha256}", response_class=Response)
async def consultar(sha256: Sha256, recursos: RecursosDep):
    async with recursos.fabrica() as s, s.begin():
        midia = (
            await s.execute(select(Midia.dados, Midia.content_type).where(Midia.sha256 == sha256))
        ).one_or_none()
        if midia is None:
            raise Recusa("midia_nao_encontrada")
        return Response(
            midia.dados,
            media_type=midia.content_type,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "ETag": f'"{sha256}"',
                "X-Content-Type-Options": "nosniff",
            },
        )
