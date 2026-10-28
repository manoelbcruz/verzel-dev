import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { criarDespachante } from "../tempoReal/despachar";
import SalaLotePage from "./SalaLotePage";
import { renderizar, simularApi } from "../test/utilitarios";
import { ANA, ID, LEILOEIRO, lote, recusa } from "../test/dados";

it("valida o lance, mostra mínimo e repete tentativa incerta com a mesma chave", async () => {
  let numero = 0;
  const { pedidos } = simularApi({
    [`GET /api/lotes/${ID}`]: () => lote({
      proximo_lance_minimo_centavos: numero >= 3 ? 1700 : 1500,
    }),
    [`POST /api/lotes/${ID}/lances`]: () => {
      numero++;
      if (numero === 1) return recusa("abaixo_do_minimo", { minimo_centavos: 1600 });
      if (numero === 2) throw new TypeError("Rede interrompida");
      if (numero === 3) return { valor_centavos: 1600 };
      return recusa("ja_esta_ganhando");
    },
  });
  renderizar(<SalaLotePage />, { rota: `/lotes/${ID}`, caminho: "/lotes/:loteId", usuario: ANA });
  const campo = await screen.findByLabelText("Seu lance (R$)");
  expect(campo).toHaveValue("15,00");
  fireEvent.click(screen.getByRole("button", { name: "Dar lance" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("R$ 16,00");
  fireEvent.change(campo, { target: { value: "16,00" } });
  fireEvent.click(screen.getByRole("button", { name: "Dar lance" }));
  expect(await screen.findByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("não será duplicado");
  fireEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
  await waitFor(() => expect(screen.getAllByRole("status").some(
    (el) => /Lance de R\$\s16,00 registrado/.test(el.textContent ?? ""),
  )).toBe(true));
  await waitFor(() => expect(campo).toHaveValue("17,00"));
  fireEvent.click(screen.getByRole("button", { name: "Dar lance" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Você já está ganhando"));
  const posts = pedidos.filter((p) => p.metodo === "POST");
  expect(posts.map((p) => p.corpo.valor_centavos)).toEqual([1500, 1600, 1600, 1700]);
  const chaves = posts.map((p) => p.headers.get("Idempotency-Key"));
  expect(chaves[0]).toMatch(/^[A-Za-z0-9_-]{8,128}$/);
  expect(chaves[0]).not.toBe(chaves[1]);
  expect(chaves[1]).toBe(chaves[2]);
  expect(chaves[3]).not.toBe(chaves[2]);
  expect(pedidos.filter((p) => p.metodo === "GET").length).toBeGreaterThan(1);
  fireEvent.change(campo, { target: { value: "abc" } });
  fireEvent.click(screen.getByRole("button", { name: "Dar lance" }));
  expect(screen.getByText("Use o formato 1.234,56")).toBeInTheDocument();
  expect(numero).toBe(4);
});
it("leiloeiro não tem envio habilitado", async () => {
  simularApi({ [`GET /api/lotes/${ID}`]: lote() });
  renderizar(<SalaLotePage />, {
    rota: `/lotes/${ID}`, caminho: "/lotes/:loteId", usuario: LEILOEIRO,
  });
  expect(await screen.findByText("Leiloeiros não dão lances")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Dar lance" })).toBeDisabled();
});
it("id inválido é mostrado como não encontrado", async () => {
  simularApi({ "GET /api/lotes/invalido": recusa("entrada_invalida", {}, 422) });
  renderizar(<SalaLotePage />, { rota: "/lotes/invalido", caminho: "/lotes/:loteId" });
  expect(await screen.findByRole("alert")).toHaveTextContent("não encontrado");
});

it("evento ao vivo mostra superação, posição, novo mínimo e prorrogação", async () => {
  let dados = lote({
    lance_atual_centavos: 1500,
    proximo_lance_minimo_centavos: 1600,
    total_lances: 1,
    lider_pseudonimo: "identidade-ana",
    minha_participacao: { meu_pseudonimo: "identidade-ana", ganhando: true,
      meu_maior_lance_centavos: 1500, posicao: 1, total_participantes: 1 },
  });
  simularApi({ [`GET /api/lotes/${ID}`]: () => dados });
  const { cliente } = renderizar(<SalaLotePage />, {
    rota: `/lotes/${ID}`, caminho: "/lotes/:loteId", usuario: ANA,
  });
  expect(await screen.findByText("Você está ganhando")).toBeInTheDocument();
  expect(screen.getByText("1º de 1 participante")).toBeInTheDocument();
  expect(screen.getByText("Você está ganhando").closest("[role=status]"))
    .toHaveClass("posicao-ganhando");
  const lider = screen.getByText("identi").closest(".dica")!;
  expect(lider).not.toHaveAttribute("tabindex");
  expect(screen.getByText("identi")).toHaveAttribute("aria-hidden", "true");
  expect(lider.querySelector(".visualmente-oculto")).toHaveTextContent("identidade-ana");
  fireEvent.mouseEnter(lider);
  expect(screen.getByRole("tooltip")).toHaveTextContent("identidade-ana");
  expect(lider).toHaveAccessibleDescription("identidade-ana");
  fireEvent.mouseLeave(lider);
  const despachante = criarDespachante(cliente);
  try {
    dados = { ...dados, versao: 2, total_lances: 2, lance_atual_centavos: 1600,
      proximo_lance_minimo_centavos: 1700,
      fim_em: new Date(Date.parse(dados.fim_em) + 120000).toISOString(),
      minha_participacao: { ...dados.minha_participacao!, ganhando: false, posicao: 2,
        total_participantes: 2 } };
    act(() => despachante.despachar({ v: 1, tipo: "lote_atualizado", lote_id: ID, versao: 2 }));
    expect(await screen.findByText("Você foi superado")).toBeInTheDocument();
    expect(screen.getByText("2º de 2 participantes")).toBeInTheDocument();
    expect(screen.getByText("Você foi superado").closest("[role=status]"))
      .toHaveClass("posicao-superado");
    expect(screen.getByText(/Prorrogado/)).toBeInTheDocument();
    expect(screen.getByText(/O mínimo subiu para R\$\s17,00/)).toBeInTheDocument();
    expect(screen.getByLabelText("Seu lance (R$)")).toHaveValue("17,00");
  } finally { despachante.parar(); }
});
it.each(["encerrado", "cancelado"] as const)("sem convite para lance: %s", async (fase) => {
  simularApi({
    [`GET /api/lotes/${ID}`]: lote({ fase, fim_em: new Date(Date.now() - 1000).toISOString() }),
  });
  renderizar(<SalaLotePage />, { rota: `/lotes/${ID}`, caminho: "/lotes/:loteId" });
  await screen.findByRole("heading", { name: "Obra do acervo" });
  expect(screen.queryByText(/Entre como licitante/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Próximo mínimo/)).not.toBeInTheDocument();
});
