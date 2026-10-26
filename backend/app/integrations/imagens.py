import hashlib
import logging
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.erros import Recusa

logger = logging.getLogger(__name__)


def url_para_log(url: str) -> str:
    try:
        partes = urlsplit(url)
        host = partes.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if partes.port is not None:
            host = f"{host}:{partes.port}"
        return urlunsplit((partes.scheme, host, partes.path, "", ""))
    except ValueError:
        return "<url inválida>"


@dataclass(frozen=True)
class MidiaBaixada:
    dados: bytes
    content_type: str
    sha256: str


def url_permitida(url: str) -> bool:
    try:
        partes = urlsplit(url)
        return (
            partes.scheme == "https"
            and partes.hostname == "images.metmuseum.org"
            and partes.username is None
            and partes.password is None
        )
    except ValueError:
        return False


def assinatura_confere(dados: bytes, tipo: str) -> bool:
    return (
        (tipo == "image/jpeg" and dados.startswith(b"\xff\xd8\xff"))
        or (tipo == "image/png" and dados.startswith(b"\x89PNG\r\n\x1a\n"))
        or (tipo == "image/webp" and dados.startswith(b"RIFF") and dados[8:12] == b"WEBP")
    )


async def baixar_imagem(http: httpx.AsyncClient, url: str, max_bytes: int) -> MidiaBaixada:
    status = None
    try:
        if not url_permitida(url):
            raise Recusa("imagem_indisponivel")
        async with http.stream("GET", url, follow_redirects=False) as resposta:
            status = resposta.status_code
            tipo = resposta.headers.get("content-type", "").split(";")[0].strip().lower()
            if resposta.status_code != 200 or tipo not in {"image/jpeg", "image/png", "image/webp"}:
                raise Recusa("imagem_indisponivel")
            tamanho = resposta.headers.get("content-length")
            if tamanho is not None and not 0 < int(tamanho) <= max_bytes:
                raise Recusa("imagem_indisponivel")
            dados = bytearray()
            async for parte in resposta.aiter_bytes():
                if len(dados) + len(parte) > max_bytes:
                    raise Recusa("imagem_indisponivel")
                dados.extend(parte)
            conteudo = bytes(dados)
            if not assinatura_confere(conteudo, tipo):
                raise Recusa("imagem_indisponivel")
            return MidiaBaixada(conteudo, tipo, hashlib.sha256(conteudo).hexdigest())
    except (httpx.HTTPError, ValueError, Recusa) as exc:
        logger.warning(
            "Falha no download da imagem (%s; status=%s): %s",
            type(exc).__name__,
            status,
            url_para_log(url),
        )
        if isinstance(exc, Recusa):
            raise
        raise Recusa("imagem_indisponivel") from exc
