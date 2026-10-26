from urllib.parse import urlsplit

from starlette.responses import JSONResponse

from app.core.config import Settings
from app.core.erros import Recusa


def origem_permitida(origem: str | None, settings: Settings) -> bool:
    return origem is not None and origem != "null" and origem in settings.cors_origins


class ProtecaoCSRF:
    def __init__(self, app, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope["path"].startswith("/api/")
            and scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}
        ):
            headers = {k.decode().lower(): v.decode("latin-1") for k, v in scope["headers"]}
            origem = headers.get("origin")
            if origem is None and headers.get("referer"):
                try:
                    url = urlsplit(headers["referer"])
                    origem = f"{url.scheme}://{url.netloc}"
                except ValueError:
                    origem = None
            if not origem_permitida(origem, self.settings):
                erro = Recusa("origem_invalida")
                await JSONResponse(erro.corpo(), status_code=erro.status)(scope, receive, send)
                return
        await self.app(scope, receive, send)
