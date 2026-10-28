import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MAX_CENTAVOS = 1_000_000_000_000
MAX_DEPOSITO = 100_000_000
LIMITE_SALDO_DEPOSITO = 1_000_000_000_000
JS_MAX_SEGURO = 9_007_199_254_740_991
SENHA_DEMO_PUBLICA = "leilao-demo-2026"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True
    )

    database_url: str = "postgresql+psycopg://leilao:leilao@localhost:5432/leilao"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    environment: Literal["development", "production"] = "development"
    chave_integridade: SecretStr | None = None
    chave_privacidade: SecretStr | None = None
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    met_base_url: str = "https://collectionapi.metmuseum.org/public/collection"
    imagem_max_bytes: int = Field(default=5_000_000, ge=1, le=5_000_000)
    sessao_dias: int = Field(default=7, ge=1)
    encerramento_intervalo_s: float = Field(default=1.0, gt=0)
    seed_demo: bool = False
    seed_intervalo_s: float = Field(default=3600.0, gt=0)
    senha_demo: SecretStr = SecretStr(SENHA_DEMO_PUBLICA)
    frontend_dist: str | None = None
    ws_max_conexoes: int = Field(default=500, ge=1)
    ws_tamanho_fila: int = Field(default=64, ge=1)
    ws_intervalo_ping_s: float = Field(default=25.0, gt=0)
    ws_revalidar_s: float = Field(default=300.0, gt=0)

    @field_validator("senha_demo")
    @classmethod
    def validar_senha_demo(cls, value: SecretStr) -> SecretStr:
        if not 8 <= len(value.get_secret_value()) <= 128:
            raise ValueError("SENHA_DEMO deve ter entre 8 e 128 caracteres")
        return value

    @field_validator("frontend_dist", mode="before")
    @classmethod
    def normalizar_frontend_dist(cls, value: object) -> object:
        return value.strip() or None if isinstance(value, str) else value

    @property
    def producao(self) -> bool:
        return self.environment == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.producao

    @field_validator("environment", mode="before")
    @classmethod
    def normalizar_ambiente(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Provedores gerenciados entregam postgres:// ou postgresql:// sem o driver.
        value = value.strip()
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        # Aceita lista JSON ou separada por vírgula, como se preenche num painel de deploy.
        if isinstance(value, str):
            origins = json.loads(value) if value.lstrip().startswith("[") else value.split(",")
        else:
            origins = value
        if isinstance(origins, list):
            # O navegador manda o Origin sem barra final.
            return [str(origin).strip().rstrip("/") for origin in origins if str(origin).strip()]
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
