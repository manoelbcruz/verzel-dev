from typing import Literal

from app.schemas.comum import Schema


class ItemExterno(Schema):
    id_externo: str
    titulo: str
    atributos: dict[str, str]
    imagem_url_externa: str


class PaginaItens(Schema):
    pagina: int
    por_pagina: int = 20
    total_ids: int
    tem_mais: bool
    parcial: bool
    origem: Literal["api", "cache"]
    itens: list[ItemExterno]
