import hmac
from dataclasses import dataclass, field
from datetime import timedelta

from app.core.chaves import Chaves
from app.core.erros import ErroIntegridade
from app.services.cadeia import ZERO_MAC, assinar_cabeca, mac_evento, pseudonimo

MENSAGENS = {
    "midia_divergente": "Os bytes da imagem não conferem com seu resumo.",
    "sequencia_quebrada": "A sequência de eventos não é contínua.",
    "gramatica_invalida": "A ordem dos tipos de evento é inválida.",
    "pseudonimo_divergente": "O pseudônimo não confere com o participante.",
    "mac_invalido": "A autenticação do evento não confere.",
    "transicao_invalida": "A transição entre eventos viola as regras do lote.",
    "cabeca_invalida": "A cabeça autenticada não confere com os eventos.",
    "projecao_divergente": "O estado do lote não confere com seu histórico.",
    "reserva_divergente": "A reserva não confere com o líder e o valor do lance.",
    "liquidacao_divergente": "A liquidação ou seus lançamentos não conferem.",
}


@dataclass
class DadosAuditoria:
    lote: dict
    midia_sha256: str
    midia_sha256_calculado: str
    eventos: list[dict]
    reserva: dict | None = None
    liquidacao: dict | None = None
    lancamentos: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Falha:
    codigo: str
    seq: int | None
    mensagem: str


@dataclass(frozen=True)
class Veredito:
    integro: bool
    eventos_verificados: int
    total_eventos: int
    falha: Falha | None


def _reserva_confere(dados, lider, valor, status):
    reserva = dados.reserva
    if status == "publicado" and lider is not None:
        return reserva is not None and (
            reserva["lote_id"] == dados.lote["id"]
            and reserva["usuario_id"] == lider
            and reserva["valor_centavos"] == valor
        )
    return reserva is None


def _projecao_confere(lote, lider, valor, total, fim, status):
    return all(
        lote[campo] == esperado
        for campo, esperado in {
            "lider_id": lider,
            "lance_atual_centavos": valor,
            "total_lances": total,
            "fim_em": fim,
            "status": status,
        }.items()
    )


def verificar(dados: DadosAuditoria, chaves: Chaves) -> Veredito:
    lote = dados.lote
    eventos = dados.eventos
    verificados = 0

    def falha(codigo, seq=None):
        return Veredito(False, verificados, len(eventos), Falha(codigo, seq, MENSAGENS[codigo]))

    if dados.midia_sha256_calculado != dados.midia_sha256:
        return falha("midia_divergente")
    anterior = ZERO_MAC
    lider, valor, total, status = None, None, 0, "publicado"
    fim = lote["fim_original_em"]
    instante_anterior = None
    for seq, evento in enumerate(eventos, 1):
        if evento["seq"] != seq:
            return falha("sequencia_quebrada", seq)
        tipo = evento["tipo"]
        if (
            (seq == 1 and tipo != "publicacao")
            or (seq > 1 and tipo == "publicacao")
            or status != "publicado"
            or tipo not in {"publicacao", "lance", "cancelamento", "encerramento"}
            or (tipo == "cancelamento" and total != 0)
        ):
            return falha("gramatica_invalida", seq)
        if tipo == "lance" and evento["pseudonimo"] != pseudonimo(
            chaves.privacidade, lote["public_id"], evento["licitante_id"]
        ):
            return falha("pseudonimo_divergente", seq)
        if tipo == "encerramento" and dados.liquidacao is None:
            return falha("liquidacao_divergente", seq)
        esperado = mac_evento(
            lote, evento, anterior, dados.midia_sha256, dados.liquidacao, chaves, fim
        )
        if not hmac.compare_digest(evento["mac"], esperado):
            return falha("mac_invalido", seq)
        if instante_anterior is not None and evento["instante"] < instante_anterior:
            return falha("transicao_invalida", seq)
        if tipo == "lance":
            minimo = (
                lote["lance_inicial_centavos"]
                if total == 0
                else valor + lote["incremento_centavos"]
            )
            if (
                evento["fim_anterior"] != fim
                or evento["valor_centavos"] < minimo
                or evento["licitante_id"] == lider
                or evento["licitante_id"] == lote["leiloeiro_id"]
                or not lote["inicio_em"] <= evento["instante"] < evento["fim_anterior"]
                or evento["fim_novo"] != max(fim, evento["instante"] + timedelta(seconds=120))
            ):
                return falha("transicao_invalida", seq)
            lider, valor, fim = evento["licitante_id"], evento["valor_centavos"], evento["fim_novo"]
            total += 1
        elif tipo == "encerramento":
            if evento["instante"] < fim:
                return falha("transicao_invalida", seq)
            status = "encerrado"
        elif tipo == "cancelamento":
            status = "cancelado"
        anterior, instante_anterior = evento["mac"], evento["instante"]
        verificados += 1
    if (
        not eventos
        or lote["cabeca_seq"] != len(eventos)
        or not hmac.compare_digest(
            lote["cabeca_assinatura"],
            assinar_cabeca(chaves.integridade, lote["public_id"], len(eventos), anterior),
        )
    ):
        return falha("cabeca_invalida")
    if not _projecao_confere(lote, lider, valor, total, fim, status):
        return falha("projecao_divergente")
    if not _reserva_confere(dados, lider, valor, status):
        return falha("reserva_divergente")
    liquidacao = dados.liquidacao
    if status != "encerrado":
        if liquidacao is not None or dados.lancamentos:
            return falha("liquidacao_divergente")
    elif liquidacao is None or liquidacao["lote_id"] != lote["id"]:
        return falha("liquidacao_divergente")
    elif lider is None:
        if (
            liquidacao["resultado"] != "sem_lances"
            or dados.lancamentos
            or any(
                liquidacao[campo] is not None
                for campo in (
                    "vencedor_id",
                    "vencedor_pseudonimo",
                    "valor_centavos",
                    "comprovante_codigo",
                )
            )
        ):
            return falha("liquidacao_divergente")
    else:
        esperados = {
            (lider, "arremate_debito", -valor, liquidacao["id"]),
            (lote["leiloeiro_id"], "arremate_credito", valor, liquidacao["id"]),
        }
        obtidos = {
            (item["usuario_id"], item["tipo"], item["valor_centavos"], item["liquidacao_id"])
            for item in dados.lancamentos
        }
        if (
            liquidacao["resultado"] != "arrematado"
            or liquidacao["vencedor_id"] != lider
            or liquidacao["valor_centavos"] != valor
            or not liquidacao["comprovante_codigo"]
            or liquidacao["vencedor_pseudonimo"]
            != pseudonimo(chaves.privacidade, lote["public_id"], lider)
            or len(dados.lancamentos) != 2
            or obtidos != esperados
        ):
            return falha("liquidacao_divergente")
    return Veredito(True, verificados, len(eventos), None)


def conferir_ponta(dados: DadosAuditoria, chaves: Chaves) -> None:
    """Confere toda a cadeia antes de aceitar uma escrita sobre o lote."""
    if max((evento["seq"] for evento in dados.eventos), default=0) != dados.lote["cabeca_seq"]:
        raise ErroIntegridade("cabeca_invalida", dados.lote["cabeca_seq"])
    veredito = verificar(dados, chaves)
    if not veredito.integro:
        raise ErroIntegridade(veredito.falha.codigo, veredito.falha.seq)
