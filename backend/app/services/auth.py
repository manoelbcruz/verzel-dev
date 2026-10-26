import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from threading import Lock

import anyio
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.core.erros import Recusa
from app.db.transacao import preparar_escrita
from app.models import CarteiraRegistro, Sessao, Usuario
from app.schemas.auth import CadastroEntrada, LoginEntrada

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_hash_ficticio: str | None = None
_trava_hash_ficticio = Lock()


@dataclass(frozen=True)
class UsuarioAutenticado:
    id: int
    nome: str
    email: str
    papel: str
    sessao_id: int


def exigir_papel(usuario: UsuarioAutenticado, papel: str) -> None:
    if usuario.papel != papel:
        raise Recusa("papel_nao_permitido")


def _verificar_senha(hash_senha, senha):
    global _hash_ficticio
    if _hash_ficticio is None:
        # Este helper roda em thread; só a primeira verificação calcula o hash fictício.
        with _trava_hash_ficticio:
            if _hash_ficticio is None:
                _hash_ficticio = hasher.hash(secrets.token_urlsafe(32))
    try:
        return hasher.verify(hash_senha or _hash_ficticio, senha) and hash_senha is not None
    except VerificationError:
        return False


async def _nova_sessao(s, usuario, settings):
    token = secrets.token_urlsafe(32)
    agora = await s.scalar(select(func.clock_timestamp()))
    sessao_id = await s.scalar(
        insert(Sessao)
        .values(
            usuario_id=usuario["id"],
            token_hash=hashlib.sha256(token.encode()).digest(),
            expira_em=agora + timedelta(days=settings.sessao_dias),
        )
        .returning(Sessao.id)
    )
    return UsuarioAutenticado(
        usuario["id"], usuario["nome"], usuario["email"], usuario["papel"], sessao_id
    ), token


async def cadastrar_usuario(recursos, entrada: CadastroEntrada):
    hash_senha = await anyio.to_thread.run_sync(hasher.hash, entrada.senha)
    try:
        async with recursos.fabrica() as s, s.begin():
            await preparar_escrita(s)
            usuario = (
                (
                    await s.execute(
                        insert(Usuario.__table__)
                        .values(
                            nome=entrada.nome,
                            email=entrada.email,
                            senha_hash=hash_senha,
                            papel=entrada.papel,
                        )
                        .returning(Usuario.__table__)
                    )
                )
                .mappings()
                .one()
            )
            await s.execute(insert(CarteiraRegistro).values(usuario_id=usuario["id"]))
            resposta = await _nova_sessao(s, usuario, recursos.settings)
        return resposta
    except IntegrityError as exc:
        if (
            getattr(exc.orig, "sqlstate", None) == "23505"
            and getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            == "uq_usuarios_email"
        ):
            raise Recusa("email_em_uso") from exc
        raise


async def login(recursos, entrada: LoginEntrada):
    async with recursos.fabrica() as s, s.begin():
        usuario = (
            (await s.execute(select(Usuario.__table__).where(Usuario.email == entrada.email)))
            .mappings()
            .one_or_none()
        )
    valido = await anyio.to_thread.run_sync(
        _verificar_senha, usuario["senha_hash"] if usuario else None, entrada.senha
    )
    if not valido:
        raise Recusa("credenciais_invalidas")
    async with recursos.fabrica() as s, s.begin():
        await preparar_escrita(s)
        resposta = await _nova_sessao(s, usuario, recursos.settings)
    return resposta


async def autenticar_token(fabrica, token: str | None) -> UsuarioAutenticado:
    if not token:
        raise Recusa("nao_autenticado")
    async with fabrica() as s, s.begin():
        linha = (
            (
                await s.execute(
                    select(
                        Usuario.id,
                        Usuario.nome,
                        Usuario.email,
                        Usuario.papel,
                        Sessao.id.label("sessao_id"),
                    )
                    .join(Sessao, Sessao.usuario_id == Usuario.id)
                    .where(
                        Sessao.token_hash == hashlib.sha256(token.encode()).digest(),
                        Sessao.revogada_em.is_(None),
                        Sessao.expira_em > func.now(),
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
    if linha is None:
        raise Recusa("nao_autenticado")
    return UsuarioAutenticado(**linha)


async def logout(recursos, token):
    if token:
        async with recursos.fabrica() as s, s.begin():
            await preparar_escrita(s)
            await s.execute(
                update(Sessao)
                .where(
                    Sessao.token_hash == hashlib.sha256(token.encode()).digest(),
                    Sessao.revogada_em.is_(None),
                )
                .values(revogada_em=func.clock_timestamp())
            )
