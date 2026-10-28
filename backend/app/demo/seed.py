import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta
from types import SimpleNamespace

import anyio
from sqlalchemy import func, select, text

from app.core.config import LIMITE_SALDO_DEPOSITO
from app.core.erros import Recusa
from app.db.transacao import leitura_consistente
from app.demo.catalogo import (
    CATALOGO,
    USUARIOS_DEMO,
    Criar,
    LoteExistente,
    carregar_item,
    deposito_necessario,
    planejar,
)
from app.models import Liquidacao, Lote, Usuario
from app.schemas.auth import CadastroEntrada
from app.schemas.demo import ContaDemo
from app.services.auth import UsuarioAutenticado, _verificar_senha, cadastrar_usuario, logout
from app.services.carteira import depositar
from app.services.consultas import consultar_carteira
from app.services.lances import dar_lance
from app.services.lotes import publicar_lote

logger = logging.getLogger(__name__)
TRAVA_DEMO = 742018001
PRAZO_LIBERAR_TRAVA = 5


@dataclass
class ResumoSeed:
    usuarios_criados: int = 0
    depositos: int = 0
    lotes_criados: int = 0
    lances: int = 0
    trava_obtida: bool = False
    erro: str | None = None


async def _ler_usuario(recursos, email):
    async with recursos.fabrica() as s, s.begin():
        return (
            (await s.execute(select(Usuario.__table__).where(Usuario.email == email)))
            .mappings()
            .one_or_none()
        )


async def _usuarios(recursos, resumo):
    senha = recursos.settings.senha_demo.get_secret_value()
    existentes, usuarios, conferidas = {}, {}, []
    divergente = False
    # Confere todas as contas já existentes antes de criar ou movimentar qualquer coisa.
    for conta in USUARIOS_DEMO:
        existente = await _ler_usuario(recursos, conta.email)
        if existente is None:
            continue
        valida = existente["papel"] == conta.papel and await anyio.to_thread.run_sync(
            _verificar_senha, existente["senha_hash"], senha
        )
        if not valida:
            logger.error("Conta de demonstração com papel ou senha divergente: %s", conta.chave)
            divergente = True
            continue
        existentes[conta.chave] = existente
        conferidas.append(ContaDemo(email=conta.email, papel=conta.papel, rotulo=conta.rotulo))
    recursos.contas_demo = conferidas
    if divergente:
        resumo.erro = "conta_demo_divergente"
        return None
    for conta in USUARIOS_DEMO:
        existente = existentes.get(conta.chave)
        if existente is None:
            try:
                usuario, token = await cadastrar_usuario(
                    recursos,
                    CadastroEntrada(
                        nome=conta.nome,
                        email=conta.email,
                        senha=senha,
                        papel=conta.papel,
                    ),
                )
                sessao_id = await logout(recursos, token)
                if sessao_id is not None:
                    recursos.central.encerrar_sessao(sessao_id)
                resumo.usuarios_criados += 1
            except Recusa as exc:
                if exc.codigo != "email_em_uso":
                    raise
            existente = await _ler_usuario(recursos, conta.email)
            if existente["papel"] != conta.papel or not await anyio.to_thread.run_sync(
                _verificar_senha, existente["senha_hash"], senha
            ):
                logger.error("Conta de demonstração divergente após cadastro: %s", conta.chave)
                resumo.erro = "conta_demo_divergente"
                return None
            conferidas.append(ContaDemo(email=conta.email, papel=conta.papel, rotulo=conta.rotulo))
        usuarios[conta.chave] = UsuarioAutenticado(
            existente["id"], existente["nome"], existente["email"], existente["papel"], 0
        )
    recursos.contas_demo = [
        next(c for c in conferidas if c.email == conta.email) for conta in USUARIOS_DEMO
    ]
    return usuarios


