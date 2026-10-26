from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.erros import Recusa


@dataclass(frozen=True)
class DecisaoLance:
    fim_novo: datetime
    prorrogou: bool


def avaliar_lance(estado, licitante_id, valor, saldo, comprometido, agora) -> DecisaoLance:
    if licitante_id == estado["leiloeiro_id"]:
        raise Recusa("papel_nao_permitido")
    if estado["status"] == "cancelado":
        raise Recusa("lote_cancelado")
    if estado["status"] == "encerrado" or agora >= estado["fim_em"]:
        raise Recusa("lote_encerrado")
    if estado["inicio_em"] > agora:
        raise Recusa("lote_nao_iniciado")
    if estado["lider_id"] == licitante_id:
        raise Recusa("ja_esta_ganhando")
    minimo = (
        estado["lance_inicial_centavos"]
        if estado["lider_id"] is None
        else estado["lance_atual_centavos"] + estado["incremento_centavos"]
    )
    if valor < minimo:
        raise Recusa("abaixo_do_minimo", {"minimo_centavos": minimo})
    disponivel = saldo - comprometido
    if valor > disponivel:
        raise Recusa("saldo_insuficiente", {"disponivel_centavos": disponivel})
    fim = max(estado["fim_em"], agora + timedelta(seconds=120))
    return DecisaoLance(fim, fim > estado["fim_em"])


def validar_datas(condicoes, agora) -> None:
    inicio, fim = condicoes.inicio_em, condicoes.fim_em
    if (
        inicio.tzinfo is None
        or fim.tzinfo is None
        or inicio < agora - timedelta(minutes=5)
        or fim <= agora
        or fim <= inicio
        or fim - inicio > timedelta(days=30)
    ):
        raise Recusa("datas_invalidas")


def calcular_fase(status, inicio_em, fim_em, agora) -> str:
    if status == "cancelado":
        return "cancelado"
    if status == "encerrado" or agora >= fim_em:
        return "encerrado"
    return "ao_vivo" if agora >= inicio_em else "agendado"
