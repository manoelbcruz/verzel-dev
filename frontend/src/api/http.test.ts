import { ErroApi, requisitar } from "./http";

afterEach(() => vi.unstubAllGlobals());

it("usa API relativa, credenciais e chave idempotente", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response('{"ok":true}'));
  vi.stubGlobal("fetch", fetch);
  await requisitar("/lotes/id/lances", {
    metodo: "POST", corpo: { valor_centavos: 1500 }, idempotencia: "chave-teste",
  });
  expect(fetch).toHaveBeenCalledWith("/api/lotes/id/lances", expect.objectContaining({
    credentials: "same-origin",
    method: "POST",
    body: '{"valor_centavos":1500}',
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": "chave-teste",
    },
  }));
});

it("preserva recusa e distingue falhas de rede e de serviço", async () => {
  vi.stubGlobal("fetch", vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({
      erro: {
        codigo: "abaixo_do_minimo", mensagem: "Recusa", detalhes: { minimo_centavos: 1600 },
      },
    }), { status: 409 }))
    .mockResolvedValueOnce(new Response("<html>fora</html>", { status: 503 }))
    .mockRejectedValueOnce(new TypeError("rede"))
    .mockResolvedValueOnce(new Response(null, { status: 204 })));
  await expect(requisitar("/x")).rejects.toMatchObject({
    status: 409,
    codigo: "abaixo_do_minimo",
    mensagem: "Recusa",
    detalhes: { minimo_centavos: 1600 },
  });
  await expect(requisitar("/x")).rejects.toMatchObject({ codigo: "servico_indisponivel" });
  await expect(requisitar("/x")).rejects.toMatchObject({ status: 0, codigo: "falha_rede" });
  await expect(requisitar("/x")).resolves.toBeUndefined();
});

it("não converte cancelamento em erro de rede", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("cancelado", "AbortError")));
  await expect(requisitar("/x")).rejects.not.toBeInstanceOf(ErroApi);
});
