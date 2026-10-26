import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest

from app.main import create_app
from app.recursos import abrir_recursos
from app.services.liquidacao import encerrar_lote
from tests.apoio import envelhecer_lote, met_simulado

pytestmark = [pytest.mark.pg, pytest.mark.anyio]


async def test_api_externa_fora_preserva_operacoes(settings_teste, banco_teste):
    falhar = False
    chamadas = []

    def responder(request):
        chamadas.append(request.url)
        if falhar:
            raise httpx.ConnectError("Met indisponível no teste", request=request)
        return met_simulado(request)

    settings_teste.database_url = banco_teste.render_as_string(hide_password=False)
    async with abrir_recursos(
        settings_teste, transporte_http=httpx.MockTransport(responder), iniciar_worker=False
    ) as recursos:
        app = create_app(recursos=recursos)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": "http://test"},
        ) as cliente:
            senha = secrets.token_urlsafe(18)
            for papel in ("leiloeiro", "licitante"):
                await cliente.post(
                    "/api/auth/cadastro",
                    json={
                        "nome": papel,
                        "papel": papel,
                        "email": f"{papel}@example.test",
                        "senha": senha,
                    },
                )
            await cliente.post(
                "/api/carteira/depositos",
                json={"valor_centavos": 1000},
                headers={"Idempotency-Key": "deposito-fora"},
            )
            await cliente.post(
                "/api/auth/login", json={"email": "leiloeiro@example.test", "senha": senha}
            )
            assert (await cliente.get("/api/leiloeiro/itens?q=obra")).status_code == 200
            agora = datetime.now(UTC)
            entrada = {
                "item_id_externo": "123",
                "lance_inicial_centavos": 100,
                "incremento_centavos": 10,
                "inicio_em": agora.isoformat(),
                "fim_em": (agora + timedelta(minutes=2)).isoformat(),
            }
            criado = await cliente.post("/api/leiloeiro/lotes", json=entrada)
            assert criado.status_code == 201, criado.text
            lote = criado.json()
            await cliente.post(
                "/api/auth/login", json={"email": "licitante@example.test", "senha": senha}
            )
            assert (
                await cliente.post(
                    f"/api/lotes/{lote['id']}/lances",
                    json={"valor_centavos": 100},
                    headers={"Idempotency-Key": "lance-api-fora"},
                )
            ).status_code == 201
            interno = await envelhecer_lote(recursos, UUID(lote["id"]))
            await encerrar_lote(recursos, interno)
            codigo = (await cliente.get("/api/me/participacoes")).json()[0]["comprovante_codigo"]
            falhar = True
            total_antes = len(chamadas)
            for rota in [
                "/api/lotes",
                f"/api/lotes/{lote['id']}",
                f"/api/lotes/{lote['id']}/auditoria",
                f"/api/comprovantes/{codigo}",
                lote["imagem_url"],
                "/api/carteira",
            ]:
                assert (await cliente.get(rota)).status_code == 200
            assert len(chamadas) == total_antes
            await cliente.post(
                "/api/auth/login", json={"email": "leiloeiro@example.test", "senha": senha}
            )
            assert (await cliente.get("/api/leiloeiro/itens?q=sem-cache")).status_code == 503
            r = await cliente.get("/api/leiloeiro/itens?q=obra")
            assert r.status_code == 200 and r.json()["origem"] == "cache"
            assert (await cliente.post("/api/leiloeiro/lotes", json=entrada)).status_code == 201
            assert sum(url.host == "images.metmuseum.org" for url in chamadas) == 1
