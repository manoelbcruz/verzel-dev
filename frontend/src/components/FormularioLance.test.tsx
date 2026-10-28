import { QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import FormularioLance from "./FormularioLance";
import { ANA, ID, lote } from "../test/dados";
import { criarClienteTeste, simularApi } from "../test/utilitarios";

function renderizar(ui: React.ReactNode) {
  const cliente = criarClienteTeste();
  return render(ui, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={cliente}>{children}</QueryClientProvider>
    ),
  });
}

it("não avisa sobre aumento pelo próprio lance aceito", async () => {
  simularApi({ [`POST /api/lotes/${ID}/lances`]: { valor_centavos: 1500 } });
  const { rerender } = renderizar(<FormularioLance lote={lote()} usuario={ANA} fase="ao_vivo" />);
  fireEvent.click(screen.getByRole("button", { name: "Dar lance" }));
  await screen.findByText("registrado.", { exact: false });
  rerender(<FormularioLance
    lote={lote({ proximo_lance_minimo_centavos: 1600 })}
    usuario={ANA}
    fase="ao_vivo"
  />);
  expect(screen.queryByText(/O mínimo subiu/)).not.toBeInTheDocument();
});

it("não avisa quando o usuário lidera e o mínimo aumenta", () => {
  const inicial = lote();
  const { rerender } = renderizar(<FormularioLance lote={inicial} usuario={ANA} fase="ao_vivo" />);
  rerender(<FormularioLance
    lote={{ ...inicial, proximo_lance_minimo_centavos: 1600, minha_participacao: {
      meu_pseudonimo: "pessoa-a", ganhando: true, meu_maior_lance_centavos: 1500,
      posicao: 1, total_participantes: 1,
    } }}
    usuario={ANA}
    fase="ao_vivo"
  />);
  expect(screen.queryByText(/O mínimo subiu/)).not.toBeInTheDocument();
});

it.each(["editar", "enviar", "tempo"])("limpa aviso ao %s", async (acao) => {
  vi.useFakeTimers();
  simularApi({ [`POST /api/lotes/${ID}/lances`]: () => new Promise(() => {}) });
  const { rerender } = renderizar(<FormularioLance lote={lote()} usuario={ANA} fase="ao_vivo" />);
  rerender(<FormularioLance
    lote={lote({ proximo_lance_minimo_centavos: 1600 })}
    usuario={ANA}
    fase="ao_vivo"
  />);
  expect(screen.getByText(/O mínimo subiu/)).toBeInTheDocument();
  if (acao === "editar") {
    fireEvent.change(screen.getByLabelText("Seu lance (R$)"), { target: { value: "17,00" } });
  } else if (acao === "enviar") {
    fireEvent.click(screen.getByRole("button", { name: "Dar lance" }));
  } else {
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
  }
  expect(screen.queryByText(/O mínimo subiu/)).not.toBeInTheDocument();
});
