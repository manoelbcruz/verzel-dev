import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { TempoRealProvider } from "../tempoReal/TempoRealProvider";
import App from "../App";
import { registrarConexao, trocarIdentidade } from "./sessao";
import { ANA, BRUNO, ID, carteira, lote, promessa, recusa, vitrine } from "../test/dados";
import { renderizar, respostaJson, simularApi, SocketFalso } from "../test/utilitarios";

it.each([false, true])("descarta depósito de A após trocar para B, erro: %s", async (falha) => {
  const deposito = promessa<unknown>();
  let atual = ANA;
  const { pedidos } = simularApi({
    "GET /api/carteira": () => carteira(atual === ANA ? 100000 : 200000),
    "GET /api/me/participacoes": [],
    "POST /api/carteira/depositos": () => deposito.pendente,
  });
  const { cliente } = renderizar(<App />, { rota: "/carteira", usuario: ANA });
  fireEvent.click(await screen.findByRole("button", { name: "Depositar" }));
  await waitFor(() => expect(pedidos.some((p) => p.metodo === "POST")).toBe(true));
  atual = BRUNO;
  act(() => trocarIdentidade(cliente, { reiniciar: vi.fn() }, BRUNO));
  expect(await screen.findByText("Bruno de teste")).toBeInTheDocument();
  expect(await screen.findByText("R$ 2.000,00")).toBeInTheDocument();
  const invalidar = vi.spyOn(cliente, "invalidateQueries");
  await act(async () => {
    deposito.liberar(falha ? recusa("nao_autenticado", {}, 401) : carteira(999999));
    await deposito.pendente;
  });
  expect(invalidar).not.toHaveBeenCalled();
  expect(cliente.getQueryData(["carteira"])).toEqual(carteira(200000));
  expect(cliente.getQueryData(["sessao"])).toEqual(BRUNO);
  expect(screen.queryByText(/Depósito registrado/)).not.toBeInTheDocument();
  expect(screen.queryByText("R$ 9.999,99")).not.toBeInTheDocument();
});

it("erro 401 de consulta encerra a identidade e remove a tela privada", async () => {
  simularApi({
    "GET /api/carteira": recusa("nao_autenticado", {}, 401),
    "GET /api/me/participacoes": [],
  });
  const { cliente } = renderizar(<App />, { rota: "/carteira", usuario: ANA });
  expect(await screen.findByRole("heading", { name: "Entre na sua conta" })).toBeInTheDocument();
  expect(screen.getByText("Sua sessão expirou. Entre de novo.")).toBeInTheDocument();
  expect(cliente.getQueryData(["sessao"])).toBeNull();
  expect(screen.queryByText(ANA.nome)).not.toBeInTheDocument();
});

it("logout antigo pendente não bloqueia o botão da nova identidade", async () => {
  const primeiroLogout = promessa<unknown>();
  let chamadas = 0;
  simularApi({
    "GET /api/lotes": vitrine(),
    "POST /api/auth/logout": () =>
      ++chamadas === 1 ? primeiroLogout.pendente : respostaJson(null, 204),
  });
  const { cliente } = renderizar(<App />, { usuario: ANA });
  fireEvent.click(screen.getByRole("button", { name: "Sair" }));
  await waitFor(() => expect(chamadas).toBe(1));
  act(() => trocarIdentidade(cliente, { reiniciar: vi.fn() }, BRUNO));
  expect(screen.getByRole("button", { name: "Sair" })).toBeEnabled();
  const invalidar = vi.spyOn(cliente, "invalidateQueries");
  await act(async () => {
    primeiroLogout.liberar(respostaJson(null, 204));
    await primeiroLogout.pendente;
  });
  expect(cliente.getQueryData(["sessao"])).toEqual(BRUNO);
  expect(invalidar).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Sair" }));
  await waitFor(() => expect(cliente.getQueryData(["sessao"])).toBeNull());
});

