import { fireEvent, screen, waitFor } from "@testing-library/react";
import App from "../App";
import { ANA, ID, LEILOEIRO, lote } from "../test/dados";
import { renderizar, simularApi } from "../test/utilitarios";

function preencherLogin(email: string, senha: string) {
  fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: email } });
  fireEvent.change(screen.getByLabelText("Senha"), { target: { value: senha } });
  fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
}

it("login respeita volta", async () => {
  const senha = crypto.getRandomValues(new Uint32Array(4)).join("");
  const { pedidos } = simularApi({
    "POST /api/auth/login": ANA,
    [`GET /api/lotes/${ID}`]: lote(),
  });
  renderizar(<App />, { rota: `/entrar?volta=${encodeURIComponent(`/lotes/${ID}`)}` });
  preencherLogin(ANA.email, senha);
  expect(await screen.findByRole("heading", { name: "Obra do acervo" })).toBeInTheDocument();
  expect(pedidos.find((p) => p.metodo === "POST")!.corpo).toEqual({ email: ANA.email, senha });
});

it.each(["/entrar", "/cadastro"])("erros não entram no nome dos campos em %s", (rota) => {
  simularApi({});
  renderizar(<App />, { rota });
  const botao = rota === "/entrar" ? "Entrar" : "Criar conta";
  fireEvent.click(screen.getByRole("button", { name: botao }));
  const rotulos = rota === "/entrar" ? ["E-mail", "Senha"] : ["Nome", "E-mail", "Senha"];
  for (const rotulo of rotulos) {
    const campo = screen.getByLabelText(rotulo, { exact: true });
    expect(campo).toHaveAccessibleName(rotulo);
    expect(campo).toHaveAccessibleDescription(/Preencha este campo\./);
    expect(campo.closest("label")).not.toHaveTextContent("Preencha este campo.");
  }
});

it("cadastro limpa somente o erro do campo alterado", () => {
  simularApi({});
  renderizar(<App />, { rota: "/cadastro" });
  fireEvent.click(screen.getByRole("button", { name: "Criar conta" }));
  const nome = screen.getByLabelText("Nome");
  fireEvent.change(nome, { target: { value: ANA.nome } });
  expect(nome).toHaveAttribute("aria-invalid", "false");
  expect(nome).not.toHaveAccessibleDescription();
  expect(screen.getAllByText("Preencha este campo.")).toHaveLength(2);
  expect(screen.getByLabelText("E-mail")).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByLabelText("Senha")).toHaveAttribute("aria-invalid", "true");
});

it("entrada rápida usa o rótulo do papel e respeita volta", async () => {
  const senha = crypto.getRandomValues(new Uint32Array(4)).join("");
  const { pedidos } = simularApi({
    "GET /api/demo": {
      contas: [{ papel: "licitante", email: ANA.email, rotulo: "comprador 1" }],
      senha,
    },
    "POST /api/auth/login": ANA,
    [`GET /api/lotes/${ID}`]: lote(),
  });
  renderizar(<App />, { rota: `/entrar?volta=${encodeURIComponent(`/lotes/${ID}`)}` });
  fireEvent.click(await screen.findByRole("button", { name: "Entrar como comprador 1" }));
  expect(await screen.findByRole("heading", { name: "Obra do acervo" })).toBeInTheDocument();
  expect(pedidos.find((p) => p.metodo === "POST")!.corpo).toEqual({ email: ANA.email, senha });
});

it("sem demo 404 não oferece acesso rápido", async () => {
  const { pedidos } = simularApi({});
  renderizar(<App />, { rota: "/entrar" });
  await waitFor(() => expect(pedidos.some((p) => p.caminho === "/api/demo")).toBe(true));
  expect(screen.queryByText("Acesso rápido para avaliação")).not.toBeInTheDocument();
});

