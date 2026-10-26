from datetime import timedelta, timezone
from uuid import uuid4

from app.core.chaves import Chaves
from app.services.cadeia import ZERO_MAC, assinar_cabeca, canon, envelope, iso, pseudonimo
from tests.apoio import AGORA, dados_publicados


def test_vetor_fixo():
    # Vetor público de teste; não é chave de ambiente nem credencial.
    chaves = Chaves(bytes(range(32)), bytes(range(32, 64)))
    dados = dados_publicados(chaves)
    assert (
        dados.eventos[0]["mac"].hex()
        == "37b1791ff18760e846d0a3f7d4d4807b108aae5b5ee92e3eb71013cb1fff7db0"
    )
    corpo = envelope(
        dados.lote,
        dados.eventos[0],
        ZERO_MAC,
        dados.midia_sha256,
        None,
        chaves,
        dados.lote["fim_em"],
    )
    assert corpo["anterior"] == "0" * 64
    assert corpo["instante"] == "2026-10-25T12:00:00.000000Z"
    assert (
        assinar_cabeca(chaves.integridade, dados.lote["public_id"], 1, dados.eventos[0]["mac"])
        != dados.eventos[0]["mac"]
    )


def test_canonicalizacao():
    assert canon({"b": 2, "a": "ç"}) == canon({"a": "ç", "b": 2})
    assert iso(AGORA.astimezone(timezone(timedelta(hours=-3)))) == "2026-10-25T12:00:00.000000Z"


def test_pseudonimo(chaves):
    lote = uuid4()
    atual = pseudonimo(chaves.privacidade, lote, 2)
    assert len(atual) == 26
    assert atual == pseudonimo(chaves.privacidade, lote, 2)
    assert atual != pseudonimo(chaves.privacidade, uuid4(), 2)
    assert atual != pseudonimo(chaves.integridade, lote, 2)
    assert atual != pseudonimo(chaves.privacidade, lote, 3)
