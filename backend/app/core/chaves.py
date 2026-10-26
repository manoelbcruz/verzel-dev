import logging
import re
from dataclasses import dataclass, field

from app.core.config import Settings

logger = logging.getLogger(__name__)
CHAVES_DE_DESENVOLVIMENTO = (bytes.fromhex("1" * 64), bytes.fromhex("2" * 64))


class ConfiguracaoInvalida(ValueError):
    pass


@dataclass(frozen=True)
class Chaves:
    integridade: bytes = field(repr=False)
    privacidade: bytes = field(repr=False)


def carregar_chaves(settings: Settings) -> Chaves:
    valores = []
    for nome in ("chave_integridade", "chave_privacidade"):
        segredo = getattr(settings, nome)
        valor = segredo.get_secret_value() if segredo is not None else ""
        if not re.fullmatch(r"(?:[0-9a-fA-F]{2}){32,}", valor):
            raise ConfiguracaoInvalida(
                f"Defina {nome.upper()} com ao menos 32 bytes em hexadecimal."
            )
        valores.append(bytes.fromhex(valor))
    desenvolvimento = any(valor in CHAVES_DE_DESENVOLVIMENTO for valor in valores)
    if settings.producao and (valores[0] == valores[1] or desenvolvimento):
        raise ConfiguracaoInvalida(
            "Defina CHAVE_INTEGRIDADE e CHAVE_PRIVACIDADE distintas e privadas em produção."
        )
    if desenvolvimento:
        logger.warning("Chaves públicas de desenvolvimento em uso; produção recusa essas chaves.")
    return Chaves(*valores)