it("logout atualiza cabeçalho e tela privada sem render ou navegação externos", async () => {
  simularApi({
    "GET /api/carteira": carteira(),
    "GET /api/me/participacoes": [],
    "POST /api/auth/logout": respostaJson(null, 204),
  });
  const { cliente } = renderizar(<App />, { rota: "/carteira", usuario: ANA });
  expect(await screen.findByRole("heading", { name: "Minha carteira" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Sair" }));
  expect(await screen.findByRole("heading", { name: "Entre na sua conta" })).toBeInTheDocument();
  expect(screen.queryByText("Ana de teste")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Minha carteira" })).not.toBeInTheDocument();
  expect(cliente.getQueryData(["sessao"])).toBeNull();
});

it("trocas de identidade não reutilizam detalhes privados com GET bloqueado", async () => {
  const pendente = promessa<unknown>();
  const vencedor = lote({
    minha_participacao: {
      meu_pseudonimo: "Identidade-antiga", ganhando: true, meu_maior_lance_centavos: 1600,
      posicao: 1, total_participantes: 2,
    },
    resultado: {
      situacao: "arrematado", valor_centavos: 1600, vencedor_pseudonimo: "Identidade-antiga",
      encerrado_em: new Date().toISOString(), comprovante_codigo: "comprovante-antigo",
    },
  });
  let primeira = true;
  simularApi({
    [`GET /api/lotes/${ID}`]: () => {
      if (primeira) {
        primeira = false;
        return vencedor;
      }
      return pendente.pendente;
    },
  });
  const { cliente } = renderizar(<App />, { rota: `/lotes/${ID}`, usuario: ANA });
  expect(await screen.findByText("Você arrematou este lote")).toBeInTheDocument();
  for (const usuario of [BRUNO, null]) {
    act(() => trocarIdentidade(cliente, { reiniciar: vi.fn() }, usuario));
    expect(cliente.getQueryData(["lote", ID])).toBeUndefined();
    expect(screen.queryByText("Você arrematou este lote")).not.toBeInTheDocument();
    expect(screen.queryByText(/Identidade-antiga/)).not.toBeInTheDocument();
    expect(screen.queryAllByRole("link", { name: "Ver comprovante" })).toHaveLength(0);
  }
  await act(async () => {
    pendente.liberar(lote());
    await pendente.pendente;
  });
});

it("login a partir de anônimo reinicia a conexão", async () => {
  const senha = crypto.getRandomValues(new Uint32Array(4)).join("");
  simularApi({ "POST /api/auth/login": ANA, "GET /api/lotes": vitrine() });
  renderizar(<App />, { rota: "/entrar" });
  const reiniciar = vi.fn();
  const remover = registrarConexao({ reiniciar });
  try {
    fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: ANA.email } });
    fireEvent.change(screen.getByLabelText("Senha"), { target: { value: senha } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await waitFor(() => expect(reiniciar).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(ANA.nome)).toBeInTheDocument();
  } finally {
    remover();
  }
});

it("401 em depósito explica a expiração na entrada", async () => {
  simularApi({ "GET /api/carteira": carteira(), "GET /api/me/participacoes": [],
    "POST /api/carteira/depositos": recusa("nao_autenticado", {}, 401) });
  const { cliente } = renderizar(<App />, { rota: "/carteira", usuario: ANA });
  fireEvent.click(await screen.findByRole("button", { name: "Depositar" }));
  expect(await screen.findByRole("heading", { name: "Entre na sua conta" })).toBeInTheDocument();
  expect(screen.getByText("Sua sessão expirou. Entre de novo.")).toBeInTheDocument();
  expect(cliente.getQueryData(["sessao"])).toBeNull();
});

it("logout com 4001 antes do 204 não anuncia expiração", async () => {
  const sockets: SocketFalso[] = [];
  vi.stubGlobal("WebSocket", class extends SocketFalso {
    constructor(url: string) {
      super(url);
      sockets.push(this);
    }
  });
  const logout = promessa<unknown>();
  let revogada = false;
  simularApi({
    "GET /api/carteira": carteira(),
    "GET /api/me/participacoes": [],
    "GET /api/auth/me": () => revogada ? recusa("nao_autenticado", {}, 401) : ANA,
    "POST /api/auth/logout": () => logout.pendente,
  });
  const { cliente } = renderizar(<TempoRealProvider><App /></TempoRealProvider>, {
    rota: "/carteira", usuario: ANA,
  });
  await screen.findByRole("heading", { name: "Minha carteira" });
  fireEvent.click(screen.getByRole("button", { name: "Sair" }));
  revogada = true;
  act(() => sockets[0].fecharPeloServidor(4001));
  await screen.findByRole("heading", { name: "Entre na sua conta" });
  expect(screen.queryByText(/Sua sessão expirou/)).not.toBeInTheDocument();
  await act(async () => {
    logout.liberar(respostaJson(null, 204));
    await logout.pendente;
  });
  expect(cliente.getQueryData(["sessao"])).toBeNull();
  expect(screen.queryByText(/Sua sessão expirou/)).not.toBeInTheDocument();
});

it("logout recusado não esconde expiração posterior", async () => {
  simularApi({
    "GET /api/carteira": carteira(),
    "GET /api/me/participacoes": [],
    "GET /api/auth/me": () => recusa("nao_autenticado", {}, 401),
    "POST /api/auth/logout": () => recusa("origem_invalida", {}, 403),
  });
  const { cliente } = renderizar(<App />, { rota: "/carteira", usuario: ANA });
  await screen.findByRole("heading", { name: "Minha carteira" });
  fireEvent.click(screen.getByRole("button", { name: "Sair" }));
  await screen.findByRole("alert");
  await act(async () => { await cliente.invalidateQueries({ queryKey: ["sessao"] }); });
  expect(await screen.findByText("Sua sessão expirou. Entre de novo.")).toBeInTheDocument();
});

it("logout pendente de A não esconde expiração da nova identidade B", async () => {
  const logout = promessa<unknown>();
  simularApi({
    "GET /api/carteira": carteira(),
    "GET /api/me/participacoes": [],
    "GET /api/auth/me": () => recusa("nao_autenticado", {}, 401),
    "POST /api/auth/logout": () => logout.pendente,
  });
  const { cliente } = renderizar(<App />, { rota: "/carteira", usuario: ANA });
  await screen.findByRole("heading", { name: "Minha carteira" });
  fireEvent.click(screen.getByRole("button", { name: "Sair" }));
  act(() => trocarIdentidade(cliente, { reiniciar: vi.fn() }, BRUNO));
  await act(async () => { await cliente.invalidateQueries({ queryKey: ["sessao"] }); });
  expect(await screen.findByText("Sua sessão expirou. Entre de novo.")).toBeInTheDocument();
  await act(async () => {
    logout.liberar(respostaJson(null, 204));
    await logout.pendente;
  });
  expect(screen.getByText("Sua sessão expirou. Entre de novo.")).toBeInTheDocument();
});
