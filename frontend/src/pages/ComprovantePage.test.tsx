import { fireEvent, screen } from "@testing-library/react";
import ComprovantePage from "./ComprovantePage";
import { comprovante, recusa } from "../test/dados";
import { renderizar, simularApi } from "../test/utilitarios";

it("exibe dados públicos e link copiável com a origem", async () => {
  simularApi({ "GET /api/comprovantes/codigo-publico": comprovante() });
  renderizar(<ComprovantePage />, {
    rota: "/comprovantes/codigo-publico", caminho: "/comprovantes/:codigo",
  });
  expect(await screen.findByText("R$ 16,00")).toBeInTheDocument();
  expect(screen.getByText("Vencedor: Pessoa-vencedora")).toBeInTheDocument();
  expect(screen.getByText("a".repeat(64))).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Copiar link" }));
  expect(await screen.findByLabelText("Link para compartilhar"))
    .toHaveValue(`${location.origin}/comprovantes/codigo-publico`);
});

it.each([404, 422])("mapeia código inválido %s", async (status) => {
  simularApi({
    "GET /api/comprovantes/invalido": recusa(
      status === 404 ? "comprovante_nao_encontrado" : "entrada_invalida", {}, status,
    ),
  });
  renderizar(<ComprovantePage />, {
    rota: "/comprovantes/invalido", caminho: "/comprovantes/:codigo",
  });
  expect(await screen.findByRole("alert")).toHaveTextContent("não encontrado");
});
