import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.services.cadeia import ZERO_MAC, assinar_cabeca, mac_evento, pseudonimo
from app.services.verificacao import DadosAuditoria

PNG = b"\x89PNG\r\n\x1a\nconteudo de teste"
AGORA = datetime(2026, 10, 25, 12, tzinfo=UTC)


def dados_publicados(chaves):
    lote = {
        "id": 1,
        "public_id": UUID("11111111-aaaa-4000-8000-111111111111"),
        "leiloeiro_id": 1,
        "status": "publicado",
        "item_fonte": "met",
        "item_id_externo": "123",
        "titulo": "Obra de arte",
        "atributos": {"artista": "Pessoa", "licenca": "CC0"},
        "lance_inicial_centavos": 100,
        "incremento_centavos": 10,
        "inicio_em": AGORA,
        "fim_original_em": AGORA + timedelta(seconds=60),
        "fim_em": AGORA + timedelta(seconds=60),
        "lider_id": None,
        "lance_atual_centavos": None,
        "total_lances": 0,
        "cabeca_seq": 1,
    }
    dados = DadosAuditoria(
        lote, hashlib.sha256(PNG).hexdigest(), hashlib.sha256(PNG).hexdigest(), []
    )
    anexar_memoria(dados, chaves, "publicacao", AGORA)
    return dados


def anexar_memoria(dados, chaves, tipo, instante, usuario=2, valor=100):
    lote = dados.lote
    seq = len(dados.eventos) + 1
    evento = {
        "lote_id": lote["id"],
        "seq": seq,
        "tipo": tipo,
        "instante": instante,
        "licitante_id": None,
        "pseudonimo": None,
        "valor_centavos": None,
        "fim_anterior": None,
        "fim_novo": None,
    }
    if tipo == "lance":
        fim = max(lote["fim_em"], instante + timedelta(seconds=120))
        evento.update(
            licitante_id=usuario,
            pseudonimo=pseudonimo(chaves.privacidade, lote["public_id"], usuario),
            valor_centavos=valor,
            fim_anterior=lote["fim_em"],
            fim_novo=fim,
        )
        lote.update(
            lider_id=usuario,
            lance_atual_centavos=valor,
            fim_em=fim,
            total_lances=lote["total_lances"] + 1,
        )
        dados.reserva = {"lote_id": lote["id"], "usuario_id": usuario, "valor_centavos": valor}
    elif tipo == "cancelamento":
        lote["status"] = "cancelado"
    elif tipo == "encerramento":
        lider, valor = lote["lider_id"], lote["lance_atual_centavos"]
        dados.reserva = None
        lote["status"] = "encerrado"
        dados.liquidacao = {
            "id": 1,
            "lote_id": lote["id"],
            "resultado": "arrematado" if lider else "sem_lances",
            "vencedor_id": lider,
            "valor_centavos": valor,
            "vencedor_pseudonimo": pseudonimo(chaves.privacidade, lote["public_id"], lider)
            if lider
            else None,
            "comprovante_codigo": "comprovante-publico" if lider else None,
        }
        if lider:
            dados.lancamentos = [
                {
                    "usuario_id": lider,
                    "tipo": "arremate_debito",
                    "valor_centavos": -valor,
                    "liquidacao_id": 1,
                },
                {
                    "usuario_id": lote["leiloeiro_id"],
                    "tipo": "arremate_credito",
                    "valor_centavos": valor,
                    "liquidacao_id": 1,
                },
            ]
    anterior = dados.eventos[-1]["mac"] if dados.eventos else ZERO_MAC
    evento["mac"] = mac_evento(
        lote, evento, anterior, dados.midia_sha256, dados.liquidacao, chaves, lote["fim_em"]
    )
    dados.eventos.append(evento)
    lote.update(
        cabeca_seq=seq,
        cabeca_assinatura=assinar_cabeca(chaves.integridade, lote["public_id"], seq, evento["mac"]),
    )
    return evento


def dados_com_lances(chaves, encerrar=False):
    dados = dados_publicados(chaves)
    anexar_memoria(dados, chaves, "lance", AGORA + timedelta(seconds=10))
    anexar_memoria(dados, chaves, "lance", AGORA + timedelta(seconds=20), usuario=3, valor=110)
    if encerrar:
        anexar_memoria(dados, chaves, "encerramento", dados.lote["fim_em"])
    return dados


def reassinar(dados, chaves):
    anterior = ZERO_MAC
    fim = dados.lote["fim_original_em"]
    for evento in dados.eventos:
        evento["mac"] = mac_evento(
            dados.lote, evento, anterior, dados.midia_sha256, dados.liquidacao, chaves, fim
        )
        if evento["tipo"] == "lance":
            fim = evento["fim_novo"]
        anterior = evento["mac"]
    dados.lote["cabeca_assinatura"] = assinar_cabeca(
        chaves.integridade, dados.lote["public_id"], len(dados.eventos), anterior
    )


def met_simulado(request):
    import httpx

    if request.url.host == "images.metmuseum.org":
        return httpx.Response(200, content=PNG, headers={"Content-Type": "image/png"})
    if request.url.path.endswith("/search"):
        return httpx.Response(200, json={"total": 50, "objectIDs": list(range(1, 51))})
    item_id = request.url.path.rsplit("/", 1)[-1]
    return httpx.Response(
        200,
        json={
            "objectID": int(item_id),
            "isPublicDomain": True,
            "title": f"Obra {item_id}",
            "primaryImageSmall": f"https://images.metmuseum.org/obra-{item_id}.png",
            "artistDisplayName": "Artista do acervo",
        },
    )


