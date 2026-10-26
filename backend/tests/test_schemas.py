import pytest
from pydantic import ValidationError

from app.core.config import MAX_CENTAVOS, MAX_DEPOSITO
from app.core.erros import Recusa
from app.schemas.carteira import DepositoEntrada
from app.schemas.comum import validar_chave
from app.schemas.lotes import LanceEntrada, LoteEntrada


@pytest.mark.parametrize("valor", [1.5, 100.0, "100", True, 0, -1, MAX_CENTAVOS + 1, None])
def test_centavos_estritos(valor):
    with pytest.raises(ValidationError):
        LanceEntrada(valor_centavos=valor)


def test_teto_deposito_e_extra():
    with pytest.raises(ValidationError):
        DepositoEntrada(valor_centavos=MAX_DEPOSITO + 1)
    with pytest.raises(ValidationError):
        LanceEntrada(valor_centavos=100, usuario_id=1)


def test_data_sem_fuso():
    with pytest.raises(ValidationError):
        LoteEntrada(
            item_id_externo="123",
            lance_inicial_centavos=100,
            incremento_centavos=10,
            inicio_em="2026-10-25T12:00:00",
            fim_em="2026-10-25T13:00:00Z",
        )


@pytest.mark.parametrize(
    "chave", [None, "curta", "x" * 129, "invalida!", "espaco aqui", "a" * 8 + "\n"]
)
def test_chave_invalida(chave):
    with pytest.raises(Recusa) as erro:
        validar_chave(chave)
    assert erro.value.codigo == "chave_idempotencia_invalida"


def test_chave_valida():
    assert validar_chave("chave_01-OK") == "chave_01-OK"


def test_metadados_idempotencia_nao_vazam_no_corpo():
    from uuid import uuid4

    from app.schemas.lotes import LanceAceito
    from app.services.idempotencia import RespostaIdempotente, materializar
    from tests.apoio import AGORA

    original = LanceAceito(
        lote_id=uuid4(),
        seq=2,
        valor_centavos=100,
        instante=AGORA,
        fim_em=AGORA,
        prorrogou=False,
        lider_pseudonimo="pseudonimo-publico",
        proximo_lance_minimo_centavos=110,
    )
    corpo = original.model_dump(mode="json")
    repetida = materializar(RespostaIdempotente(201, corpo, True), LanceAceito)
    assert isinstance(repetida, LanceAceito)
    assert repetida.repetida and repetida.status_http == 201
    assert repetida.model_dump(mode="json") == corpo
    assert set(LanceAceito.model_json_schema()["properties"]) == set(corpo)


@pytest.mark.parametrize("campo", ["nome", "email", "senha"])
def test_textos_cadastro_recusam_nul(campo):
    import secrets

    from app.schemas.auth import CadastroEntrada

    entrada = {
        "nome": "Pessoa",
        "email": "pessoa@example.test",
        "senha": secrets.token_urlsafe(18),
        "papel": "licitante",
    }
    entrada[campo] += "\x00"
    with pytest.raises(ValidationError):
        CadastroEntrada(**entrada)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "rota,campo",
    [
        ("/api/lotes?q=%00", None),
        ("/api/leiloeiro/itens?q=%00", None),
        ("/api/midias/%00", None),
        ("/api/comprovantes/%00", None),
        ("/api/auth/login", "email"),
        ("/api/auth/login", "senha"),
        ("/api/auth/cadastro", "nome"),
        ("/api/auth/cadastro", "email"),
        ("/api/auth/cadastro", "senha"),
    ],
)
async def test_http_recusa_nul_antes_do_servico(settings_teste, rota, campo):
    import secrets
    from types import SimpleNamespace

    import httpx

    from app.api.deps import leiloeiro, obter_recursos
    from app.main import create_app
    from app.services.auth import UsuarioAutenticado

    app = create_app(recursos=SimpleNamespace(settings=settings_teste))

    async def recursos_teste():
        return app.state.recursos

    async def leiloeiro_teste():
        return UsuarioAutenticado(1, "Pessoa", "pessoa@example.test", "leiloeiro", 1)

    app.dependency_overrides[leiloeiro] = leiloeiro_teste
    app.dependency_overrides[obter_recursos] = recursos_teste
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Origin": "http://test"},
    ) as cliente:
        if campo:
            entrada = {"email": "pessoa@example.test", "senha": secrets.token_urlsafe(18)}
            if rota.endswith("cadastro"):
                entrada.update(nome="Pessoa", papel="licitante")
            entrada[campo] += "\x00"
            resposta = await cliente.post(rota, json=entrada)
        else:
            resposta = await cliente.get(rota)
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "entrada_invalida"


def test_formato_exato_comprovante_e_hash():
    from pydantic import TypeAdapter

    from app.schemas.comum import CodigoComprovante, Sha256
    from app.services.liquidacao import gerar_codigo_comprovante

    codigo = TypeAdapter(CodigoComprovante)
    for _ in range(100):
        codigo.validate_python(gerar_codigo_comprovante())
    for valor in ["a" * 22, "a" * 23, "a" * 21 + "A\n", "codigo\x00"]:
        with pytest.raises(ValidationError):
            codigo.validate_python(valor)
    sha = TypeAdapter(Sha256)
    assert sha.validate_python("a" * 64) == "a" * 64
    for valor in ["A" * 64, "a" * 63, "a" * 64 + "\n", "a" * 63 + "\x00"]:
        with pytest.raises(ValidationError):
            sha.validate_python(valor)
