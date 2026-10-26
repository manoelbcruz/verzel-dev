import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "url",
    [
        "postgres://u:p@h:5432/db",
        "postgresql://u:p@h:5432/db",
        "postgresql+psycopg://u:p@h:5432/db",
    ],
)
def test_database_url_uses_psycopg_driver(url: str) -> None:
    settings = Settings(_env_file=None, database_url=url)

    assert settings.database_url == "postgresql+psycopg://u:p@h:5432/db"


@pytest.mark.parametrize(
    "raw",
    ["http://a.com, http://b.com/", '["http://a.com/", "http://b.com"]'],
)
def test_cors_origins_accepts_comma_separated_or_json(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", raw)

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://a.com", "http://b.com"]


def test_unknown_env_vars_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOME_FUTURE_SETTING", "x")

    Settings(_env_file=None)


@pytest.mark.parametrize("valor", [None, "ab", "x" * 64, "ab " * 32])
def test_chaves_invalidas(settings_teste, valor):
    from pydantic import SecretStr

    from app.core.chaves import ConfiguracaoInvalida, carregar_chaves

    settings_teste.chave_integridade = SecretStr(valor) if valor is not None else None
    with pytest.raises(ConfiguracaoInvalida, match="CHAVE_INTEGRIDADE"):
        carregar_chaves(settings_teste)


def test_chaves_producao(settings_teste):
    from pydantic import SecretStr

    from app.core.chaves import CHAVES_DE_DESENVOLVIMENTO, ConfiguracaoInvalida, carregar_chaves

    settings_teste.environment = "production"
    settings_teste.chave_privacidade = settings_teste.chave_integridade
    with pytest.raises(ConfiguracaoInvalida):
        carregar_chaves(settings_teste)
    settings_teste.chave_integridade = SecretStr(CHAVES_DE_DESENVOLVIMENTO[0].hex())
    settings_teste.chave_privacidade = SecretStr(CHAVES_DE_DESENVOLVIMENTO[1].hex())
    with pytest.raises(ConfiguracaoInvalida):
        carregar_chaves(settings_teste)
    settings_teste.environment = "development"
    assert repr(carregar_chaves(settings_teste)) == "Chaves()"
    assert settings_teste.cookie_secure is False


@pytest.mark.anyio
async def test_lifespan_exige_chaves(settings_teste):
    from app.core.chaves import ConfiguracaoInvalida
    from app.main import create_app

    settings_teste.chave_integridade = None
    app = create_app(settings_teste, iniciar_worker=False)
    with pytest.raises(ConfiguracaoInvalida):
        async with app.router.lifespan_context(app):
            pytest.fail("Não deveria iniciar sem chaves")


@pytest.mark.parametrize("valor", ["production", "Production", " PRODUCTION "])
def test_ambiente_producao_normalizado(valor):
    settings = Settings(_env_file=None, environment=valor)
    assert settings.environment == "production"
    assert settings.cookie_secure is True


@pytest.mark.parametrize("valor", ["prod", "staging", "", None])
def test_ambiente_invalido_recusado(valor):
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="environment"):
        Settings(_env_file=None, environment=valor)


def test_ambiente_desenvolvimento_normalizado():
    settings = Settings(_env_file=None, environment=" Development ")
    assert settings.environment == "development" and not settings.cookie_secure