async def criar_usuario(recursos, papel="licitante", saldo=0, *, cliente=None):
    import secrets

    from app.schemas.auth import CadastroEntrada
    from app.services.auth import cadastrar_usuario
    from app.services.carteira import depositar

    sufixo = secrets.token_hex(6)
    usuario, token = await cadastrar_usuario(
        recursos,
        CadastroEntrada(
            nome=f"Pessoa {sufixo}",
            email=f"{sufixo}@example.test",
            senha=secrets.token_urlsafe(18),
            papel=papel,
        ),
    )
    if saldo:
        await depositar(recursos, usuario, saldo, secrets.token_urlsafe(12))
    if cliente is not None:
        cliente.cookies.set("sessao", token)
    return usuario


async def criar_lote(
    recursos,
    leiloeiro=None,
    *,
    segundos=3600,
    inicio=None,
    inicial=100,
    incremento=10,
    titulo="Obra de arte",
):
    from types import SimpleNamespace

    from sqlalchemy import func, select

    from app.integrations.imagens import MidiaBaixada
    from app.schemas.itens import ItemExterno
    from app.services.lotes import publicar_lote

    leiloeiro = leiloeiro or await criar_usuario(recursos, "leiloeiro")
    async with recursos.fabrica() as s, s.begin():
        agora = await s.scalar(select(func.clock_timestamp()))
    item = ItemExterno(
        id_externo="123",
        titulo=titulo,
        atributos={"artista": "Artista"},
        imagem_url_externa="https://images.metmuseum.org/teste.png",
    )
    condicoes = SimpleNamespace(
        lance_inicial_centavos=inicial,
        incremento_centavos=incremento,
        inicio_em=inicio or agora - timedelta(seconds=1),
        fim_em=agora + timedelta(seconds=segundos),
    )
    return await publicar_lote(
        recursos,
        leiloeiro,
        item,
        MidiaBaixada(PNG, "image/png", hashlib.sha256(PNG).hexdigest()),
        condicoes,
    )


async def id_interno(recursos, public_id):
    from sqlalchemy import select

    from app.models import Lote

    async with recursos.fabrica() as s, s.begin():
        return await s.scalar(select(Lote.id).where(Lote.public_id == public_id))


async def conferir_reconciliacao(recursos):
    from sqlalchemy import func, select

    from app.db.transacao import leitura_consistente
    from app.models import CarteiraRegistro, Lancamento, Reserva

    async with leitura_consistente(recursos.fabrica) as s:
        carteiras = (await s.execute(select(CarteiraRegistro.__table__))).mappings()
        for carteira in carteiras:
            saldo_razao = await s.scalar(
                select(func.coalesce(func.sum(Lancamento.valor_centavos), 0)).where(
                    Lancamento.usuario_id == carteira["usuario_id"]
                )
            )
            reservas = await s.scalar(
                select(func.coalesce(func.sum(Reserva.valor_centavos), 0)).where(
                    Reserva.usuario_id == carteira["usuario_id"]
                )
            )
            assert carteira["saldo_centavos"] == saldo_razao
            assert carteira["saldo_centavos"] - reservas >= 0


async def simultaneos(*chamadas):
    import anyio

    from app.core.erros import Recusa

    inicio = anyio.Event()
    resultados = [None] * len(chamadas)

    async def executar(pos, chamada):
        await inicio.wait()
        try:
            resultados[pos] = await chamada()
        except Recusa as erro:
            resultados[pos] = erro

    async with anyio.create_task_group() as grupo:
        for pos, chamada in enumerate(chamadas):
            grupo.start_soon(executar, pos, chamada)
        inicio.set()
    return resultados


async def envelhecer_lote(recursos, public_id):
    """Desloca um histórico válido no tempo para testar liquidação sem esperar 120 s.

    Só a fixture conhece as chaves: as datas persistidas são deslocadas igualmente e
    os eventos reassinados. O serviço de liquidação continua real e usa o relógio do banco.
    Não usar nos testes da disputa por trava/instante, que esperam o tempo real passar.
    """
    from sqlalchemy import func, select, update

    from app.models import EventoLote, Lote
    from app.services.consultas import carregar_dados

    async with recursos.fabrica() as s, s.begin():
        lote = (
            (
                await s.execute(
                    select(Lote.__table__).where(Lote.public_id == public_id).with_for_update()
                )
            )
            .mappings()
            .one()
        )
        dados = await carregar_dados(s, lote)
        dados.eventos = [dict(e) for e in dados.eventos]
        agora = await s.scalar(select(func.clock_timestamp()))
        deslocamento = lote["fim_em"] - agora + timedelta(seconds=1)
        for campo in ("inicio_em", "fim_original_em", "fim_em"):
            dados.lote[campo] -= deslocamento
        for evento in dados.eventos:
            for campo in ("instante", "fim_anterior", "fim_novo"):
                if evento[campo] is not None:
                    evento[campo] -= deslocamento
        reassinar(dados, recursos.chaves)
        await s.execute(
            update(Lote)
            .where(Lote.id == lote["id"])
            .values(
                **{
                    campo: dados.lote[campo]
                    for campo in ("inicio_em", "fim_original_em", "fim_em", "cabeca_assinatura")
                }
            )
        )
        for evento in dados.eventos:
            await s.execute(
                update(EventoLote)
                .where(EventoLote.id == evento["id"])
                .values(
                    **{
                        campo: evento[campo]
                        for campo in ("instante", "fim_anterior", "fim_novo", "mac")
                    }
                )
            )
    return lote["id"]
