import { fireEvent, screen, waitFor } from "@testing-library/react";
import CarteiraPage from "./CarteiraPage";
import { ANA, carteira, recusa } from "../test/dados";
import { renderizar, respostaJson, simularApi } from "../test/utilitarios";

it("mostra saldos, deposita centavos e consulta o saldo atual em vez do replay", async () => {
  let leituras = 0;
  const { pedidos } = simularApi({
    "GET /api/carteira": () => carteira(++leituras === 1 ? 100000 : 250000),
    "GET /api/me/participacoes": [],
    "POST /api/carteira/depositos": () => {
      const resposta = respostaJson(carteira(110000), 201);
      resposta.headers.set("Idempotency-Replayed", "true");
      return resposta;
    },
  });
  renderizar(<CarteiraPage />, { usuario: ANA });
  expect(await screen.findByText("R$ 1.000,00", { selector: ".dinheiro" })).toBeInTheDocument();
  expect(screen.getByText("R$ 20,00")).toBeInTheDocument();
  expect(screen.getByText("R$ 980,00")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Depositar" }));
  expect(await screen.findByText("R$ 2.500,00")).toBeInTheDocument();
  const post = pedidos.find((p) => p.metodo === "POST")!;
  expect(post.corpo).toEqual({ valor_centavos: 10000 });
  expect(post.headers.get("Idempotency-Key")).toBeTruthy();
  expect(screen.queryByText("R$ 1.100,00")).not.toBeInTheDocument();
});

it("explica limite de saldo", async () => {
  simularApi({
    "GET /api/carteira": carteira(),
    "GET /api/me/participacoes": [],
    "POST /api/carteira/depositos": recusa("limite_saldo"),
  });
  renderizar(<CarteiraPage />, { usuario: ANA });
  fireEvent.click(await screen.findByRole("button", { name: "Depositar" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("limite de saldo"));
});

it.each(["", "abc", "0,00", "1.000.000,01"])(
  "depósito inválido %s foca o campo e não chama a API", async (valor) => {
    const { pedidos } = simularApi({
      "GET /api/carteira": carteira(), "GET /api/me/participacoes": [],
    });
    renderizar(<CarteiraPage />, { usuario: ANA });
    const campo = await screen.findByLabelText("Valor do depósito (R$)");
    fireEvent.change(campo, { target: { value: valor } });
    fireEvent.click(screen.getByRole("button", { name: "Depositar" }));
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo).toHaveAccessibleDescription();
    expect(campo).toHaveFocus();
    expect(pedidos.some((p) => p.metodo === "POST")).toBe(false);
  },
);
