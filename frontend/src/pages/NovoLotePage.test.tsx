import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import NovoLotePage from "./NovoLotePage";
import { LEILOEIRO, lote, promessa, recusa, vitrine } from "../test/dados";
import { renderizar, simularApi } from "../test/utilitarios";
import { relogio } from "../lib/relogio";
const item = {
  id_externo: "45434", titulo: "A grande onda", atributos: {},
  imagem_url_externa: "https://images.metmuseum.org/obra.jpg",
};
const pagina = {
  pagina: 1, por_pagina: 20, total_ids: 1, tem_mais: false,
  parcial: false, origem: "api", itens: [item],
};
async function selecionar() {
  fireEvent.change(screen.getByLabelText("Buscar no acervo do Met"), { target: { value: "onda" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
  fireEvent.click(await screen.findByRole("button", { name: "Selecionar A grande onda" }));
}
it("sincroniza relógio deslocado, seleciona e envia centavos e datas ISO", async () => {
  const servidor = Date.now();
  const original = Date.now;
  vi.spyOn(Date, "now").mockImplementation(() => original() + 3600000);
  try {
    const { pedidos } = simularApi({
      "GET /api/lotes": vitrine({ servidor_agora: new Date(servidor).toISOString() }),
      "GET /api/leiloeiro/itens?q=onda&pagina=1": pagina,
      "POST /api/leiloeiro/lotes": lote(),
    });
    renderizar(<NovoLotePage />, { usuario: LEILOEIRO, rota: "/painel/novo" });
    expect(screen.getByText("Sincronizando relógio")).toBeInTheDocument();
    await selecionar();
    await waitFor(() => expect(relogio.sincronizado()).toBe(true));
    fireEvent.change(screen.getByLabelText("Lance inicial (valor mínimo)"), {
      target: { value: "1.500,00" },
    });
    fireEvent.change(screen.getByLabelText("Incremento mínimo"), { target: { value: "50,00" } });
    fireEvent.click(screen.getByRole("button", { name: "Publicar lote" }));
    await waitFor(() => expect(pedidos.some((p) => p.metodo === "POST")).toBe(true));
    const corpo = pedidos.find((p) => p.metodo === "POST")!.corpo;
    expect(corpo).toMatchObject({
      item_id_externo: "45434", lance_inicial_centavos: 150000, incremento_centavos: 5000,
    });
    expect(Date.parse(String(corpo.inicio_em)) - servidor).toBeGreaterThan(0);
    expect(Date.parse(String(corpo.inicio_em)) - servidor).toBeLessThanOrEqual(60000);
    expect(Date.parse(String(corpo.fim_em)) - Date.parse(String(corpo.inicio_em))).toBe(3600000);
  } finally {
    vi.restoreAllMocks();
  }
});
it("duração inválida bloqueia envio", async () => {
  const { pedidos } = simularApi({
    "GET /api/lotes": vitrine(), "GET /api/leiloeiro/itens?q=onda&pagina=1": pagina,
  });
  renderizar(<NovoLotePage />, { usuario: LEILOEIRO });
  await selecionar();
  fireEvent.change(screen.getByLabelText("Fim"), {
    target: { value: (screen.getByLabelText("Início") as HTMLInputElement).value },
  });
  fireEvent.click(screen.getByRole("button", { name: "Publicar lote" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("1 minuto a 30 dias");
  expect(pedidos.some((p) => p.metodo === "POST")).toBe(false);
});
it("explica indisponibilidade do Met", async () => {
  simularApi({
    "GET /api/lotes": vitrine(),
    "GET /api/leiloeiro/itens?q=onda&pagina=1": recusa("api_externa_indisponivel", {}, 503),
  });
  renderizar(<NovoLotePage />, { usuario: LEILOEIRO });
  fireEvent.change(screen.getByLabelText("Buscar no acervo do Met"), { target: { value: "onda" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("acervo do Met está indisponível");
});

it("preserva datas editadas quando o início é apagado e destaca a seleção", async () => {
  simularApi({ "GET /api/lotes": vitrine(), "GET /api/leiloeiro/itens?q=onda&pagina=1": pagina });
  renderizar(<NovoLotePage />, { usuario: LEILOEIRO });
  await selecionar();
  expect(screen.getByRole("button", { name: "Selecionar A grande onda" }))
    .toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("heading", { name: "Condições do leilão" })).toHaveFocus();
  expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Fim"), { target: { value: "01/01/2030 12:00" } });
  fireEvent.change(screen.getByLabelText("Início"), { target: { value: "" } });
  expect(screen.getByLabelText("Início")).toHaveValue("");
  expect(screen.getByLabelText("Fim")).toHaveValue("01/01/2030 12:00");
});

it("mantém a página anterior do Met durante a paginação", async () => {
  const seguinte = promessa<unknown>();
  simularApi({ "GET /api/lotes": vitrine(),
    "GET /api/leiloeiro/itens?q=onda&pagina=1": { ...pagina, tem_mais: true },
    "GET /api/leiloeiro/itens?q=onda&pagina=2": () => seguinte.pendente });
  renderizar(<NovoLotePage />, { usuario: LEILOEIRO });
  await selecionar();
  fireEvent.click(screen.getByRole("button", { name: "Próxima página" }));
  expect(screen.getByRole("button", { name: "Selecionar A grande onda" })).toBeInTheDocument();
  await act(async () => seguinte.liberar({ ...pagina, pagina: 2,
    itens: [{ ...item, id_externo: "2", titulo: "Outra obra" }] }));
  expect(await screen.findByRole("button", { name: "Selecionar Outra obra" })).toBeInTheDocument();
});
it("não repete busca quando o Met responde 503", async () => {
  vi.useFakeTimers();
  const { pedidos } = simularApi({ "GET /api/lotes": vitrine(),
    "GET /api/leiloeiro/itens?q=onda&pagina=1": () => recusa("api_externa_indisponivel", {}, 503),
  });
  renderizar(<NovoLotePage />, { usuario: LEILOEIRO });
  fireEvent.change(screen.getByLabelText("Buscar no acervo do Met"), { target: { value: "onda" } });
  fireEvent.click(screen.getByRole("button", { name: "Buscar" }));
  await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
  expect(pedidos.filter((p) => p.caminho.includes("/itens"))).toHaveLength(1);
  expect(screen.getByRole("alert")).toHaveTextContent("acervo do Met está indisponível");
});

it("não publica o último valor válido enquanto a data visível está incompleta", async () => {
  const { pedidos } = simularApi({
    "GET /api/lotes": vitrine(), "GET /api/leiloeiro/itens?q=onda&pagina=1": pagina,
  });
  renderizar(<NovoLotePage />, { usuario: LEILOEIRO });
  await selecionar();
  const fim = screen.getByLabelText("Fim");
  fireEvent.change(fim, { target: { value: "28/10/2026 14:" } });
  fireEvent.click(screen.getByRole("button", { name: "Publicar lote" }));
  expect(fim).toHaveAccessibleDescription("Use o formato dd/mm/aaaa hh:mm");
  expect(fim).toHaveFocus();
  expect(pedidos.some((p) => p.metodo === "POST")).toBe(false);
});

it.each([
  ["Início", "Preencha o início."], ["Fim", "Preencha o fim."],
])("explica %s vazio antes da duração", async (rotulo, mensagem) => {
  const { pedidos } = simularApi({
    "GET /api/lotes": vitrine(), "GET /api/leiloeiro/itens?q=onda&pagina=1": pagina,
  });
  renderizar(<NovoLotePage />, { usuario: LEILOEIRO });
  await selecionar();
  const campo = screen.getByLabelText(rotulo);
  fireEvent.change(campo, { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "Publicar lote" }));
  expect(screen.getByRole("alert")).toHaveTextContent(mensagem);
  expect(campo).toHaveAccessibleDescription(mensagem);
  expect(screen.queryByText(/A duração deve ser/)).not.toBeInTheDocument();
  expect(pedidos.some((p) => p.metodo === "POST")).toBe(false);
});

it("Começar agora aceita início vazio e ainda exige o fim", async () => {
  const { pedidos } = simularApi({
    "GET /api/lotes": vitrine(), "GET /api/leiloeiro/itens?q=onda&pagina=1": pagina,
    "POST /api/leiloeiro/lotes": lote(),
  });
  renderizar(<NovoLotePage />, { usuario: LEILOEIRO });
  await selecionar();
  const fim = screen.getByLabelText("Fim") as HTMLInputElement;
  const fimOriginal = fim.value;
  fireEvent.change(screen.getByLabelText("Início"), { target: { value: "" } });
  fireEvent.click(screen.getByLabelText("Começar agora"));
  fireEvent.change(fim, { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "Publicar lote" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Preencha o fim.");
  expect(pedidos.some((p) => p.metodo === "POST")).toBe(false);
  fireEvent.change(fim, { target: { value: fimOriginal } });
  fireEvent.click(screen.getByRole("button", { name: "Publicar lote" }));
  await waitFor(() => expect(pedidos.some((p) => p.metodo === "POST")).toBe(true));
});
