from dataclasses import asdict

from sqlalchemy import func, select

from app.core.erros import Recusa
from app.db.transacao import leitura_consistente
from app.models import Lote
from app.schemas.auditoria import RelatorioAuditoria
from app.services.consultas import carregar_dados
from app.services.regras import calcular_fase
from app.services.verificacao import verificar


async def auditar_lote(recursos, public_id):
    async with leitura_consistente(recursos.fabrica) as s:
        lote = (
            (await s.execute(select(Lote.__table__).where(Lote.public_id == public_id)))
            .mappings()
            .one_or_none()
        )
        if lote is None:
            raise Recusa("lote_nao_encontrado")
        dados = await carregar_dados(s, lote)
        agora = await s.scalar(select(func.clock_timestamp()))
        veredito = verificar(dados, recursos.chaves)
        return RelatorioAuditoria(
            lote_id=public_id,
            titulo=lote["titulo"],
            imagem_url=f"/api/midias/{dados.midia_sha256}",
            fase=calcular_fase(lote["status"], lote["inicio_em"], lote["fim_em"], agora),
            veredito="integro" if veredito.integro else "adulterado",
            total_eventos=veredito.total_eventos,
            eventos_verificados=veredito.eventos_verificados,
            falha=asdict(veredito.falha) if veredito.falha else None,
            verificado_em=agora,
            eventos=[
                {
                    "seq": evento["seq"],
                    "tipo": evento["tipo"],
                    "instante": evento["instante"],
                    "licitante_pseudonimo": evento["pseudonimo"],
                    "valor_centavos": evento["valor_centavos"],
                    "fim_novo": evento["fim_novo"],
                    "prorrogou": evento["tipo"] == "lance"
                    and evento["fim_novo"] > evento["fim_anterior"],
                    "mac": evento["mac"].hex(),
                    "verificado": pos < veredito.eventos_verificados,
                }
                for pos, evento in enumerate(dados.eventos)
            ],
        )
