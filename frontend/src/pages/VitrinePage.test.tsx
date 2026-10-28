import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import VitrinePage from "./VitrinePage";
import { lote, promessa, vitrine } from "../test/dados";
import { renderizar, simularApi } from "../test/utilitarios";
it("agrupa por fase efetiva, filtra, busca e oculta cancelados", async () => {
  const dados = vitrine({
    ao_vivo: [
      lote({ titulo: "Sol" }),
      lote({ id: "cancelado", titulo: "Cancelado proibido", fase: "cancelado" }),
    ],
    agendados: [lote({
      id: "futuro", titulo: "Obra futura", fase: "agendado",
      inicio_em: new Date(Date.now() + 600000).toISOString(),
    })],
    encerrados: [lote({
      id: "passado", titulo: "Obra passada", fase: "encerrado",
      fim_em: new Date(Date.now() - 1000).toISOString(),
    })],
  });
  const { pedidos } = simularApi({
    "GET /api/lotes": dados,
    "GET /api/lotes?q=sol": vitrine({ ao_vivo: [dados.ao_vivo[0]] }),
  });
  renderizar(<VitrinePage />);
  expect(await screen.findByRole("heading", { name: "Sol" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Agendados 1" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Encerrados 1" })).toBeInTheDocument();
  expect(screen.queryByText("Cancelado proibido")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Agendados" }));
  expect(screen.queryByRole("heading", { name: "Sol" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Todos" }));
  fireEvent.change(screen.getByLabelText("Buscar por título"), { target: { value: "sol" } });
  await waitFor(() => expect(pedidos.some((p) => p.caminho === "/api/lotes?q=sol")).toBe(true));
});

it("refaz a lista depois do início e do fim mesmo com os tiques do relógio", async () => {
  vi.useFakeTimers();
  const agora = Date.now();
  const obra = lote({ inicio_em: new Date(agora + 2000).toISOString(),
    fim_em: new Date(agora + 6000).toISOString(), fase: "agendado" });
  const { pedidos } = simularApi({ "GET /api/lotes": () => vitrine({ agendados: [obra] }) });
  renderizar(<VitrinePage />);
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(pedidos).toHaveLength(1);
  await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
  expect(pedidos).toHaveLength(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(4000); });
  expect(pedidos).toHaveLength(3);
});
it("espera a primeira leitura e mantém a vitrine anterior durante a busca", async () => {
  const primeira = promessa<unknown>();
  const busca = promessa<unknown>();
  const { pedidos } = simularApi({ "GET /api/lotes": () => primeira.pendente,
    "GET /api/lotes?q=sol": () => busca.pendente });
  renderizar(<VitrinePage />);
  expect(screen.queryByText("Nenhum lote nesta seção.")).not.toBeInTheDocument();
  await act(async () => primeira.liberar(vitrine({ ao_vivo: [lote({ titulo: "Sol" })] })));
  expect(await screen.findByRole("heading", { name: "Sol" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Buscar por título"), { target: { value: "sol" } });
  await waitFor(() => expect(pedidos).toHaveLength(2));
  expect(screen.getByRole("heading", { name: "Sol" })).toBeInTheDocument();
  await act(async () => busca.liberar(vitrine({ ao_vivo: [lote({ titulo: "Sol novo" })] })));
  expect(await screen.findByRole("heading", { name: "Sol novo" })).toBeInTheDocument();
});
