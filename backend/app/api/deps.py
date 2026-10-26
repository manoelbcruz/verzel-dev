from typing import Annotated

from fastapi import Depends, Header, Request

from app.recursos import Recursos
from app.schemas.comum import validar_chave
from app.services.auth import UsuarioAutenticado, autenticar_token, exigir_papel


def obter_recursos(request: Request) -> Recursos:
    return request.app.state.recursos


RecursosDep = Annotated[Recursos, Depends(obter_recursos)]


async def obter_usuario(request: Request, recursos: RecursosDep) -> UsuarioAutenticado:
    return await autenticar_token(recursos.fabrica, request.cookies.get("sessao"))


UsuarioDep = Annotated[UsuarioAutenticado, Depends(obter_usuario)]


async def usuario_opcional(request: Request, recursos: RecursosDep):
    token = request.cookies.get("sessao")
    if token is None:
        return None
    from app.core.erros import Recusa

    try:
        return await autenticar_token(recursos.fabrica, token)
    except Recusa as exc:
        if exc.codigo != "nao_autenticado":
            raise
        return None


UsuarioOpcional = Annotated[UsuarioAutenticado | None, Depends(usuario_opcional)]


def leiloeiro(usuario: UsuarioDep):
    exigir_papel(usuario, "leiloeiro")
    return usuario


def licitante(usuario: UsuarioDep):
    exigir_papel(usuario, "licitante")
    return usuario


LeiloeiroDep = Annotated[UsuarioAutenticado, Depends(leiloeiro)]
LicitanteDep = Annotated[UsuarioAutenticado, Depends(licitante)]


def obter_chave(chave: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
    return validar_chave(chave)


ChaveDep = Annotated[str, Depends(obter_chave)]