it("preserva volta ao criar conta e atualiza o título da rota", async () => {
  const senha = crypto.getRandomValues(new Uint32Array(4)).join("");
  simularApi({ "POST /api/auth/cadastro": ANA, [`GET /api/lotes/${ID}`]: lote() });
  renderizar(<App />, { rota: `/entrar?volta=${encodeURIComponent(`/lotes/${ID}`)}` });
  expect(document.title).toBe("Entrar · Casa de Leilões");
  const criar = screen
    .getAllByRole("link", { name: "Criar conta" })
    .find((link) => link.getAttribute("href")?.includes("volta="))!;
  fireEvent.click(criar);
  expect(document.title).toBe("Criar conta · Casa de Leilões");
  expect(screen.getByText("Mínimo de 8 caracteres")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Nome"), { target: { value: ANA.nome } });
  fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: ANA.email } });
  fireEvent.change(screen.getByLabelText(/Senha/), { target: { value: senha } });
  fireEvent.click(screen.getByRole("button", { name: "Criar conta" }));
  expect(await screen.findByRole("heading", { name: "Obra do acervo" })).toBeInTheDocument();
  expect(document.title).toBe("Sala do lote · Casa de Leilões");
});

it("login de leiloeiro sem volta abre o painel", async () => {
  simularApi({
    "POST /api/auth/login": LEILOEIRO,
    "GET /api/leiloeiro/lotes": { total_recebido_centavos: 0, lotes: [] },
  });
  renderizar(<App />, { rota: "/entrar" });
  preencherLogin(LEILOEIRO.email, crypto.getRandomValues(new Uint32Array(4)).join(""));
  expect(await screen.findByRole("heading", { name: "Painel do leiloeiro" })).toBeInTheDocument();
});

describe.each([
  { rota: "/entrar", botao: "Entrar", primeiro: "E-mail", quantidade: 2 },
  { rota: "/cadastro", botao: "Criar conta", primeiro: "Nome", quantidade: 3 },
])("validação própria em $rota", ({ rota, botao, primeiro, quantidade }) => {
  it("exibe erros no envio vazio, foca o primeiro campo e não envia à API", () => {
    const { pedidos } = simularApi({});
    renderizar(<App />, { rota });
    const campo = screen.getByLabelText(primeiro);
    fireEvent.click(screen.getByRole("button", { name: botao }));
    expect(screen.getAllByText("Preencha este campo.")).toHaveLength(quantidade);
    expect(campo).toHaveFocus();
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo).toHaveAccessibleDescription("Preencha este campo.");
    expect(campo.closest("form")).toHaveAttribute("novalidate");
    expect(pedidos.some((p) => p.metodo === "POST")).toBe(false);
  });

  it("valida e-mail e senha e foca o primeiro erro restante", () => {
    const { pedidos } = simularApi({});
    renderizar(<App />, { rota });
    if (rota === "/cadastro") {
      fireEvent.change(screen.getByLabelText("Nome"), { target: { value: ANA.nome } });
    }
    const email = screen.getByLabelText("E-mail");
    const senha = screen.getByLabelText(/Senha/);
    fireEvent.change(email, { target: { value: "email@sem-ponto" } });
    const curta = String(crypto.getRandomValues(new Uint32Array(1))[0]).slice(0, 4);
    fireEvent.change(senha, { target: { value: curta } });
    fireEvent.click(screen.getByRole("button", { name: botao }));
    expect(email).toHaveAccessibleDescription("Informe um e-mail válido.");
    expect(screen.getByText("Mínimo de 8 caracteres.")).toBeInTheDocument();
    expect(email).toHaveFocus();
    fireEvent.change(email, { target: { value: ANA.email } });
    fireEvent.click(screen.getByRole("button", { name: botao }));
    expect(email).toHaveAttribute("aria-invalid", "false");
    expect(senha).toHaveFocus();
    expect(pedidos.some((p) => p.metodo === "POST")).toBe(false);
  });
});
