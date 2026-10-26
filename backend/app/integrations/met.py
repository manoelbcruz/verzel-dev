import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import anyio
import httpx

from app.core.erros import ApiExternaIndisponivel, Recusa
from app.integrations.imagens import url_para_log, url_permitida
from app.schemas.itens import ItemExterno, PaginaItens
from app.services.cadeia import sanitizar

logger = logging.getLogger(__name__)


def registrar_falha(url, exc):
    status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
    logger.warning(
        "Falha no Met (%s; status=%s): %s", type(exc).__name__, status, url_para_log(url)
    )


@dataclass(frozen=True)
class RegistroCache:
    dados: dict
    obtido_em: datetime


class CacheMet(Protocol):
    async def obter(self, chave: str) -> RegistroCache | None: ...
    async def guardar(self, chave: str, dados: dict) -> None: ...


class CacheMetMemoria:
    def __init__(self):
        self.registros: dict[str, RegistroCache] = {}

    async def obter(self, chave):
        return self.registros.get(chave)

    async def guardar(self, chave, dados):
        self.registros[chave] = RegistroCache(dados, datetime.now(UTC))


def _valido(registro, horas):
    return registro is not None and registro.obtido_em > datetime.now(UTC) - timedelta(hours=horas)


def normalizar_item(objeto, item_id):
    imagem = objeto.get("primaryImageSmall")
    if (
        objeto.get("isPublicDomain") is not True
        or not isinstance(imagem, str)
        or not url_permitida(imagem)
    ):
        return {"erro": "item_inelegivel"}
    campos = {
        "artista": "artistDisplayName",
        "data": "objectDate",
        "cultura": "culture",
        "tecnica": "medium",
        "dimensoes": "dimensions",
        "departamento": "department",
        "classificacao": "classification",
        "url_objeto": "objectURL",
        "credito": "creditLine",
    }
    atributos = {
        destino: sanitizar(str(objeto.get(origem) or "")) for destino, origem in campos.items()
    }
    atributos["licenca"] = "Domínio público (Met Open Access, CC0)"
    return {
        "item": ItemExterno(
            id_externo=str(item_id),
            titulo=sanitizar(str(objeto.get("title") or ""), 300) or "Sem título",
            atributos=atributos,
            imagem_url_externa=imagem,
        ).model_dump()
    }


class MetCliente:
    def __init__(self, http: httpx.AsyncClient, cache: CacheMet, base_url: str):
        self.http, self.cache, self.base_url = http, cache, base_url.rstrip("/")

    async def obter_item(self, item_id: str) -> ItemExterno:
        chave = f"objeto:v1:{item_id}"
        cache = await self.cache.obter(chave)
        if _valido(cache, 24):
            dados = cache.dados
        else:
            url = f"{self.base_url}/v1/objects/{item_id}"
            try:
                resposta = await self.http.get(url)
                if resposta.status_code == 404:
                    logger.warning("Item não encontrado no Met (status=404): %s", url_para_log(url))
                    dados = {"erro": "item_nao_encontrado"}
                else:
                    resposta.raise_for_status()
                    objeto = resposta.json()
                    if not isinstance(objeto, dict):
                        raise ValueError("Objeto Met inválido")
                    dados = normalizar_item(objeto, item_id)
            except (httpx.HTTPError, ValueError) as exc:
                registrar_falha(url, exc)
                if cache is None:
                    raise ApiExternaIndisponivel() from None
                dados = cache.dados
            else:
                await self.cache.guardar(chave, dados)
        if "erro" in dados:
            raise Recusa(dados["erro"])
        return ItemExterno.model_validate(dados["item"])

    async def buscar(self, q: str, pagina: int = 1) -> PaginaItens:
        q = " ".join(q.strip().lower().split())
        chave = f"busca:v1:{q}"
        cache = await self.cache.obter(chave)
        origem = "cache"
        if _valido(cache, 1):
            ids = cache.dados["ids"]
        else:
            url = f"{self.base_url}/v1.1/search"
            try:
                resposta = await self.http.get(url, params={"q": q, "hasImages": "true"})
                resposta.raise_for_status()
                ids = resposta.json()["objectIDs"] or []
                if not isinstance(ids, list) or any(
                    type(item) is not int or item < 1 for item in ids
                ):
                    raise ValueError("Lista Met inválida")
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                registrar_falha(url, exc)
                if cache is None:
                    raise ApiExternaIndisponivel() from None
                ids = cache.dados["ids"]
            else:
                origem = "api"
                await self.cache.guardar(chave, {"ids": ids})
        pagina_ids = ids[(pagina - 1) * 20 : pagina * 20]
        itens = [None] * len(pagina_ids)
        parcial = False
        limite = anyio.Semaphore(6)

        async def detalhar(posicao, item_id):
            nonlocal parcial
            async with limite:
                try:
                    itens[posicao] = await self.obter_item(str(item_id))
                except ApiExternaIndisponivel:
                    parcial = True
                except Recusa as exc:
                    if exc.codigo not in {"item_inelegivel", "item_nao_encontrado"}:
                        raise

        with anyio.move_on_after(10) as prazo:
            async with anyio.create_task_group() as grupo:
                for posicao, item_id in enumerate(pagina_ids):
                    grupo.start_soon(detalhar, posicao, item_id)
        if prazo.cancel_called:
            logger.warning(
                "Prazo da página do Met excedido (TimeoutError): %s",
                url_para_log(f"{self.base_url}/v1.1/search"),
            )
        return PaginaItens(
            pagina=pagina,
            total_ids=len(ids),
            tem_mais=pagina * 20 < len(ids),
            parcial=parcial or prazo.cancel_called,
            origem=origem,
            itens=[item for item in itens if item is not None],
        )
