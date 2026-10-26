import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID

from app.core.chaves import Chaves

ZERO_MAC = bytes(32)


def canon(corpo: dict) -> bytes:
    return json.dumps(
        corpo, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def iso(data: datetime) -> str:
    if data.tzinfo is None or data.utcoffset() is None:
        raise ValueError("Data sem fuso")
    return data.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def pseudonimo(chave: bytes, public_id: UUID, usuario_id: int) -> str:
    mensagem = f"casa-de-leiloes/pseudonimo/v1|{public_id}|{usuario_id}".encode()
    resumo = hmac.digest(chave, mensagem, "sha256")[:16]
    return base64.b32encode(resumo).decode().lower().rstrip("=")


def campos_evento(lote, evento, midia_sha256, liquidacao, chaves: Chaves, fim_final) -> dict:
    match evento["tipo"]:
        case "publicacao":
            return {
                "leiloeiro": lote["leiloeiro_id"],
                "item": {
                    "fonte": lote["item_fonte"],
                    "id_externo": lote["item_id_externo"],
                    "titulo": lote["titulo"],
                    "atributos": lote["atributos"],
                },
                "midia_sha256": midia_sha256,
                "lance_inicial": lote["lance_inicial_centavos"],
                "incremento": lote["incremento_centavos"],
                "inicio": iso(lote["inicio_em"]),
                "fim": iso(lote["fim_original_em"]),
            }
        case "lance":
            return {
                "licitante": pseudonimo(
                    chaves.privacidade, lote["public_id"], evento["licitante_id"]
                ),
                "valor": evento["valor_centavos"],
                "fim_anterior": iso(evento["fim_anterior"]),
                "fim_novo": iso(evento["fim_novo"]),
            }
        case "cancelamento":
            return {}
        case "encerramento":
            vencedor = liquidacao["vencedor_id"]
            return {
                "resultado": liquidacao["resultado"],
                "vencedor": pseudonimo(chaves.privacidade, lote["public_id"], vencedor)
                if vencedor is not None
                else None,
                "valor": liquidacao["valor_centavos"],
                "comprovante": liquidacao["comprovante_codigo"],
                "fim": iso(fim_final),
            }
        case _:
            raise ValueError("Tipo de evento desconhecido")


def envelope(lote, evento, anterior, midia_sha256, liquidacao, chaves, fim_final) -> dict:
    return {
        "dominio": "casa-de-leiloes/evento",
        "v": 1,
        "lote": str(lote["public_id"]),
        "seq": evento["seq"],
        "tipo": evento["tipo"],
        "instante": iso(evento["instante"]),
        "anterior": anterior.hex(),
        **campos_evento(lote, evento, midia_sha256, liquidacao, chaves, fim_final),
    }


def mac_evento(lote, evento, anterior, midia_sha256, liquidacao, chaves, fim_final) -> bytes:
    return hmac.digest(
        chaves.integridade,
        canon(envelope(lote, evento, anterior, midia_sha256, liquidacao, chaves, fim_final)),
        hashlib.sha256,
    )


def assinar_cabeca(chave: bytes, public_id: UUID, seq: int, ponta: bytes) -> bytes:
    return hmac.digest(
        chave,
        canon(
            {
                "dominio": "casa-de-leiloes/cabeca",
                "v": 1,
                "lote": str(public_id),
                "seq": seq,
                "ponta": ponta.hex(),
            }
        ),
        "sha256",
    )


def sanitizar(texto: str, limite: int = 500) -> str:
    return texto.replace("\x00", "").strip()[:limite]
