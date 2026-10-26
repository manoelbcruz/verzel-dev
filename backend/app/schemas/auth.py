import re
from typing import Annotated, Literal

from pydantic import Field, field_validator

from app.schemas.comum import Schema, Texto

Senha = Annotated[Texto, Field(min_length=8, max_length=128)]
Papel = Literal["leiloeiro", "licitante"]


class LoginEntrada(Schema):
    email: Texto
    senha: Senha

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor):
        valor = valor.strip().lower()
        if len(valor) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", valor):
            raise ValueError("E-mail inválido")
        return valor


class CadastroEntrada(LoginEntrada):
    nome: Texto
    papel: Papel

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor):
        valor = valor.strip()
        if not 1 <= len(valor) <= 80:
            raise ValueError("Nome deve ter entre 1 e 80 caracteres")
        return valor


class UsuarioSaida(Schema):
    nome: str
    email: str
    papel: Papel
