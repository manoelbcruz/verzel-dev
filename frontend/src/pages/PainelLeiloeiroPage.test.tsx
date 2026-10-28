import { fireEvent, screen, waitFor } from "@testing-library/react";
import PainelLeiloeiroPage from "./PainelLeiloeiroPage";
import { LEILOEIRO, lote, recusa } from "../test/dados";
import { renderizar, simularApi } from "../test/utilitarios";
it("mostra recebido, comprovante e permite cancelar só lote cancelável", async () => {
  simularApi({
    "GET /api/leiloeiro/lotes": {
      total_recebido_centavos: 1600,
      lotes: [
        lote({ id: "cancelavel", cancelavel: true }),
        lote({ id: "vendido", resultado: {
          situacao: "arrematado", valor_centavos: 1600, vencedor_pseudonimo: "Pessoa",
          encerrado_em: new Date().toISOString(), comprovante_codigo: "venda",
        } }),
      ],
    },
    "POST /api/leiloeiro/lotes/cancelavel/cancelar": recusa("lote_com_lances"),
  });
  renderizar(<PainelLeiloeiroPage />, { usuario: LEILOEIRO });
  expect(await screen.findByRole("link", { name: "Ver comprovante: Obra do acervo" }))
    .toHaveAttribute("href", "/comprovantes/venda");
  expect(screen.getByRole("heading", { name: "Total recebido" }).parentElement)
    .toHaveTextContent("R$ 16,00");
  expect(screen.getAllByRole("button", { name: "Cancelar lote: Obra do acervo" })).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Cancelar lote: Obra do acervo" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirmar cancelamento" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("já recebeu lances");
});

it("cancelamento confirmado refaz o painel e retira a ação", async () => {
  let obra = lote({ cancelavel: true });
  const { pedidos } = simularApi({
    "GET /api/leiloeiro/lotes": () => ({ total_recebido_centavos: 0, lotes: [obra] }),
    [`POST /api/leiloeiro/lotes/${obra.id}/cancelar`]: () => {
      obra = { ...obra, fase: "cancelado", cancelavel: false };
      return obra;
    },
  });
  renderizar(<PainelLeiloeiroPage />, { usuario: LEILOEIRO });
  fireEvent.click(await screen.findByRole("button", { name: "Cancelar lote: Obra do acervo" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirmar cancelamento" }));
  expect(await screen.findByText("Cancelado")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Confirmar cancelamento" })).not.toBeInTheDocument();
  await waitFor(() => expect(pedidos.filter((p) => p.metodo === "GET")).toHaveLength(2));
  expect(pedidos.filter((p) => p.metodo === "POST")).toHaveLength(1);
});
