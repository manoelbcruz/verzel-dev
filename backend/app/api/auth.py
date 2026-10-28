from fastapi import APIRouter, Request, Response

from app.api.deps import RecursosDep, UsuarioDep
from app.schemas.auth import CadastroEntrada, LoginEntrada, UsuarioSaida
from app.services import auth

router = APIRouter(prefix="/auth")


def definir_cookie(response, token, settings):
    response.set_cookie(
        "sessao",
        token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=settings.sessao_dias * 86400,
        secure=settings.cookie_secure,
    )


@router.post("/cadastro", response_model=UsuarioSaida, status_code=201)
async def cadastro(entrada: CadastroEntrada, response: Response, recursos: RecursosDep):
    usuario, token = await auth.cadastrar_usuario(recursos, entrada)
    definir_cookie(response, token, recursos.settings)
    return UsuarioSaida.model_validate(usuario)


@router.post("/login", response_model=UsuarioSaida)
async def login(entrada: LoginEntrada, response: Response, recursos: RecursosDep):
    usuario, token = await auth.login(recursos, entrada)
    definir_cookie(response, token, recursos.settings)
    return UsuarioSaida.model_validate(usuario)


@router.post("/logout", status_code=204)
async def logout(request: Request, recursos: RecursosDep):
    sessao_id = await auth.logout(recursos, request.cookies.get("sessao"))
    if sessao_id is not None:
        recursos.central.encerrar_sessao(sessao_id)
    response = Response(status_code=204)
    response.delete_cookie(
        "sessao", path="/", secure=recursos.settings.cookie_secure, httponly=True, samesite="lax"
    )
    return response


@router.get("/me", response_model=UsuarioSaida)
async def me(usuario: UsuarioDep):
    return UsuarioSaida.model_validate(usuario)
