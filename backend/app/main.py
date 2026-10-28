import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.auth import router as auth_router
from app.api.carteira import router as carteira_router
from app.api.comprovantes import router as comprovantes_router
from app.api.demo import router as demo_router
from app.api.health import router as health_router
from app.api.leiloeiro import router as leiloeiro_router
from app.api.lotes import router as lotes_router
from app.api.me import router as me_router
from app.api.midias import router as midias_router
from app.api.tempo_real import router as tempo_real_router
from app.core.config import get_settings
from app.core.erros import ErroApi, Recusa
from app.core.seguranca import ProtecaoCSRF
from app.recursos import abrir_recursos
from app.web.spa import ArquivosSpa

logger = logging.getLogger(__name__)


def create_app(
    settings=None, *, recursos=None, transporte_http=None, iniciar_worker=True
) -> FastAPI:
    settings = settings or (recursos.settings if recursos is not None else get_settings())
    spa = ArquivosSpa.carregar(settings.frontend_dist) if settings.frontend_dist else None

    @asynccontextmanager
    async def lifespan(app):
        if recursos is not None:
            yield
        else:
            async with abrir_recursos(
                settings, transporte_http=transporte_http, iniciar_worker=iniciar_worker
            ) as abertos:
                app.state.recursos = abertos
                yield

    app = FastAPI(
        title="Casa de Leilões",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    if recursos is not None:
        app.state.recursos = recursos
    app.add_middleware(ProtecaoCSRF, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ErroApi)
    async def erro_api(request: Request, exc: ErroApi):
        return JSONResponse(exc.corpo(), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def entrada_invalida(request: Request, exc: RequestValidationError):
        erro = Recusa(
            "entrada_invalida",
            {
                "campos": [
                    {"campo": ".".join(map(str, item["loc"])), "problema": item["msg"]}
                    for item in exc.errors()
                ]
            },
        )
        return JSONResponse(erro.corpo(), status_code=erro.status)

    @app.exception_handler(StarletteHTTPException)
    async def erro_http(request: Request, exc: StarletteHTTPException):
        if spa is not None and exc.status_code == 404 and request.method in {"GET", "HEAD"}:
            resposta = spa.responder(request.url.path, request.method)
            if resposta is not None:
                return resposta
        codigo = {404: "nao_encontrado", 405: "metodo_nao_permitido"}.get(
            exc.status_code, "entrada_invalida" if 400 <= exc.status_code < 500 else "erro_interno"
        )
        erro = ErroApi(exc.status_code, codigo)
        return JSONResponse(erro.corpo(), status_code=erro.status, headers=exc.headers)

    @app.exception_handler(Exception)
    async def erro_interno(request: Request, exc: Exception):
        logger.exception("Erro não tratado", exc_info=exc)
        erro = Recusa("erro_interno")
        return JSONResponse(erro.corpo(), status_code=erro.status)

    app.include_router(health_router, prefix="/api")
    app.include_router(tempo_real_router)
    app.include_router(auth_router, prefix="/api")
    for router in (
        carteira_router,
        demo_router,
        comprovantes_router,
        leiloeiro_router,
        lotes_router,
        me_router,
        midias_router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
