import re
from datetime import UTC
from typing import Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    PrivateAttr,
)

from app.core.config import MAX_CENTAVOS
from app.core.erros import Recusa


def recusar_nul(valor: str) -> str:
    if "\x00" in valor:
        raise ValueError("Texto não pode conter o caractere NUL")
    return valor


Texto = Annotated[str, AfterValidator(recusar_nul)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]
# token_urlsafe(16): 128 bits, 22 caracteres base64url, sem padding.
CodigoComprovante = Annotated[
    str, Field(pattern=r"^[A-Za-z0-9_-]{21}[AQgw]$", min_length=22, max_length=22)
]
Centavos = Annotated[int, Field(strict=True, ge=1, le=MAX_CENTAVOS)]
DataUTC = Annotated[
    AwareDatetime,
    PlainSerializer(
        lambda valor: valor.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        return_type=str,
        when_used="json",
    ),
]
IdItem = Annotated[str, Field(pattern=r"^[1-9][0-9]{0,9}$")]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class SaidaIdempotente(Schema):
    # Metadados do transporte; nunca integram o corpo público ou o OpenAPI.
    _repetida: bool = PrivateAttr(default=False)
    _status_http: int = PrivateAttr(default=201)

    @property
    def repetida(self) -> bool:
        return self._repetida

    @property
    def status_http(self) -> int:
        return self._status_http

    @property
    def resposta(self) -> dict:
        return self.model_dump(mode="json")


def validar_chave(chave: str | None) -> str:
    if chave is None or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", chave):
        raise Recusa("chave_idempotencia_invalida")
    return chave