async def _semear(recursos, resumo):
    usuarios = await _usuarios(recursos, resumo)
    if usuarios is None:
        return
    for chave in ("comprador1", "comprador2"):
        carteira = await consultar_carteira(recursos, usuarios[chave])
        valor = min(
            deposito_necessario(carteira.saldo_total_centavos, carteira.comprometido_centavos),
            max(0, LIMITE_SALDO_DEPOSITO - carteira.saldo_total_centavos),
        )
        if valor:
            try:
                await depositar(recursos, usuarios[chave], valor, "demo-" + secrets.token_hex(12))
                resumo.depositos += 1
            except Recusa as exc:
                logger.warning("Depósito do seed recusado para %s: %s", chave, exc.codigo)
    async with leitura_consistente(recursos.fabrica) as s:
        agora = await s.scalar(select(func.clock_timestamp()))
        linhas = (
            (
                await s.execute(
                    select(
                        Lote.item_id_externo,
                        Lote.public_id,
                        Lote.status,
                        Lote.inicio_em,
                        Lote.fim_em,
                        Lote.total_lances,
                        Liquidacao.resultado,
                    )
                    .outerjoin(Liquidacao, Liquidacao.lote_id == Lote.id)
                    .where(
                        Lote.leiloeiro_id == usuarios["leiloeiro"].id,
                        Lote.item_id_externo.in_([str(p.item_id) for p in CATALOGO]),
                    )
                )
            )
            .mappings()
            .all()
        )
    existentes = {}
    for linha in linhas:
        valores = dict(linha)
        item = int(valores.pop("item_id_externo"))
        existentes.setdefault(item, []).append(LoteExistente(**valores))
    criados = {}
    for acao in planejar(existentes, agora):
        papel = CATALOGO[acao.indice]
        if isinstance(acao, Criar):
            item, midia = carregar_item(papel)
            async with recursos.fabrica() as s, s.begin():
                instante = await s.scalar(select(func.clock_timestamp()))
            if papel.papel == "ao_vivo":
                inicio, fim = instante - timedelta(minutes=1), instante + timedelta(days=14)
            elif papel.papel == "agendado":
                inicio = instante + timedelta(days=2)
                fim = inicio + timedelta(days=3)
            else:
                inicio, fim = instante - timedelta(minutes=4), instante + timedelta(seconds=125)
            lote = await publicar_lote(
                recursos,
                usuarios["leiloeiro"],
                item,
                midia,
                SimpleNamespace(
                    lance_inicial_centavos=papel.lance_inicial_centavos,
                    incremento_centavos=papel.incremento_centavos,
                    inicio_em=inicio,
                    fim_em=fim,
                ),
            )
            criados[acao.indice] = lote.id
            resumo.lotes_criados += 1
        else:
            public_id = acao.public_id or criados[acao.indice]
            for indice, (chave, valor) in enumerate(papel.lances):
                try:
                    lance = await dar_lance(
                        recursos, usuarios[chave], public_id, valor, f"demo-{public_id}-{indice}"
                    )
                    resumo.lances += int(not lance.repetida)
                except Recusa as exc:
                    logger.warning("Lance do seed recusado no lote %s: %s", public_id, exc.codigo)
                    break


async def garantir_demonstracao(recursos) -> ResumoSeed:
    resumo = ResumoSeed()
    try:
        async with recursos.engine.connect() as conexao:
            adquirida = None
            try:
                adquirida = await conexao.scalar(
                    text("SELECT pg_try_advisory_lock(:id)"), {"id": TRAVA_DEMO}
                )
                await conexao.commit()
                if not adquirida:
                    logger.info("Outro processo está preparando a demonstração")
                    return resumo
                resumo.trava_obtida = True
                await _semear(recursos, resumo)
            finally:
                with anyio.CancelScope(shield=True):
                    if adquirida is None:
                        await conexao.invalidate()
                    elif adquirida:
                        falhou = False
                        with anyio.move_on_after(PRAZO_LIBERAR_TRAVA, shield=True) as limpeza:
                            try:
                                liberada = await conexao.scalar(
                                    text("SELECT pg_advisory_unlock(:id)"), {"id": TRAVA_DEMO}
                                )
                                await conexao.commit()
                                if not liberada:
                                    raise RuntimeError("Trava de demonstração não foi liberada")
                            except Exception:
                                logger.exception("Falha ao liberar a trava de demonstração")
                                falhou = True
                        if limpeza.cancel_called:
                            logger.error("Prazo excedido ao liberar a trava de demonstração")
                        if falhou or limpeza.cancel_called:
                            resumo.erro = "falha_liberar_trava"
                            await conexao.invalidate()
    except Exception as exc:
        logger.exception("Falha ao preparar demonstração")
        resumo.erro = type(exc).__name__
    return resumo


async def laco_demonstracao(recursos):
    while True:
        await anyio.sleep(recursos.settings.seed_intervalo_s)
        await garantir_demonstracao(recursos)
