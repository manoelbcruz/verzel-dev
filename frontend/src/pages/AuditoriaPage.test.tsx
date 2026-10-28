import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import AuditoriaPage from "./AuditoriaPage";
import { ID, auditoria, recusa } from "../test/dados";
import { renderizar, simularApi } from "../test/utilitarios";
it.each([false, true])("exibe veredito e falha: %s", async (adulterado) => {
  simularApi({
    [`GET /api/lotes/${ID}/auditoria`]: {
      ...auditoria(),
      veredito: adulterado ? "adulterado" : "integro",
      falha: adulterado ? { codigo: "mac_divergente", mensagem: "Evento alterado", seq: 1 } : null,
    },
  });
  renderizar(<AuditoriaPage />, { rota: `/auditoria/${ID}`, caminho: "/auditoria/:loteId" });
  expect(await screen.findByRole("heading", {
    name: adulterado ? "⚠ Adulterado" : "✓ Íntegro",
  })).toBeInTheDocument();
  if (adulterado) {
    expect(screen.getByText(/mac_divergente.*Evento alterado.*Sequência 1/)).toBeInTheDocument();
  }
  const mac = screen.getByText(`${"b".repeat(12)}…`).closest("[tabindex]")!;
  fireEvent.focus(mac);
  expect(screen.getByRole("tooltip")).toHaveTextContent("b".repeat(64));
  expect(mac).toHaveAccessibleDescription("b".repeat(64));
});
it("id inválido mostra não encontrado", async () => {
  simularApi({ "GET /api/lotes/invalido/auditoria": recusa("entrada_invalida", {}, 422) });
  renderizar(<AuditoriaPage />, { rota: "/auditoria/invalido", caminho: "/auditoria/:loteId" });
  expect(await screen.findByRole("alert")).toHaveTextContent("não encontrado");
});

it("exibe histórico adulterado com valor inseguro e verifica novamente", async () => {
  const base = auditoria();
  const dados = {
    ...base,
    veredito: "adulterado",
    falha: { codigo: "mac_divergente", mensagem: "Evento alterado", seq: 2 },
    total_eventos: 4,
    eventos_verificados: 1,
    eventos: [
      base.eventos[0],
      { ...base.eventos[0], seq: 2, tipo: "lance", valor_centavos: 2 ** 53,
        licitante_pseudonimo: "pseudonimo-completo", prorrogou: true,
        fim_novo: new Date().toISOString(), verificado: false },
      { ...base.eventos[0], seq: 3, tipo: "cancelamento", verificado: false },
      { ...base.eventos[0], seq: 4, tipo: "encerramento", verificado: false },
    ],
  };
  const { pedidos } = simularApi({ [`GET /api/lotes/${ID}/auditoria`]: () => dados });
  renderizar(<AuditoriaPage />, { rota: `/auditoria/${ID}`, caminho: "/auditoria/:loteId" });
  expect(await screen.findByRole("heading", { name: "⚠ Adulterado" })).toBeInTheDocument();
  const tabela = within(screen.getByRole("table"));
  expect(tabela.getAllByRole("row")).toHaveLength(5);
  for (const tipo of ["Publicação", "Lance", "Cancelamento", "Encerramento"]) {
    expect(tabela.getByRole("cell", { name: tipo })).toBeInTheDocument();
  }
  expect(tabela.getByText("valor inválido")).toBeInTheDocument();
  expect(tabela.getByText("pseudonimo-completo")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Verificar novamente" }));
  await waitFor(() => expect(pedidos).toHaveLength(2));
});
