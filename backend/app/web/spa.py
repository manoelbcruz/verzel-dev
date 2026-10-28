from dataclasses import dataclass
from pathlib import Path

from starlette.responses import Response

from app.core.chaves import ConfiguracaoInvalida

TIPOS = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".json": "application/json",
    ".txt": "text/plain",
    ".woff2": "font/woff2",
    ".map": "application/json",
}
CABECALHOS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
}


@dataclass(frozen=True)
class ArquivosSpa:
    arquivos: dict[str, tuple[bytes, str]]

    @classmethod
    def carregar(cls, diretorio):
        raiz = Path(diretorio)
        if not (raiz / "index.html").is_file():
            raise ConfiguracaoInvalida("FRONTEND_DIST precisa conter index.html")
        arquivos = {
            arquivo.relative_to(raiz).as_posix(): (
                arquivo.read_bytes(),
                TIPOS.get(arquivo.suffix, "application/octet-stream"),
            )
            for arquivo in raiz.rglob("*")
            if arquivo.is_file()
        }
        return cls(arquivos)

    def responder(self, caminho, metodo):
        if metodo not in {"GET", "HEAD"}:
            return None
        if caminho in {"/api", "/ws"} or caminho.startswith(("/api/", "/ws/")):
            return None
        relativo = caminho.removeprefix("/")
        if relativo not in self.arquivos:
            if relativo.startswith("assets/") or "." in relativo.rsplit("/", 1)[-1]:
                return None
            relativo = "index.html"
        dados, tipo = self.arquivos[relativo]
        headers = {
            **CABECALHOS,
            "Cache-Control": "public, max-age=31536000, immutable"
            if relativo.startswith("assets/")
            else "no-cache",
            "Content-Length": str(len(dados)),
        }
        return Response(dados if metodo == "GET" else b"", media_type=tipo, headers=headers)
