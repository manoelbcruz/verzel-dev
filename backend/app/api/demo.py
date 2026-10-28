from fastapi import APIRouter, Request

from app.core.config import SENHA_DEMO_PUBLICA
from app.core.erros import Recusa
from app.schemas.demo import ContasDemo

router = APIRouter()


@router.get("/demo", response_model=ContasDemo)
async def demonstracao(request: Request):
    recursos = request.app.state.recursos
    if not recursos.settings.seed_demo or not recursos.contas_demo:
        raise Recusa("nao_encontrado")
    senha = recursos.settings.senha_demo.get_secret_value()
    return ContasDemo(
        contas=recursos.contas_demo,
        senha=SENHA_DEMO_PUBLICA if senha == SENHA_DEMO_PUBLICA else None,
    )
